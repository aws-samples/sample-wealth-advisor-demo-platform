import { Construct } from 'constructs';
import * as url from 'url';
import { Code, Function, Runtime, Tracing } from 'aws-cdk-lib/aws-lambda';
import { Duration } from 'aws-cdk-lib';

export class SchedulerToolsGenerateReport extends Function {
  constructor(scope: Construct, id: string) {
    super(scope, id, {
      timeout: Duration.seconds(300),
      memorySize: 512,
      runtime: Runtime.PYTHON_3_12,
      handler:
        'wealth_management_portal_scheduler_tools.lambda_functions.generate_report.lambda_handler',
      code: Code.fromAsset(
        url.fileURLToPath(
          new URL(
            '../../../../../../dist/packages/scheduler-tools/scheduler_tools/bundle-x86',
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
