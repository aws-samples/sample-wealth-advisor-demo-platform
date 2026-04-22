import { Construct } from 'constructs';
import * as url from 'url';
import { Code, Function, Runtime, Tracing } from 'aws-cdk-lib/aws-lambda';
import { Duration } from 'aws-cdk-lib';

export class EmailSenderMcpEmailSenderGateway extends Function {
  constructor(scope: Construct, id: string) {
    super(scope, id, {
      timeout: Duration.seconds(30),
      runtime: Runtime.PYTHON_3_12,
      handler:
        'wealth_management_portal_email_sender_mcp.lambda_functions.email_sender_gateway.lambda_handler',
      code: Code.fromAsset(
        url.fileURLToPath(
          new URL(
            '../../../../../../dist/packages/email_sender_mcp/bundle-x86',
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
