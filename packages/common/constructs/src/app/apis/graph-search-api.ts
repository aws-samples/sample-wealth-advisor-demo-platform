import { Construct } from 'constructs';
import * as url from 'url';
import { Distribution } from 'aws-cdk-lib/aws-cloudfront';
import {
  Code,
  Runtime,
  Function,
  FunctionProps,
  Tracing,
} from 'aws-cdk-lib/aws-lambda';
import {
  AuthorizationType,
  CognitoUserPoolsAuthorizer,
  Cors,
  LambdaIntegration,
  ResponseType,
} from 'aws-cdk-lib/aws-apigateway';
import { Duration } from 'aws-cdk-lib';
import {
  PolicyDocument,
  PolicyStatement,
  Effect,
  AnyPrincipal,
  IGrantable,
  Grant,
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
} from '../../generated/graph-search-api/metadata.gen.js';

/**
 * Properties for creating a GraphSearchApi construct
 *
 * @template TIntegrations - Map of operation names to their integrations
 */
export interface GraphSearchApiProps<
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
 * specifically for GraphSearchApi.
 * @template TIntegrations - Map of operation names to their integrations
 */
export class GraphSearchApi<
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
    return IntegrationBuilder.rest({
      operations: OPERATION_DETAILS,
      defaultIntegrationOptions: {
        runtime: Runtime.PYTHON_3_12,
        handler: 'wealth_management_portal_graph_search_api.main.handler',
        code: Code.fromAsset(
          url.fileURLToPath(
            new URL(
              '../../../../../../dist/packages/graph_search_api/bundle-x86',
              import.meta.url,
            ),
          ),
        ),
        timeout: Duration.seconds(30),
        tracing: Tracing.ACTIVE,
        memorySize: 512,
        environment: {
          AWS_CONNECTION_REUSE_ENABLED: '1',
        },
      } satisfies FunctionProps,
      buildDefaultIntegration: (op, props: FunctionProps) => {
        const handler = new Function(
          scope,
          `GraphSearchApi${op}Handler`,
          props,
        );
        return { handler, integration: new LambdaIntegration(handler) };
      },
    });
  };

  constructor(
    scope: Construct,
    id: string,
    props: GraphSearchApiProps<TIntegrations>,
  ) {
    super(scope, id, {
      apiName: 'GraphSearchApi',
      defaultMethodOptions: {
        authorizationType: AuthorizationType.COGNITO,
        authorizer: new CognitoUserPoolsAuthorizer(
          scope,
          'GraphSearchApiAuthorizer',
          {
            cognitoUserPools: [props.identity.userPool],
          },
        ),
      },
      defaultCorsPreflightOptions: {
        allowOrigins: Cors.ALL_ORIGINS,
        allowMethods: Cors.ALL_METHODS,
        allowHeaders: Cors.DEFAULT_HEADERS.concat(['x-amzn-trace-id']),
      },
      deployOptions: {
        tracingEnabled: true,
        throttlingBurstLimit: 100,
        throttlingRateLimit: 50,
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

    // Ensure 4xx/5xx responses from API Gateway include CORS headers
    for (const [suffix, type] of [
      ['4xx', ResponseType.DEFAULT_4XX],
      ['5xx', ResponseType.DEFAULT_5XX],
    ] as const) {
      this.api.addGatewayResponse(`GraphSearchApi${suffix}`, {
        type,
        responseHeaders: {
          'Access-Control-Allow-Origin': "'*'",
          'Access-Control-Allow-Headers': "'*'",
        },
      });
    }
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

  /**
   * Grants IAM permissions to invoke any method on this API.
   *
   * @param grantee - The IAM principal to grant permissions to
   */
  public grantInvokeAccess(grantee: IGrantable) {
    // Here we grant grantee permission to call the api.
    // Machine to machine fine-grained access can be defined here using more specific principals (eg roles or
    // users) and resources (eg which api paths may be invoked by which principal) if required.
    this.api.addToResourcePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        principals: [grantee.grantPrincipal],
        actions: ['execute-api:Invoke'],
        resources: ['execute-api:/*'],
      }),
    );

    Grant.addToPrincipal({
      grantee,
      actions: ['execute-api:Invoke'],
      resourceArns: [this.api.arnForExecuteApi('*', '/*', '*')],
    });
  }
}
