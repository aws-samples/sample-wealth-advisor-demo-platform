import { CfnResource, Duration, Stack } from 'aws-cdk-lib';
import {
  Architecture,
  Code,
  Function,
  Runtime,
  Tracing,
} from 'aws-cdk-lib/aws-lambda';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';
import {
  Vpc,
  SecurityGroup,
  Port,
  Subnet,
  InterfaceVpcEndpoint,
  InterfaceVpcEndpointAwsService,
} from 'aws-cdk-lib/aws-ec2';
import { Construct, IConstruct } from 'constructs';
import * as path from 'path';
import * as url from 'url';
import {
  Gateway,
  GatewayAuthorizer,
  GatewayExceptionLevel,
  ToolSchema,
} from '@aws-cdk/aws-bedrock-agentcore-alpha';
import { suppressRules } from '../../../core/checkov.js';

export interface PortfolioDataGatewayProps {
  vpcId: string;
  privateSubnetIds: string[];
  privateRouteTableId: string;
  redshiftSecurityGroupId: string;
  redshiftWorkgroup: string;
  redshiftDatabase: string;
}

export class PortfolioDataGateway extends Construct {
  public readonly gateway: Gateway;
  public readonly lambdaFunction: Function;
  public readonly mcpSecurityGroup: SecurityGroup;
  public readonly vpcEndpointSecurityGroup: SecurityGroup;

  constructor(scope: Construct, id: string, props: PortfolioDataGatewayProps) {
    super(scope, id);

    const {
      vpcId,
      privateSubnetIds,
      privateRouteTableId,
      redshiftSecurityGroupId,
      redshiftWorkgroup,
      redshiftDatabase,
    } = props;

    // Import VPC and subnets
    const vpc = Vpc.fromLookup(this, 'Vpc', { vpcId });
    const privateSubnets = privateSubnetIds.map((subnetId, index) =>
      Subnet.fromSubnetAttributes(this, `PrivateSubnet${index + 1}`, {
        subnetId,
        routeTableId: privateRouteTableId,
      }),
    );

    // Create VPC endpoint security group
    this.vpcEndpointSecurityGroup = new SecurityGroup(this, 'VpcEndpointSg', {
      vpc,
      allowAllOutbound: false,
    });

    // Create MCP security group
    this.mcpSecurityGroup = new SecurityGroup(this, 'McpSg', {
      vpc,
      allowAllOutbound: false,
    });

    // Configure security group rules
    this.mcpSecurityGroup.addEgressRule(
      this.vpcEndpointSecurityGroup,
      Port.tcp(443),
    );
    const redshiftSg = SecurityGroup.fromSecurityGroupId(
      this,
      'RedshiftSg',
      redshiftSecurityGroupId,
    );
    this.mcpSecurityGroup.addEgressRule(redshiftSg, Port.tcp(5439));
    this.vpcEndpointSecurityGroup.addIngressRule(
      this.mcpSecurityGroup,
      Port.tcp(443),
    );
    // Allow Lambda to connect to Redshift on port 5439
    redshiftSg.addIngressRule(
      this.mcpSecurityGroup,
      Port.tcp(5439),
      'Portfolio Gateway Lambda access',
    );

    // VPC Endpoints — VPC-level resources, created only by the primary (sandbox) stage.
    // Other stages sharing the same VPC reuse the existing ones.
    const stageName = this.node.tryGetContext('stageName') ?? 'sandbox';
    if (stageName === 'sandbox') {
      new InterfaceVpcEndpoint(this, 'StsEndpoint', {
        vpc,
        service: InterfaceVpcEndpointAwsService.STS,
        subnets: { subnets: privateSubnets },
        securityGroups: [this.vpcEndpointSecurityGroup],
        privateDnsEnabled: true,
      });

      new InterfaceVpcEndpoint(this, 'RedshiftServerlessEndpoint', {
        vpc,
        service: new InterfaceVpcEndpointAwsService('redshift-serverless'),
        subnets: { subnets: privateSubnets },
        securityGroups: [this.vpcEndpointSecurityGroup],
        privateDnsEnabled: true,
      });

      // Note: CloudWatch Logs interface endpoint already created by the data-platform stack (Phase 1).
    }

    // Lambda function
    const environmentVariables = {
      REDSHIFT_WORKGROUP: redshiftWorkgroup,
      REDSHIFT_DATABASE: redshiftDatabase,
      REDSHIFT_REGION: Stack.of(this).region,
      AWS_ACCOUNT_ID: Stack.of(this).account,
      AWS_CONNECTION_REUSE_ENABLED: '1',
    };

    this.lambdaFunction = new Function(this, 'Handler', {
      runtime: Runtime.PYTHON_3_12,
      architecture: Architecture.ARM_64,
      handler:
        'wealth_management_portal_portfolio_data_server.lambda_functions.portfolio_data_gateway.lambda_handler',
      code: Code.fromAsset(
        url.fileURLToPath(
          new URL(
            '../../../../../../../dist/packages/portfolio_data_server/bundle-arm',
            import.meta.url,
          ),
        ),
      ),
      timeout: Duration.seconds(180),
      memorySize: 512,
      tracing: Tracing.ACTIVE,
      environment: environmentVariables,
      vpc,
      vpcSubnets: { subnets: privateSubnets },
      securityGroups: [this.mcpSecurityGroup],
    });

    // Redshift IAM permissions
    this.lambdaFunction.addToRolePolicy(
      new PolicyStatement({
        actions: [
          'redshift-serverless:GetCredentials',
          'redshift-serverless:GetWorkgroup',
          'redshift-data:ExecuteStatement',
          'redshift-data:GetStatementResult',
          'redshift-data:DescribeStatement',
        ],
        resources: ['*'],
      }),
    );

    // Required for Redshift to resolve federated S3 Tables catalog views via Lake Formation
    this.lambdaFunction.addToRolePolicy(
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

    // Suppress checkov rules for wildcard Redshift resources
    suppressRules(
      this.lambdaFunction,
      ['CKV_AWS_107', 'CKV_AWS_111'],
      'Lambda requires wildcard resources for Redshift serverless operations',
      (c: IConstruct) =>
        CfnResource.isCfnResource(c) &&
        c.cfnResourceType === 'AWS::IAM::Policy',
    );

    // AgentCore Gateway
    this.gateway = new Gateway(this, 'Gateway', {
      authorizerConfiguration: GatewayAuthorizer.usingAwsIam(),
      exceptionLevel: GatewayExceptionLevel.DEBUG,
    });
    this.gateway.addLambdaTarget('LambdaTarget', {
      lambdaFunction: this.lambdaFunction,
      toolSchema: ToolSchema.fromLocalAsset(
        path.join(
          path.dirname(url.fileURLToPath(import.meta.url)),
          'tool-schema.json',
        ),
      ),
    });
  }
}
