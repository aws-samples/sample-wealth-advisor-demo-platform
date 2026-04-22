import { CfnResource, Stack } from 'aws-cdk-lib';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Function } from 'aws-cdk-lib/aws-lambda';
import {
  Gateway,
  GatewayAuthorizer,
  GatewayExceptionLevel,
  ToolSchema,
} from '@aws-cdk/aws-bedrock-agentcore-alpha';
import { Construct, IConstruct } from 'constructs';
import * as path from 'path';
import * as url from 'url';
import { EmailSenderMcpEmailSenderGateway } from '../../lambda-functions/email-sender-mcp-email-sender-gateway.js';
import { suppressRules } from '../../../core/checkov.js';

export interface EmailSenderGatewayProps {
  senderEmail: string;
  reportBucketName?: string;
}

export class EmailSenderGateway extends Construct {
  public readonly gateway: Gateway;
  public readonly lambdaFunction: Function;

  constructor(scope: Construct, id: string, props: EmailSenderGatewayProps) {
    super(scope, id);

    this.lambdaFunction = new EmailSenderMcpEmailSenderGateway(this, 'Handler');
    this.lambdaFunction.addEnvironment(
      'AWS_REGION_NAME',
      Stack.of(this).region,
    );
    this.lambdaFunction.addEnvironment('SES_SENDER_EMAIL', props.senderEmail);

    if (props.reportBucketName) {
      this.lambdaFunction.addEnvironment(
        'REPORT_BUCKET_NAME',
        props.reportBucketName,
      );
    }

    this.lambdaFunction.addToRolePolicy(
      new PolicyStatement({
        actions: ['ses:SendEmail', 'ses:SendRawEmail'],
        resources: ['*'],
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

    // SES actions require wildcard resources when not scoped to specific identities
    suppressRules(
      this.lambdaFunction,
      ['CKV_AWS_111'],
      'SES SendEmail/SendRawEmail require wildcard resources',
      (c: IConstruct) =>
        CfnResource.isCfnResource(c) &&
        c.cfnResourceType === 'AWS::IAM::Policy',
    );
  }
}
