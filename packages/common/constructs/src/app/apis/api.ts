import { Construct } from 'constructs';
import * as url from 'url';
import { Distribution } from 'aws-cdk-lib/aws-cloudfront';
import { Code, Runtime, Function, Tracing } from 'aws-cdk-lib/aws-lambda';
import {
  AuthorizationType,
  Cors,
  LambdaIntegration,
  CognitoUserPoolsAuthorizer,
} from 'aws-cdk-lib/aws-apigateway';
import { Duration, Stack } from 'aws-cdk-lib';
import {
  PolicyDocument,
  PolicyStatement,
  Effect,
  AnyPrincipal,
} from 'aws-cdk-lib/aws-iam';
import { IUserPool } from 'aws-cdk-lib/aws-cognito';
import {
  IVpc,
  SecurityGroup,
  ISubnet,
  Port,
  InterfaceVpcEndpoint,
  InterfaceVpcEndpointAwsService,
  InterfaceVpcEndpointService,
  Vpc,
  Subnet,
} from 'aws-cdk-lib/aws-ec2';
import {
  IntegrationBuilder,
  RestApiIntegration,
} from '../../core/api/utils.js';
import { RestApi } from '../../core/api/rest-api.js';
import {
  OPERATION_DETAILS,
  Operations,
} from '../../generated/api/metadata.gen.js';

/**
 * Properties for creating a Api construct
 *
 * @template TIntegrations - Map of operation names to their integrations
 */
export interface ApiProps<
  TIntegrations extends Record<Operations, RestApiIntegration>,
> {
  /**
   * Map of operation names to their API Gateway integrations
   */
  integrations: TIntegrations;
  /**
   * Identity details for Cognito Authentication
   */
  identity: {
    userPool: IUserPool;
  };
  /**
   * VPC configuration for Lambda placement
   */
  vpcId?: string;
  privateSubnetIds?: string[];
  redshiftSecurityGroupId?: string;
}

/**
 * A CDK construct that creates and configures an AWS API Gateway REST API
 * specifically for Api.
 * @template TIntegrations - Map of operation names to their integrations
 */
export class Api<
  TIntegrations extends Record<Operations, RestApiIntegration>,
> extends RestApi<Operations, TIntegrations> {
  private static _lambdaSecurityGroup: SecurityGroup | undefined;

  public readonly lambdaSecurityGroup?: SecurityGroup;

  /**
   * Creates default integrations for all operations, which implement all operations
   * using a single router lambda function.
   *
   * @param scope - The CDK construct scope
   * @param vpcConfig - Optional VPC configuration for Lambda placement
   * @returns An IntegrationBuilder with router lambda integration
   */
  public static defaultIntegrations = (
    scope: Construct,
    vpcConfig?: {
      vpcId: string;
      privateSubnetIds: string[];
      redshiftSecurityGroupId: string;
    },
  ) => {
    let vpcConfiguration:
      | {
          vpc: IVpc;
          vpcSubnets: { subnets: ISubnet[] };
        }
      | undefined = undefined;
    let securityGroups: SecurityGroup[] | undefined = undefined;

    if (vpcConfig) {
      // Import VPC and subnets
      const vpc = Vpc.fromLookup(scope, 'ApiVpc', { vpcId: vpcConfig.vpcId });
      const privateSubnets = vpcConfig.privateSubnetIds.map((subnetId, index) =>
        Subnet.fromSubnetId(scope, `ApiPrivateSubnet${index + 1}`, subnetId),
      );

      // Create security group for Lambda
      const lambdaSecurityGroup = new SecurityGroup(scope, 'ApiLambdaSg', {
        vpc,
        allowAllOutbound: false,
      });

      // Create VPC endpoint security group
      const vpcEndpointSecurityGroup = new SecurityGroup(
        scope,
        'ApiVpcEndpointSg',
        {
          vpc,
          allowAllOutbound: false,
        },
      );

      // Configure security group rules
      lambdaSecurityGroup.addEgressRule(
        vpcEndpointSecurityGroup,
        Port.tcp(443),
        'VPC endpoints access',
      );
      lambdaSecurityGroup.addEgressRule(
        SecurityGroup.fromSecurityGroupId(
          scope,
          'ApiRedshiftSg',
          vpcConfig.redshiftSecurityGroupId,
        ),
        Port.tcp(5439),
        'Redshift access',
      );
      vpcEndpointSecurityGroup.addIngressRule(
        lambdaSecurityGroup,
        Port.tcp(443),
        'Lambda access',
      );

      // Add ingress rule to Redshift security group
      const redshiftSg = SecurityGroup.fromSecurityGroupId(
        scope,
        'RedshiftSgForIngress',
        vpcConfig.redshiftSecurityGroupId,
      );
      redshiftSg.addIngressRule(
        lambdaSecurityGroup,
        Port.tcp(5439),
        'API Lambda access',
      );

      // VPC Endpoints — VPC-level resources, created only by the primary (sandbox) stage.
      // Other stages sharing the same VPC reuse the existing ones.
      // Note: S3 GatewayVpcEndpoint is already created by the data-platform stack (Phase 1).
      const stageName = scope.node.tryGetContext('stageName') ?? 'sandbox';
      if (stageName === 'sandbox') {
        new InterfaceVpcEndpoint(scope, 'ApiRedshiftDataEndpoint', {
          vpc,
          service: InterfaceVpcEndpointAwsService.REDSHIFT_DATA,
          subnets: { subnets: privateSubnets },
          securityGroups: [vpcEndpointSecurityGroup],
        });

        new InterfaceVpcEndpoint(scope, 'ApiBedrockAgentCoreEndpoint', {
          vpc,
          service: new InterfaceVpcEndpointService(
            `com.amazonaws.${Stack.of(scope).region}.bedrock-agentcore`,
          ),
          privateDnsEnabled: true,
          subnets: { subnets: privateSubnets },
          securityGroups: [vpcEndpointSecurityGroup],
        });
      }

      vpcConfiguration = {
        vpc,
        vpcSubnets: { subnets: privateSubnets },
      };
      securityGroups = [lambdaSecurityGroup];

      // Store the security group for later access
      Api._lambdaSecurityGroup = lambdaSecurityGroup;
    }

    // Single Lambda function serving all Core API routes (router pattern)
    const router = new Function(scope, 'ApiRouterHandler', {
      runtime: Runtime.PYTHON_3_12,
      handler: 'wealth_management_portal_api.main.handler',
      code: Code.fromAsset(
        url.fileURLToPath(
          new URL(
            '../../../../../../dist/packages/api/bundle-x86',
            import.meta.url,
          ),
        ),
      ),
      timeout: Duration.seconds(60),
      tracing: Tracing.ACTIVE,
      environment: {
        AWS_CONNECTION_REUSE_ENABLED: '1',
        AWS_ACCOUNT_ID: Stack.of(scope).account,
        REDSHIFT_WORKGROUP:
          scope.node.tryGetContext('redshiftWorkgroup') ??
          'financial-advisor-wg',
        REDSHIFT_DATABASE:
          scope.node.tryGetContext('redshiftDatabase') ??
          'financial-advisor-db',
      },
      ...(vpcConfiguration && { vpc: vpcConfiguration.vpc }),
      ...(vpcConfiguration && { vpcSubnets: vpcConfiguration.vpcSubnets }),
      ...(securityGroups && { securityGroups }),
    });

    return IntegrationBuilder.rest({
      operations: OPERATION_DETAILS,
      defaultIntegrationOptions: {},
      buildDefaultIntegration: (_op) => {
        return {
          handler: router,
          integration: new LambdaIntegration(router),
        };
      },
    });
  };

  constructor(scope: Construct, id: string, props: ApiProps<TIntegrations>) {
    super(scope, id, {
      apiName: 'Api',
      defaultMethodOptions: {
        authorizationType: AuthorizationType.COGNITO,
        authorizer: new CognitoUserPoolsAuthorizer(scope, 'ApiAuthorizer', {
          cognitoUserPools: [props.identity.userPool],
        }),
      },
      defaultCorsPreflightOptions: {
        allowOrigins: Cors.ALL_ORIGINS,
        allowMethods: Cors.ALL_METHODS,
      },
      deployOptions: {
        tracingEnabled: true,
        throttlingBurstLimit: 200,
        throttlingRateLimit: 100,
      },
      policy: new PolicyDocument({
        statements: [
          // Allow all callers to invoke the API in the resource policy, since auth is handled by Cognito
          new PolicyStatement({
            effect: Effect.ALLOW,
            principals: [new AnyPrincipal()],
            actions: ['execute-api:Invoke'],
            resources: ['execute-api:/*'],
          }),
        ],
      }),
      operations: OPERATION_DETAILS,
      integrations: props.integrations,
    });

    this.lambdaSecurityGroup = Api._lambdaSecurityGroup;
  }

  /**
   * Restricts CORS to the website CloudFront distribution domains
   *
   * Configures the CloudFront distribution domains as the only permitted CORS origins
   * (other than local host) in the AWS Lambda integrations
   *
   * Note that this restriction is not applied to preflight OPTIONS
   *
   * @param websites - The CloudFront distribution to grant CORS from
   */
  public restrictCorsTo(
    ...websites: { cloudFrontDistribution: Distribution }[]
  ) {
    const allowedOrigins = websites
      .map(
        ({ cloudFrontDistribution }) =>
          `https://${cloudFrontDistribution.distributionDomainName}`,
      )
      .join(',');

    // Set ALLOWED_ORIGINS environment variable for all Lambda integrations
    Object.values(this.integrations).forEach((integration) => {
      if ('handler' in integration && integration.handler instanceof Function) {
        integration.handler.addEnvironment('ALLOWED_ORIGINS', allowedOrigins);
      }
    });
  }
}
