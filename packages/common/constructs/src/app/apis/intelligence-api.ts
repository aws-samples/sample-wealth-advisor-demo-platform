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
import { Duration } from 'aws-cdk-lib';
import {
  PolicyDocument,
  PolicyStatement,
  Effect,
  AnyPrincipal,
} from 'aws-cdk-lib/aws-iam';
import { IUserPool } from 'aws-cdk-lib/aws-cognito';
import {
  IntegrationBuilder,
  RestApiIntegration,
} from '../../core/api/utils.js';
import { RestApi } from '../../core/api/rest-api.js';
import {
  OPERATION_DETAILS,
  Operations,
} from '../../generated/intelligence-api/metadata.gen.js';

/**
 * Properties for creating a IntelligenceApi construct
 *
 * @template TIntegrations - Map of operation names to their integrations
 */
export interface IntelligenceApiProps<
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
}

/**
 * A CDK construct that creates and configures an AWS API Gateway REST API
 * specifically for IntelligenceApi.
 * @template TIntegrations - Map of operation names to their integrations
 */
export class IntelligenceApi<
  TIntegrations extends Record<Operations, RestApiIntegration>,
> extends RestApi<Operations, TIntegrations> {
  /**
   * Creates default integrations for all operations, which implement each operation as
   * its own individual lambda function.
   *
   * @param scope - The CDK construct scope
   * @returns An IntegrationBuilder with default lambda integrations
   */
  public static defaultIntegrations = (scope: Construct) => {
    // Single Lambda function serving all Intelligence API routes (router pattern)
    const router = new Function(scope, 'IntelligenceApiRouterHandler', {
      runtime: Runtime.PYTHON_3_12,
      handler: 'wealth_management_portal_intelligence_api.main.handler',
      code: Code.fromAsset(
        url.fileURLToPath(
          new URL(
            '../../../../../../dist/packages/intelligence_api/bundle-x86',
            import.meta.url,
          ),
        ),
      ),
      timeout: Duration.seconds(300),
      memorySize: 512,
      tracing: Tracing.ACTIVE,
      environment: {
        AWS_CONNECTION_REUSE_ENABLED: '1',
        REDSHIFT_WORKGROUP:
          scope.node.tryGetContext('redshiftWorkgroup') ??
          'financial-advisor-wg',
        REDSHIFT_DATABASE:
          scope.node.tryGetContext('redshiftDatabase') ??
          'financial-advisor-db',
      },
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

  constructor(
    scope: Construct,
    id: string,
    props: IntelligenceApiProps<TIntegrations>,
  ) {
    super(scope, id, {
      apiName: 'IntelligenceApi',
      defaultMethodOptions: {
        authorizationType: AuthorizationType.COGNITO,
        authorizer: new CognitoUserPoolsAuthorizer(
          scope,
          'IntelligenceApiAuthorizer',
          {
            cognitoUserPools: [props.identity.userPool],
          },
        ),
      },
      defaultCorsPreflightOptions: {
        allowOrigins: Cors.ALL_ORIGINS,
        allowMethods: Cors.ALL_METHODS,
        allowHeaders: [...Cors.DEFAULT_HEADERS, 'x-amzn-trace-id'],
      },
      deployOptions: {
        tracingEnabled: true,
        throttlingBurstLimit: 50,
        throttlingRateLimit: 25,
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
      ...props,
    });
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
