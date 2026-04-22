import { Duration, Stack } from 'aws-cdk-lib';
import {
  Architecture,
  Code,
  Function,
  Runtime,
  Tracing,
} from 'aws-cdk-lib/aws-lambda';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';
import * as url from 'url';
import {
  Gateway,
  GatewayAuthorizer,
  GatewayExceptionLevel,
  ToolSchema,
} from '@aws-cdk/aws-bedrock-agentcore-alpha';

export interface NeptuneAnalyticsGatewayProps {
  neptuneGraphId: string;
}

export class NeptuneAnalyticsGateway extends Construct {
  public readonly gateway: Gateway;
  public readonly lambdaFunction: Function;

  constructor(
    scope: Construct,
    id: string,
    props: NeptuneAnalyticsGatewayProps,
  ) {
    super(scope, id);

    this.lambdaFunction = new Function(this, 'Handler', {
      runtime: Runtime.PYTHON_3_12,
      architecture: Architecture.ARM_64,
      handler:
        'wealth_management_portal_neptune_analytics_server.lambda_functions.neptune_analytics_gateway.lambda_handler',
      code: Code.fromAsset(
        url.fileURLToPath(
          new URL(
            '../../../../../../../dist/packages/neptune_analytics_server/bundle-arm',
            import.meta.url,
          ),
        ),
      ),
      timeout: Duration.seconds(60),
      memorySize: 256,
      tracing: Tracing.ACTIVE,
      environment: {
        NEPTUNE_GRAPH_ID: props.neptuneGraphId,
      },
    });

    this.lambdaFunction.addToRolePolicy(
      new PolicyStatement({
        actions: [
          'neptune-graph:ExecuteQuery',
          'neptune-graph:ReadDataViaQuery',
          'neptune-graph:WriteDataViaQuery',
          'neptune-graph:DeleteDataViaQuery',
          'neptune-graph:GetGraph',
        ],
        resources: [
          `arn:aws:neptune-graph:${Stack.of(this).region}:${Stack.of(this).account}:graph/*`,
        ],
      }),
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
