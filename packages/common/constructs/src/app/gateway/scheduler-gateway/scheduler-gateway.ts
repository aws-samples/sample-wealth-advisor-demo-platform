import { CfnResource, Stack } from 'aws-cdk-lib';
import { Table } from 'aws-cdk-lib/aws-dynamodb';
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
import { SchedulerMcpSchedulerGateway } from '../../lambda-functions/scheduler-mcp-scheduler-gateway.js';
import { suppressRules } from '../../../core/checkov.js';

export interface SchedulerGatewayProps {
  schedulesTable: Table;
  scheduleResultsTable: Table;
  executorLambdaArn: string;
  eventBridgeRoleArn: string;
}

export class SchedulerGateway extends Construct {
  public readonly gateway: Gateway;
  public readonly lambdaFunction: Function;

  constructor(scope: Construct, id: string, props: SchedulerGatewayProps) {
    super(scope, id);

    const {
      schedulesTable,
      scheduleResultsTable,
      executorLambdaArn,
      eventBridgeRoleArn,
    } = props;

    this.lambdaFunction = new SchedulerMcpSchedulerGateway(this, 'Handler');
    this.lambdaFunction.addEnvironment(
      'SCHEDULES_TABLE_NAME',
      schedulesTable.tableName,
    );
    this.lambdaFunction.addEnvironment(
      'SCHEDULE_RESULTS_TABLE_NAME',
      scheduleResultsTable.tableName,
    );
    this.lambdaFunction.addEnvironment(
      'EXECUTOR_LAMBDA_ARN',
      executorLambdaArn,
    );
    this.lambdaFunction.addEnvironment(
      'EVENTBRIDGE_ROLE_ARN',
      eventBridgeRoleArn,
    );
    this.lambdaFunction.addEnvironment(
      'AWS_REGION_NAME',
      Stack.of(this).region,
    );

    // Grant DynamoDB + KMS permissions via CDK grant methods
    schedulesTable.grantReadWriteData(this.lambdaFunction);
    scheduleResultsTable.grantReadWriteData(this.lambdaFunction);

    this.lambdaFunction.addToRolePolicy(
      new PolicyStatement({
        actions: [
          'scheduler:CreateSchedule',
          'scheduler:DeleteSchedule',
          'scheduler:UpdateSchedule',
          'scheduler:GetSchedule',
        ],
        resources: ['*'],
      }),
    );

    this.lambdaFunction.addToRolePolicy(
      new PolicyStatement({
        actions: ['iam:PassRole'],
        resources: [eventBridgeRoleArn],
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

    // EventBridge Scheduler actions require wildcard resources
    suppressRules(
      this.lambdaFunction,
      ['CKV_AWS_111'],
      'EventBridge Scheduler API does not support resource-level permissions',
      (c: IConstruct) =>
        CfnResource.isCfnResource(c) &&
        c.cfnResourceType === 'AWS::IAM::Policy',
    );
  }
}
