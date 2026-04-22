import { Construct } from 'constructs';
import * as url from 'url';
import { Code, Function, Runtime, Tracing } from 'aws-cdk-lib/aws-lambda';
import { Duration } from 'aws-cdk-lib';

export class SchedulerMcpSchedulerGateway extends Function {
  constructor(scope: Construct, id: string) {
    super(scope, id, {
      timeout: Duration.seconds(30),
      runtime: Runtime.PYTHON_3_12,
      handler:
        'wealth_management_portal_scheduler_mcp.lambda_functions.scheduler_gateway.lambda_handler',
      code: Code.fromAsset(
        url.fileURLToPath(
          new URL(
            '../../../../../../dist/packages/scheduler_mcp/bundle-x86',
            import.meta.url,
          ),
        ),
      ),
      tracing: Tracing.ACTIVE,
      environment: {
        AWS_CONNECTION_REUSE_ENABLED: '1',
      },
    });
  }
}
