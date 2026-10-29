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

    // VPC Endpoints for Redshift Data API access from within VPC
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

    // Athena interface endpoint — required for the Athena data path (DATA_ENGINE=athena).
    // The Lambda talks to Athena only via the Athena API (StartQueryExecution /
    // GetQueryExecution / GetQueryResults); Athena reads Glue/S3 and writes results
    // server-side, so no Glue/S3 egress is needed from the Lambda. Without this,
    // the SG (allowAllOutbound=false, egress 443 only to the endpoint SG) has no
    // route to Athena and every query hangs until the Lambda times out.
    new InterfaceVpcEndpoint(this, 'AthenaEndpoint', {
      vpc,
      service: InterfaceVpcEndpointAwsService.ATHENA,
      subnets: { subnets: privateSubnets },
      securityGroups: [this.vpcEndpointSecurityGroup],
      privateDnsEnabled: true,
    });

    // Lambda function
    const environmentVariables = {
      DATA_ENGINE: 'athena',
      ATHENA_CATALOG: 's3tablescatalog/financial-advisor-s3table',
      ATHENA_DATABASE: 'financial_advisor',
      ATHENA_WORKGROUP: 's3tables',
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
      timeout: Duration.seconds(300),
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
          'glue:GetPartition',
          'glue:GetPartitions',
          // Iceberg writes (INSERT) commit by swapping the table metadata pointer,
          // which requires Glue table/partition write actions on the S3 Tables catalog.
          'glue:UpdateTable',
          'glue:CreateTable',
          'glue:BatchCreatePartition',
          'glue:CreatePartition',
          'glue:UpdatePartition',
          'glue:BatchGetPartition',
        ],
        resources: ['*'],
      }),
    );

    // Athena data path (DATA_ENGINE=athena): the Lambda runs queries via the Athena API
    // (StartQueryExecution / GetQueryExecution / GetQueryResults) and reads results back
    // through the API. Without these the query returns AccessDeniedException.
    this.lambdaFunction.addToRolePolicy(
      new PolicyStatement({
        actions: [
          'athena:StartQueryExecution',
          'athena:GetQueryExecution',
          'athena:GetQueryResults',
          'athena:StopQueryExecution',
          'athena:GetWorkGroup',
          'athena:GetDataCatalog',
        ],
        resources: ['*'],
      }),
    );

    // S3 access to the Athena query-results bucket (Athena writes/reads results here on
    // behalf of the calling role). Bucket name is <account>-<app>-<region>-athena-output.
    this.lambdaFunction.addToRolePolicy(
      new PolicyStatement({
        actions: [
          's3:GetBucketLocation',
          's3:GetObject',
          's3:PutObject',
          's3:ListBucket',
          's3:ListMultipartUploadParts',
          's3:AbortMultipartUpload',
        ],
        resources: [
          `arn:aws:s3:::${Stack.of(this).account}-*-athena-output`,
          `arn:aws:s3:::${Stack.of(this).account}-*-athena-output/*`,
        ],
      }),
    );

    // KMS access for SSE-KMS Athena query results (the results bucket is aws:kms
    // encrypted, so Athena needs the caller role to use the key when writing/reading
    // results). Gated by each key's key-policy; scoped here to the account/region.
    this.lambdaFunction.addToRolePolicy(
      new PolicyStatement({
        actions: [
          'kms:Decrypt',
          'kms:Encrypt',
          'kms:GenerateDataKey',
          'kms:ReEncrypt*',
          'kms:DescribeKey',
        ],
        resources: [
          `arn:aws:kms:${Stack.of(this).region}:${Stack.of(this).account}:key/*`,
        ],
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
