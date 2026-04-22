import { Duration, Lazy, Stack, StackProps } from 'aws-cdk-lib';
import {
  Memory,
  MemoryStrategy,
  RuntimeAuthorizerConfiguration,
} from '@aws-cdk/aws-bedrock-agentcore-alpha';
import {
  ManagedPolicy,
  PolicyStatement,
  Role,
  ServicePrincipal,
} from 'aws-cdk-lib/aws-iam';
import { CfnAppMonitor } from 'aws-cdk-lib/aws-rum';
import { CfnSchedule } from 'aws-cdk-lib/aws-scheduler';
import { Function } from 'aws-cdk-lib/aws-lambda';
import { Port } from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';
import {
  Api,
  DatabaseAgent,
  ClientSearchAgent,
  EmailSenderGateway,
  GraphSearchAgent,
  GraphSearchApi,
  IntelligenceApi,
  NeptuneGraph,
  StockDataAgent,
  NeptuneAnalyticsGateway,
  PortfolioDataGateway,
  ScheduleResultsTable,
  SchedulerExecutorScheduleExecutor,
  SchedulerGateway,
  SchedulesTable,
  SmartChatDataAccess,
  RedshiftDataAccess,
  ReportAgent,
  ReportSchedulerStateMachine,
  RoutingAgent,
  RuntimeConfig,
  SchedulerToolsGetClientList,
  SchedulerToolsGenerateReport,
  ThemeGeneratorStateMachine,
  ThemeSchedulerGenerateGeneralThemes,
  ThemeSchedulerGeneratePortfolioThemes,
  Ui,
  UserIdentity,
  VoiceGateway,
  WebCrawlerMcp,
  WebSearchAgent,
} from ':wealth-management-portal/common-constructs';

export class ApplicationStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const redshiftWorkgroup =
      this.node.tryGetContext('redshiftWorkgroup') ?? 'financial-advisor-wg';
    const redshiftDatabase =
      this.node.tryGetContext('redshiftDatabase') ?? 'financial-advisor-db';

    // Cognito user pool and identity pool
    const identity = new UserIdentity(this, 'Identity');

    // Core API — dashboard, clients, holdings, transactions, report
    const vpcConfig = {
      vpcId: this.node.tryGetContext('redshiftVpcId'),
      privateSubnetIds: this.node.tryGetContext('privateSubnetIds'),
      redshiftSecurityGroupId: this.node.tryGetContext(
        'redshiftSecurityGroupId',
      ),
    };

    const api = new Api(this, 'Api', {
      integrations: Api.defaultIntegrations(this, vpcConfig).build(),
      identity,
      vpcId: vpcConfig.vpcId,
      privateSubnetIds: vpcConfig.privateSubnetIds,
      redshiftSecurityGroupId: vpcConfig.redshiftSecurityGroupId,
    });

    // Intelligence API — chat (heavy AI/ML dependencies isolated)
    const intelligenceApi = new IntelligenceApi(this, 'IntelligenceApi', {
      integrations: IntelligenceApi.defaultIntegrations(this).build(),
      identity,
    });

    // Graph Search API — FastAPI Lambda for graph data load + AI search SSE
    const graphSearchApi = new GraphSearchApi(this, 'GraphSearchApi', {
      integrations: GraphSearchApi.defaultIntegrations(this).build(),
      identity,
    });

    // Placeholder for graph search agent ARN — resolved lazily after agent is created below
    let graphSearchAgentArnValue = '';
    RuntimeConfig.ensure(this).config.graphSearchAgentArn = Lazy.string({
      produce: () => graphSearchAgentArnValue,
    });

    // Placeholder for routing agent ARN — resolved lazily after agent is created below
    let routingAgentArnValue = '';
    RuntimeConfig.ensure(this).config.routingAgentArn = Lazy.string({
      produce: () => routingAgentArnValue,
    });

    // Placeholder for voice gateway ARN — resolved lazily after gateway is created below
    let voiceGatewayArnValue = '';
    RuntimeConfig.ensure(this).config.voiceGatewayArn = Lazy.string({
      produce: () => voiceGatewayArnValue,
    });

    // Lazy placeholders for scheduler gateway URLs — resolved after gateways are created
    let schedulerGatewayUrlValue = '';
    let emailSenderGatewayUrlValue = '';

    // React website (must be declared after APIs and identity for runtime config)
    const ui = new Ui(this, 'Ui');

    // ── CloudWatch RUM ────────────────────────────────────────────────────
    const rumGuestRole = new Role(this, 'RumGuestRole', {
      assumedBy: new ServicePrincipal('rum.amazonaws.com'),
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName('AmazonCloudWatchRUMFullAccess'),
      ],
    });

    const rumAppMonitor = new CfnAppMonitor(this, 'RumAppMonitor', {
      name: `${Stack.of(this).stackName}-rum`,
      domain: ui.cloudFrontDistribution.domainName,
      appMonitorConfiguration: {
        allowCookies: true,
        enableXRay: true,
        sessionSampleRate: 1.0,
        telemetries: ['errors', 'performance', 'http'],
        identityPoolId: identity.identityPool.identityPoolId,
        guestRoleArn: rumGuestRole.roleArn,
      },
      cwLogEnabled: true,
    });

    RuntimeConfig.ensure(this).config.rumConfig = {
      appMonitorId: rumAppMonitor.ref,
      identityPoolId: identity.identityPool.identityPoolId,
      region: this.region,
    };

    // Grant Cognito unauthenticated role permission to send RUM telemetry
    identity.identityPool.unauthenticatedRole.addToPrincipalPolicy(
      new PolicyStatement({
        actions: ['rum:PutRumEvents'],
        resources: [
          `arn:aws:rum:${this.region}:${this.account}:appmonitor/${rumAppMonitor.name}`,
        ],
      }),
    );

    // Restrict API CORS to the website domain
    api.restrictCorsTo(ui);
    intelligenceApi.restrictCorsTo(ui);
    graphSearchApi.restrictCorsTo(ui);

    // ── Graph Search ──────────────────────────────────────────────────────

    // Neptune Analytics graph — provisioned by CDK, graph ID wired internally via token
    const neptuneGraph = new NeptuneGraph(this, 'NeptuneGraph');

    // Neptune Analytics Gateway — exposes execute_cypher, find_similar, etc. via AgentCore Gateway
    const neptuneGateway = new NeptuneAnalyticsGateway(
      this,
      'NeptuneAnalyticsGateway',
      {
        neptuneGraphId: neptuneGraph.graphId,
      },
    );

    // Graph Search Agent — Strands Agent on AgentCore for Cypher gen + reasoning
    const graphSearchAgent = new GraphSearchAgent(this, 'GraphSearchAgent', {
      environmentVariables: {
        NEPTUNE_GATEWAY_URL: neptuneGateway.gateway.gatewayUrl!,
        NEPTUNE_GRAPH_ID: neptuneGraph.graphId,
        AWS_REGION: this.region,
        GRAPH_SEARCH_MODE: 'agentcore',
      },
    });
    neptuneGateway.gateway.grantInvoke(graphSearchAgent.agentCoreRuntime.role);

    // Grant Graph Search Agent Bedrock access (Cypher generation + reasoning)
    graphSearchAgent.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );

    // Direct Neptune read access (metric computation + MCP fallback)
    graphSearchAgent.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'neptune-graph:ExecuteQuery',
          'neptune-graph:ReadDataViaQuery',
          'neptune-graph:GetGraph',
        ],
        resources: [
          `arn:aws:neptune-graph:${this.region}:${this.account}:graph/*`,
        ],
      }),
    );

    // Expose graph search agent ARN to UI for direct invocation (bypasses API Gateway 29s timeout)
    graphSearchAgentArnValue =
      graphSearchAgent.agentCoreRuntime.agentRuntimeArn;

    // Grant Cognito Identity Pool authenticated users permission to invoke the graph search agent directly
    graphSearchAgent.agentCoreRuntime.grantInvoke(
      identity.identityPool.authenticatedRole,
    );

    // Grant Graph Search API Lambda permissions
    Object.values(graphSearchApi.integrations).forEach((integration) => {
      if ('handler' in integration && integration.handler instanceof Function) {
        // Direct Neptune access for data load (Flow 1)
        integration.handler.role?.addToPrincipalPolicy(
          new PolicyStatement({
            actions: [
              'neptune-graph:ExecuteQuery',
              'neptune-graph:ReadDataViaQuery',
              'neptune-graph:WriteDataViaQuery',
              'neptune-graph:DeleteDataViaQuery',
              'neptune-graph:GetGraph',
            ],
            resources: [
              `arn:aws:neptune-graph:${this.region}:${this.account}:graph/*`,
            ],
          }),
        );
        // Invoke Graph Search Agent for AI search (Flow 2)
        integration.handler.addEnvironment(
          'GRAPH_SEARCH_AGENT_ARN',
          graphSearchAgent.agentCoreRuntime.agentRuntimeArn,
        );
        integration.handler.addEnvironment('GRAPH_SEARCH_MODE', 'agentcore');
        integration.handler.addEnvironment(
          'NEPTUNE_GRAPH_ID',
          neptuneGraph.graphId,
        );
        graphSearchAgent.agentCoreRuntime.grantInvoke(integration.handler);
        // Bedrock access for direct Cypher gen (local fallback)
        integration.handler.role?.addToPrincipalPolicy(
          new PolicyStatement({
            actions: [
              'bedrock:InvokeModel',
              'bedrock:InvokeModelWithResponseStream',
            ],
            resources: [
              'arn:aws:bedrock:*::foundation-model/*',
              `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
            ],
          }),
        );
      }
    });

    // Portfolio data server — Gateway + Lambda interface to Redshift
    const portfolioGateway = new PortfolioDataGateway(
      this,
      'PortfolioGateway',
      {
        vpcId: this.node.tryGetContext('redshiftVpcId'),
        privateSubnetIds: this.node.tryGetContext('privateSubnetIds'),
        privateRouteTableId: this.node.tryGetContext('privateRouteTableId'),
        redshiftSecurityGroupId: this.node.tryGetContext(
          'redshiftSecurityGroupId',
        ),
        redshiftWorkgroup,
        redshiftDatabase,
      },
    );

    // Allow Core API Lambda to reach VPC endpoints created by PortfolioDataGateway
    // (STS, Redshift Serverless — needed by iam_connection_factory for direct DB connections)
    if (api.lambdaSecurityGroup) {
      portfolioGateway.vpcEndpointSecurityGroup.addIngressRule(
        api.lambdaSecurityGroup,
        Port.tcp(443),
        'Core API Lambda access to VPC endpoints',
      );
      api.lambdaSecurityGroup.addEgressRule(
        portfolioGateway.vpcEndpointSecurityGroup,
        Port.tcp(443),
        'Core API Lambda to shared VPC endpoints',
      );
    }

    // Report agent — granted permission to invoke the portfolio gateway
    const reportAgent = new ReportAgent(this, 'ReportAgent', {
      environmentVariables: {
        PORTFOLIO_GATEWAY_URL: portfolioGateway.gateway.gatewayUrl!,
        AWS_REGION: this.region,
      },
    });
    portfolioGateway.gateway.grantInvoke(reportAgent.agentCoreRuntime.role);

    // SmartChatDataAccess Gateway — execute_sql Lambda for advisor_chat agents (replaces RedshiftDataAccess MCP container)
    const smartChatDataAccess = new SmartChatDataAccess(
      this,
      'SmartChatDataAccess',
      {
        vpcId: this.node.tryGetContext('redshiftVpcId'),
        privateSubnetIds: this.node.tryGetContext('privateSubnetIds'),
        privateRouteTableId: this.node.tryGetContext('privateRouteTableId'),
        mcpSecurityGroup: portfolioGateway.mcpSecurityGroup,
        redshiftWorkgroup,
        redshiftDatabase,
      },
    );

    // Redshift Data Access MCP — execute_sql for advisor_chat agents (reuses PortfolioDataAccess VPC/SG)
    const redshiftMcp = new RedshiftDataAccess(this, 'RedshiftDataAccess', {
      vpcId: this.node.tryGetContext('redshiftVpcId'),
      privateSubnetIds: this.node.tryGetContext('privateSubnetIds'),
      privateRouteTableId: this.node.tryGetContext('privateRouteTableId'),
      mcpSecurityGroup: portfolioGateway.mcpSecurityGroup,
      redshiftWorkgroup,
      redshiftDatabase,
    });
    redshiftMcp.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'redshift-serverless:GetCredentials',
          'redshift-serverless:GetWorkgroup',
        ],
        resources: [
          `arn:aws:redshift-serverless:${this.region}:${this.account}:workgroup/*`,
        ],
      }),
    );
    redshiftMcp.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'lakeformation:GetDataAccess',
          'glue:GetTable',
          'glue:GetTables',
          'glue:GetDatabase',
          'glue:GetDatabases',
          'glue:GetCatalog',
        ],
        resources: ['*'],
      }),
    );

    // Grant report agent permission to invoke Bedrock models
    reportAgent.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );

    // Web Crawler MCP — granted permission to invoke the portfolio gateway
    const webCrawlerMcp = new WebCrawlerMcp(this, 'WebCrawlerMcp', {
      environmentVariables: {
        PORTFOLIO_GATEWAY_URL: portfolioGateway.gateway.gatewayUrl!,
        AWS_REGION: this.region,
      },
    });
    portfolioGateway.gateway.grantInvoke(webCrawlerMcp.agentCoreRuntime.role);

    // Grant web crawler permission to invoke Bedrock models
    webCrawlerMcp.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );

    // Client search agent — NL-to-SQL via Strands on AgentCore
    const clientSearchAgent = new ClientSearchAgent(this, 'ClientSearchAgent');

    clientSearchAgent.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );

    // ── Advisor Chat A2A Agents ───────────────────────────────────────────

    // Database Agent — portfolio, holdings, AUM queries
    const databaseAgent = new DatabaseAgent(this, 'DatabaseAgent', {
      environmentVariables: {
        SMART_CHAT_GATEWAY_URL: smartChatDataAccess.gateway.gatewayUrl!,
        REDSHIFT_MCP_ARN: redshiftMcp.agentCoreRuntime.agentRuntimeArn,
        AWS_REGION: this.region,
        REPORT_S3_BUCKET: reportAgent.reportBucket.bucketName,
        REPORT_AGENT_ARN: reportAgent.agentCoreRuntime.agentRuntimeArn,
      },
    });
    reportAgent.reportBucket.grantRead(databaseAgent.agentCoreRuntime.role);
    reportAgent.agentCoreRuntime.grantInvoke(databaseAgent.agentCoreRuntime);
    smartChatDataAccess.gateway.grantInvoke(
      databaseAgent.agentCoreRuntime.role,
    );
    databaseAgent.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );
    redshiftMcp.agentCoreRuntime.grantInvoke(databaseAgent.agentCoreRuntime);

    // Stock Data Agent — advisor dashboard, fees, stock quotes
    const stockDataAgent = new StockDataAgent(this, 'StockDataAgent', {
      environmentVariables: {
        SMART_CHAT_GATEWAY_URL: smartChatDataAccess.gateway.gatewayUrl!,
        REDSHIFT_MCP_ARN: redshiftMcp.agentCoreRuntime.agentRuntimeArn,
        AWS_REGION: this.region,
        TAVILY_API_KEY: this.node.tryGetContext('tavilyApiKey') || '',
      },
    });
    smartChatDataAccess.gateway.grantInvoke(
      stockDataAgent.agentCoreRuntime.role,
    );
    stockDataAgent.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );
    redshiftMcp.agentCoreRuntime.grantInvoke(stockDataAgent.agentCoreRuntime);

    // Web Search Agent — news articles, market themes
    const webSearchAgent = new WebSearchAgent(this, 'WebSearchAgent', {
      environmentVariables: {
        SMART_CHAT_GATEWAY_URL: smartChatDataAccess.gateway.gatewayUrl!,
        REDSHIFT_MCP_ARN: redshiftMcp.agentCoreRuntime.agentRuntimeArn,
        AWS_REGION: this.region,
        TAVILY_API_KEY: this.node.tryGetContext('tavilyApiKey') || '',
      },
    });
    webSearchAgent.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );
    smartChatDataAccess.gateway.grantInvoke(
      webSearchAgent.agentCoreRuntime.role,
    );
    redshiftMcp.agentCoreRuntime.grantInvoke(webSearchAgent.agentCoreRuntime);

    // Routing Agent — orchestrates specialist agents, exposes /chat/stream SSE
    // Pre-create memory stores so first chat doesn't hit cold-start
    const stm = new Memory(this, 'ShortTermMemory', {
      memoryName: 'WealthMgmt_STM',
      description: 'Short-term conversation memory',
      expirationDuration: Duration.days(7),
    });
    const ltm = new Memory(this, 'LongTermMemory', {
      memoryName: 'WealthMgmt_LTM',
      description: 'Long-term schema and SQL artifact memory',
      expirationDuration: Duration.days(30),
      memoryStrategies: [
        MemoryStrategy.usingSemantic({
          name: 'SchemaAndSQL',
          namespaces: ['/knowledge/{actorId}/'],
        }),
        MemoryStrategy.usingSummarization({
          name: 'SessionSummarizer',
          namespaces: ['/summaries/{actorId}/{sessionId}/'],
        }),
      ],
    });

    const routingAgent = new RoutingAgent(this, 'RoutingAgent', {
      environmentVariables: {
        DATABASE_AGENT_ARN: databaseAgent.agentCoreRuntime.agentRuntimeArn,
        STOCK_DATA_AGENT_ARN: stockDataAgent.agentCoreRuntime.agentRuntimeArn,
        WEB_SEARCH_AGENT_ARN: webSearchAgent.agentCoreRuntime.agentRuntimeArn,
        AWS_REGION: this.region,
        AGENTCORE_STM_ID: stm.memoryId,
        AGENTCORE_LTM_ID: ltm.memoryId,
        SCHEDULER_GATEWAY_URL: Lazy.string({
          produce: () => schedulerGatewayUrlValue,
        }),
        EMAIL_SENDER_GATEWAY_URL: Lazy.string({
          produce: () => emailSenderGatewayUrlValue,
        }),
        EXECUTOR_CLIENT_ID: identity.executorClient.userPoolClientId,
        COGNITO_USER_POOL_ID: identity.userPool.userPoolId,
      },
      // Cognito JWT auth — Runtime validates tokens, agent decodes claims for identity
      authorizerConfiguration: RuntimeAuthorizerConfiguration.usingCognito(
        identity.userPool,
        [identity.userPoolClient, identity.executorClient],
      ),
      requestHeaderConfiguration: {
        allowlistedHeaders: [
          'Authorization',
          'X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId',
        ],
      },
    });
    routingAgent.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );
    routingAgent.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock-agentcore:CreateMemory',
          'bedrock-agentcore:ListMemories',
          'bedrock-agentcore:GetMemory',
          'bedrock-agentcore:CreateSession',
          'bedrock-agentcore:GetSession',
          'bedrock-agentcore:IngestMemoryContent',
          'bedrock-agentcore:RetrieveMemoryContent',
          // Event actions required by AgentCoreMemorySessionManager
          'bedrock-agentcore:CreateEvent',
          'bedrock-agentcore:GetEvent',
          'bedrock-agentcore:ListEvents',
          'bedrock-agentcore:DeleteEvent',
        ],
        resources: ['*'],
      }),
    );

    stm.grantFullAccess(routingAgent.agentCoreRuntime);
    ltm.grantFullAccess(routingAgent.agentCoreRuntime);

    // Avoid IAM SLR rate-limit on fresh accounts: ensure the first AgentCore
    // Runtime (graphSearchAgent) creates the service-linked role before the
    // rest deploy in parallel.
    for (const r of [
      reportAgent,
      redshiftMcp,
      clientSearchAgent,
      databaseAgent,
      stockDataAgent,
      webSearchAgent,
    ]) {
      r.node.addDependency(graphSearchAgent);
    }

    // Grant routing agent permission to invoke specialist agents
    databaseAgent.agentCoreRuntime.grantInvoke(routingAgent.agentCoreRuntime);
    stockDataAgent.agentCoreRuntime.grantInvoke(routingAgent.agentCoreRuntime);
    webSearchAgent.agentCoreRuntime.grantInvoke(routingAgent.agentCoreRuntime);

    // Expose routing agent ARN to UI for direct invocation (bypasses API Gateway timeout)
    routingAgentArnValue = routingAgent.agentCoreRuntime.agentRuntimeArn;

    // Voice Gateway — BidiAgent for Nova Sonic speech-to-speech
    const voiceGateway = new VoiceGateway(this, 'VoiceGateway', {
      environmentVariables: {
        DATABASE_AGENT_ARN: databaseAgent.agentCoreRuntime.agentRuntimeArn,
        STOCK_DATA_AGENT_ARN: stockDataAgent.agentCoreRuntime.agentRuntimeArn,
        WEB_SEARCH_AGENT_ARN: webSearchAgent.agentCoreRuntime.agentRuntimeArn,
        AWS_REGION: this.region,
      },
    });
    voiceGateway.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
          'bedrock:InvokeModelWithBidirectionalStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );
    // Grant voice gateway permission to invoke specialist agents
    databaseAgent.agentCoreRuntime.grantInvoke(voiceGateway.agentCoreRuntime);
    stockDataAgent.agentCoreRuntime.grantInvoke(voiceGateway.agentCoreRuntime);
    webSearchAgent.agentCoreRuntime.grantInvoke(voiceGateway.agentCoreRuntime);
    // Grant Cognito Identity Pool authenticated users permission to invoke voice gateway
    voiceGateway.agentCoreRuntime.grantInvoke(
      identity.identityPool.authenticatedRole,
    );
    // grantInvoke doesn't include the WebSocket action — add it explicitly
    identity.identityPool.authenticatedRole.addToPrincipalPolicy(
      new PolicyStatement({
        actions: ['bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream'],
        resources: [
          voiceGateway.agentCoreRuntime.agentRuntimeArn,
          `${voiceGateway.agentCoreRuntime.agentRuntimeArn}/*`,
        ],
      }),
    );
    voiceGatewayArnValue = voiceGateway.agentCoreRuntime.agentRuntimeArn;

    // ── Scheduler Feature ─────────────────────────────────────────────────

    // DynamoDB tables for schedules and results
    const schedulesTable = new SchedulesTable(this, 'SchedulesTable');
    const scheduleResultsTable = new ScheduleResultsTable(
      this,
      'ScheduleResultsTable',
    );

    // Executor Lambda — thin orchestrator triggered by EventBridge
    const scheduleExecutor = new SchedulerExecutorScheduleExecutor(
      this,
      'ScheduleExecutor',
    );
    scheduleExecutor.addEnvironment(
      'SCHEDULES_TABLE_NAME',
      schedulesTable.tableName,
    );
    scheduleExecutor.addEnvironment(
      'SCHEDULE_RESULTS_TABLE_NAME',
      scheduleResultsTable.tableName,
    );
    scheduleExecutor.addEnvironment(
      'ROUTING_AGENT_ARN',
      routingAgent.agentCoreRuntime.agentRuntimeArn,
    );
    scheduleExecutor.addEnvironment('AWS_REGION_NAME', this.region);
    scheduleExecutor.addEnvironment(
      'EXECUTOR_CLIENT_ID',
      identity.executorClient.userPoolClientId,
    );
    scheduleExecutor.addEnvironment(
      'EXECUTOR_CLIENT_SECRET_ARN',
      identity.executorSecret.secretArn,
    );
    scheduleExecutor.addEnvironment(
      'COGNITO_TOKEN_ENDPOINT',
      identity.cognitoTokenEndpoint,
    );
    identity.executorSecret.grantRead(scheduleExecutor);

    schedulesTable.grantReadWriteData(scheduleExecutor);
    scheduleResultsTable.grantReadWriteData(scheduleExecutor);

    // IAM role for EventBridge Scheduler → Executor Lambda
    const scheduleEventBridgeRole = new Role(this, 'ScheduleEventBridgeRole', {
      assumedBy: new ServicePrincipal('scheduler.amazonaws.com'),
    });
    scheduleExecutor.grantInvoke(scheduleEventBridgeRole);

    // Scheduler MCP Gateway — create/list/delete/toggle schedules
    const schedulerGateway = new SchedulerGateway(this, 'SchedulerGateway', {
      schedulesTable: schedulesTable,
      scheduleResultsTable: scheduleResultsTable,
      executorLambdaArn: scheduleExecutor.functionArn,
      eventBridgeRoleArn: scheduleEventBridgeRole.roleArn,
    });

    // Email Sender MCP Gateway — send emails via SES
    const emailSenderGateway = new EmailSenderGateway(
      this,
      'EmailSenderGateway',
      {
        senderEmail:
          this.node.tryGetContext('sesSenderEmail') ?? 'noreply@example.com',
        reportBucketName: reportAgent.reportBucket.bucketName,
      },
    );
    reportAgent.reportBucket.grantRead(emailSenderGateway.lambdaFunction);

    // Connect routing agent to new gateways
    schedulerGateway.gateway.grantInvoke(routingAgent.agentCoreRuntime.role);
    emailSenderGateway.gateway.grantInvoke(routingAgent.agentCoreRuntime.role);

    schedulerGatewayUrlValue = schedulerGateway.gateway.gatewayUrl!;
    emailSenderGatewayUrlValue = emailSenderGateway.gateway.gatewayUrl!;

    // Grant Core API Lambda read access to report bucket for presigned URL generation
    Object.values(api.integrations).forEach((integration) => {
      if ('handler' in integration && integration.handler instanceof Function) {
        integration.handler.addEnvironment(
          'REPORT_S3_BUCKET',
          reportAgent.reportBucket.bucketName,
        );
        integration.handler.addEnvironment(
          'REDSHIFT_WORKGROUP',
          redshiftWorkgroup,
        );
        integration.handler.addEnvironment(
          'REDSHIFT_DATABASE',
          redshiftDatabase,
        );
        reportAgent.reportBucket.grantRead(integration.handler);
        integration.handler.addEnvironment(
          'CLIENT_SEARCH_AGENT_ARN',
          clientSearchAgent.agentCoreRuntime.agentRuntimeArn,
        );
        clientSearchAgent.agentCoreRuntime.grantInvoke(integration.handler);
      }
    });

    // Grant Core API Lambda Redshift access for client segments and reports
    Object.values(api.integrations).forEach((integration) => {
      if ('handler' in integration && integration.handler instanceof Function) {
        integration.handler.role?.addToPrincipalPolicy(
          new PolicyStatement({
            actions: [
              'redshift-data:ExecuteStatement',
              'redshift-data:DescribeStatement',
              'redshift-data:GetStatementResult',
              'redshift-serverless:GetCredentials',
              'redshift-serverless:GetWorkgroup',
            ],
            resources: [
              `arn:aws:redshift-serverless:${this.region}:${this.account}:workgroup/*`,
            ],
          }),
        );
        integration.handler.role?.addToPrincipalPolicy(
          new PolicyStatement({
            actions: [
              'redshift-data:DescribeStatement',
              'redshift-data:GetStatementResult',
            ],
            resources: ['*'],
          }),
        );
        // Required for Redshift to resolve federated S3 Tables catalog views via Lake Formation
        integration.handler.role?.addToPrincipalPolicy(
          new PolicyStatement({
            actions: [
              'lakeformation:GetDataAccess',
              'glue:GetTable',
              'glue:GetTables',
              'glue:GetDatabase',
              'glue:GetDatabases',
              'glue:GetCatalog',
            ],
            resources: ['*'],
          }),
        );
      }
    });

    // Grant Intelligence API Lambda Bedrock access + advisor chat agent ARNs
    Object.values(intelligenceApi.integrations).forEach((integration) => {
      if ('handler' in integration && integration.handler instanceof Function) {
        integration.handler.role?.addToPrincipalPolicy(
          new PolicyStatement({
            actions: [
              'bedrock:InvokeModel',
              'bedrock:InvokeModelWithResponseStream',
            ],
            resources: [
              'arn:aws:bedrock:*::foundation-model/*',
              `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
            ],
          }),
        );
        // Pass advisor chat agent ARNs for A2A routing
        integration.handler.addEnvironment(
          'DATABASE_AGENT_ARN',
          databaseAgent.agentCoreRuntime.agentRuntimeArn,
        );
        integration.handler.addEnvironment(
          'STOCK_DATA_AGENT_ARN',
          stockDataAgent.agentCoreRuntime.agentRuntimeArn,
        );
        // Grant invoke permissions
        databaseAgent.agentCoreRuntime.grantInvoke(integration.handler);
        stockDataAgent.agentCoreRuntime.grantInvoke(integration.handler);
      }
    });

    // --- Report Scheduler (EventBridge + Step Functions) ---

    const getClientList = new SchedulerToolsGetClientList(
      this,
      'GetClientList',
    );

    getClientList.addEnvironment('REDSHIFT_WORKGROUP', redshiftWorkgroup);
    getClientList.addEnvironment('REDSHIFT_DATABASE', redshiftDatabase);
    getClientList.addEnvironment('POWERTOOLS_SERVICE_NAME', 'scheduler-tools');
    getClientList.addEnvironment('LOG_LEVEL', 'INFO');

    getClientList.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'redshift-data:ExecuteStatement',
          'redshift-serverless:GetCredentials',
          'redshift-serverless:GetWorkgroup',
        ],
        resources: [
          `arn:aws:redshift-serverless:${this.region}:${this.account}:workgroup/*`,
        ],
      }),
    );
    getClientList.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'redshift-data:DescribeStatement',
          'redshift-data:GetStatementResult',
        ],
        resources: ['*'],
      }),
    );
    getClientList.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'lakeformation:GetDataAccess',
          'glue:GetTable',
          'glue:GetTables',
          'glue:GetDatabase',
          'glue:GetDatabases',
          'glue:GetCatalog',
        ],
        resources: ['*'],
      }),
    );

    const generateReport = new SchedulerToolsGenerateReport(
      this,
      'GenerateReport',
    );

    generateReport.addEnvironment(
      'REPORT_AGENT_ARN',
      reportAgent.agentCoreRuntime.agentRuntimeArn,
    );
    generateReport.addEnvironment('POWERTOOLS_SERVICE_NAME', 'scheduler-tools');
    generateReport.addEnvironment('LOG_LEVEL', 'INFO');

    reportAgent.agentCoreRuntime.grantInvoke(generateReport);

    const reportScheduler = new ReportSchedulerStateMachine(
      this,
      'ReportScheduler',
      {
        getClientListFunction: getClientList,
        generateReportFunction: generateReport,
      },
    );

    // Theme Generation Scheduler
    const generateGeneralThemes = new ThemeSchedulerGenerateGeneralThemes(
      this,
      'GenerateGeneralThemes',
      {
        redshiftWorkgroup: redshiftWorkgroup,
        redshiftDatabase: redshiftDatabase,
        webCrawlerMcpArn: webCrawlerMcp.agentCoreRuntime.agentRuntimeArn,
      },
    );

    generateGeneralThemes.addEnvironment(
      'POWERTOOLS_SERVICE_NAME',
      'theme-scheduler-tools',
    );
    generateGeneralThemes.addEnvironment('LOG_LEVEL', 'INFO');

    // Grant Lambda permission to invoke Web Crawler MCP
    webCrawlerMcp.agentCoreRuntime.grantInvoke(generateGeneralThemes);

    // Redshift, Lake Formation, and Bedrock permissions for theme generation
    generateGeneralThemes.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'redshift-data:ExecuteStatement',
          'redshift-serverless:GetCredentials',
          'redshift-serverless:GetWorkgroup',
        ],
        resources: [
          `arn:aws:redshift-serverless:${this.region}:${this.account}:workgroup/*`,
        ],
      }),
    );
    generateGeneralThemes.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'redshift-data:DescribeStatement',
          'redshift-data:GetStatementResult',
        ],
        resources: ['*'],
      }),
    );
    generateGeneralThemes.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'lakeformation:GetDataAccess',
          'glue:GetTable',
          'glue:GetTables',
          'glue:GetDatabase',
          'glue:GetDatabases',
          'glue:GetCatalog',
        ],
        resources: ['*'],
      }),
    );
    generateGeneralThemes.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );

    const generatePortfolioThemes = new ThemeSchedulerGeneratePortfolioThemes(
      this,
      'GeneratePortfolioThemes',
      {
        redshiftWorkgroup: redshiftWorkgroup,
        redshiftDatabase: redshiftDatabase,
        webCrawlerMcpArn: webCrawlerMcp.agentCoreRuntime.agentRuntimeArn,
      },
    );

    generatePortfolioThemes.addEnvironment(
      'POWERTOOLS_SERVICE_NAME',
      'theme-scheduler-tools',
    );
    generatePortfolioThemes.addEnvironment('LOG_LEVEL', 'INFO');

    // Grant Lambda permission to invoke Web Crawler MCP
    webCrawlerMcp.agentCoreRuntime.grantInvoke(generatePortfolioThemes);

    // Redshift, Lake Formation, and Bedrock permissions for theme generation
    generatePortfolioThemes.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'redshift-data:ExecuteStatement',
          'redshift-serverless:GetCredentials',
          'redshift-serverless:GetWorkgroup',
        ],
        resources: [
          `arn:aws:redshift-serverless:${this.region}:${this.account}:workgroup/*`,
        ],
      }),
    );
    generatePortfolioThemes.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'redshift-data:DescribeStatement',
          'redshift-data:GetStatementResult',
        ],
        resources: ['*'],
      }),
    );
    generatePortfolioThemes.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'lakeformation:GetDataAccess',
          'glue:GetTable',
          'glue:GetTables',
          'glue:GetDatabase',
          'glue:GetDatabases',
          'glue:GetCatalog',
        ],
        resources: ['*'],
      }),
    );
    generatePortfolioThemes.role?.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: [
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
        ],
      }),
    );

    const themeScheduler = new ThemeGeneratorStateMachine(
      this,
      'ThemeScheduler',
      {
        generateGeneralThemesFunction: generateGeneralThemes,
        getClientListFunction: getClientList,
        generatePortfolioThemesFunction: generatePortfolioThemes,
      },
    );

    // IAM role for EventBridge Scheduler to start state machine executions
    const schedulerRole = new Role(this, 'ReportScheduleRole', {
      assumedBy: new ServicePrincipal('scheduler.amazonaws.com'),
    });
    reportScheduler.stateMachine.grantStartExecution(schedulerRole);
    themeScheduler.stateMachine.grantStartExecution(schedulerRole);

    // Daily report generation schedule (2 AM UTC) — currently disabled
    new CfnSchedule(this, 'ReportSchedule', {
      scheduleExpression: 'cron(0 2 * * ? *)',
      description: 'Trigger daily report generation at 2 AM UTC',
      state: 'DISABLED',
      flexibleTimeWindow: { mode: 'OFF' },
      target: {
        arn: reportScheduler.stateMachine.stateMachineArn,
        roleArn: schedulerRole.roleArn,
      },
    });

    // Daily theme generation schedule (2 AM UTC) — currently disabled
    new CfnSchedule(this, 'ThemeSchedule', {
      scheduleExpression: 'cron(0 2 * * ? *)',
      description: 'Trigger daily theme generation at 2 AM UTC',
      state: 'DISABLED',
      flexibleTimeWindow: { mode: 'OFF' },
      target: {
        arn: themeScheduler.stateMachine.stateMachineArn,
        roleArn: schedulerRole.roleArn,
      },
    });
  }
}
