import { Construct } from 'constructs';
import * as url from 'url';
import { Code, Function, Runtime, Tracing } from 'aws-cdk-lib/aws-lambda';
import { Duration } from 'aws-cdk-lib';

export class SchedulerExecutorScheduleExecutor extends Function {
  constructor(scope: Construct, id: string) {
    super(scope, id, {
      timeout: Duration.minutes(10),
      runtime: Runtime.PYTHON_3_12,
      handler:
        'wealth_management_portal_scheduler_executor.lambda_functions.schedule_executor.lambda_handler',
      code: Code.fromAsset(
        url.fileURLToPath(
          new URL(
            '../../../../../../dist/packages/scheduler_executor/bundle-x86',
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
