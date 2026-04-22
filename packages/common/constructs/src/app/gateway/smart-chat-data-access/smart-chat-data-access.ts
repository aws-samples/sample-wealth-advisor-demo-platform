import { CfnResource, Duration, Stack } from 'aws-cdk-lib';
import {
  Architecture,
  Code,
  Function,
  Runtime,
  Tracing,
} from 'aws-cdk-lib/aws-lambda';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { SecurityGroup, Subnet, Vpc } from 'aws-cdk-lib/aws-ec2';
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

export interface SmartChatDataAccessProps {
  vpcId: string;
  privateSubnetIds: string[];
  privateRouteTableId: string;
  /** Security group that allows egress to Redshift + VPC endpoints */
  mcpSecurityGroup: SecurityGroup;
  redshiftWorkgroup: string;
  redshiftDatabase: string;
}

export class SmartChatDataAccess extends Construct {
  public readonly gateway: Gateway;
  public readonly lambdaFunction: Function;

  constructor(scope: Construct, id: string, props: SmartChatDataAccessProps) {
    super(scope, id);

    const {
      vpcId,
      privateSubnetIds,
      privateRouteTableId,
      mcpSecurityGroup,
      redshiftWorkgroup,
      redshiftDatabase,
    } = props;

    const vpc = Vpc.fromLookup(this, 'Vpc', { vpcId });
    const privateSubnets = privateSubnetIds.map((subnetId, index) =>
      Subnet.fromSubnetAttributes(this, `PrivateSubnet${index + 1}`, {
        subnetId,
        routeTableId: privateRouteTableId,
      }),
    );

    this.lambdaFunction = new Function(this, 'Handler', {
      runtime: Runtime.PYTHON_3_12,
      architecture: Architecture.ARM_64,
      handler:
        'wealth_management_portal_portfolio_data_server.lambda_functions.smart_chat_data_access.lambda_handler',
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
      environment: {
        REDSHIFT_WORKGROUP: redshiftWorkgroup,
        REDSHIFT_DATABASE: redshiftDatabase,
        REDSHIFT_REGION: Stack.of(this).region,
        AWS_ACCOUNT_ID: Stack.of(this).account,
        AWS_CONNECTION_REUSE_ENABLED: '1',
      },
      vpc,
      vpcSubnets: { subnets: privateSubnets },
      securityGroups: [mcpSecurityGroup],
    });

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

    suppressRules(
      this.lambdaFunction,
      ['CKV_AWS_107', 'CKV_AWS_111'],
      'Lambda requires wildcard resources for Redshift serverless operations',
      (c: IConstruct) =>
        CfnResource.isCfnResource(c) &&
        c.cfnResourceType === 'AWS::IAM::Policy',
    );

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
