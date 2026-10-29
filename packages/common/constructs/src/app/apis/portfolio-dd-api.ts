import { Construct } from 'constructs';
import * as url from 'url';
import { Distribution } from 'aws-cdk-lib/aws-cloudfront';
import {
  Code,
  Runtime as LambdaRuntime,
  Function,
  Tracing,
} from 'aws-cdk-lib/aws-lambda';
import {
  AccessLogFormat,
  AuthorizationType,
  CognitoUserPoolsAuthorizer,
  Cors,
  LambdaRestApi,
  LogGroupLogDestination,
  ResponseType,
} from 'aws-cdk-lib/aws-apigateway';
import { Duration, Stack } from 'aws-cdk-lib';
import { Key } from 'aws-cdk-lib/aws-kms';
import { LogGroup, RetentionDays } from 'aws-cdk-lib/aws-logs';
import { IUserPool } from 'aws-cdk-lib/aws-cognito';
import { ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { suppressRules } from '../../core/checkov.js';

export interface PortfolioDdApiProps {
  identity: {
    userPool: IUserPool;
  };
  handler: Function;
}

/**
 * Portfolio DD API — a Lambda-backed REST API using proxy integration.
 * The handler Lambda must be created OUTSIDE this construct to avoid
 * circular dependencies between API Gateway and Lambda IAM policies.
 */
export class PortfolioDdApi extends Construct {
  public readonly api: LambdaRestApi;
  public readonly handler: Function;

  public static createHandler(scope: Construct): Function {
    return new Function(scope, 'PortfolioDdApiHandler', {
      runtime: LambdaRuntime.PYTHON_3_12,
      handler: 'wealth_management_portal_due_diligence.api.main.handler',
      code: Code.fromAsset(
        url.fileURLToPath(
          new URL(
            '../../../../../../dist/packages/due_diligence/bundle-x86',
            import.meta.url,
          ),
        ),
      ),
      timeout: Duration.seconds(300),
      tracing: Tracing.ACTIVE,
      memorySize: 512,
      environment: {
        AWS_CONNECTION_REUSE_ENABLED: '1',
      },
    });
  }

  constructor(scope: Construct, id: string, props: PortfolioDdApiProps) {
    super(scope, id);

    this.handler = props.handler;

    const authorizer = new CognitoUserPoolsAuthorizer(this, 'Authorizer', {
      cognitoUserPools: [props.identity.userPool],
    });

    const accessLogKey = new Key(this, 'AccessLogKey', {
      enableKeyRotation: true,
    });
    accessLogKey.grantEncryptDecrypt(
      new ServicePrincipal(`logs.${Stack.of(this).region}.amazonaws.com`),
    );
    const accessLogGroup = new LogGroup(this, 'AccessLogGroup', {
      retention: RetentionDays.ONE_WEEK,
      encryptionKey: accessLogKey,
    });

    this.api = new LambdaRestApi(this, 'Api', {
      handler: this.handler,
      proxy: true,
      defaultMethodOptions: {
        authorizationType: AuthorizationType.COGNITO,
        authorizer,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: Cors.ALL_ORIGINS,
        allowMethods: Cors.ALL_METHODS,
        allowHeaders: Cors.DEFAULT_HEADERS.concat(['x-amzn-trace-id']),
      },
      deployOptions: {
        tracingEnabled: true,
        accessLogDestination: new LogGroupLogDestination(accessLogGroup),
        accessLogFormat: AccessLogFormat.jsonWithStandardFields(),
        throttlingBurstLimit: 100,
        throttlingRateLimit: 50,
      },
    });

    suppressRules(
      this.api.deploymentStage,
      ['CKV_AWS_120'],
      'Personalized DD responses must not be served from a shared API Gateway cache; caching is handled at the application layer when appropriate.',
    );

    for (const [suffix, type] of [
      ['4xx', ResponseType.DEFAULT_4XX],
      ['5xx', ResponseType.DEFAULT_5XX],
    ] as const) {
      this.api.addGatewayResponse(`${suffix}`, {
        type,
        responseHeaders: {
          'Access-Control-Allow-Origin': "'*'",
          'Access-Control-Allow-Headers': "'*'",
        },
      });
    }
  }

  public restrictCorsTo(
    ...websites: { cloudFrontDistribution: Distribution }[]
  ) {
    const allowedOrigins = websites
      .map(
        ({ cloudFrontDistribution }) =>
          `https://${cloudFrontDistribution.distributionDomainName}`,
      )
      .join(',');
    this.handler.addEnvironment('ALLOWED_ORIGINS', allowedOrigins);
  }
}
