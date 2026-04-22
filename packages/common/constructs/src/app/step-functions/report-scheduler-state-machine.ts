import * as cdk from 'aws-cdk-lib';
import { Duration } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Construct } from 'constructs';

export interface ReportSchedulerStateMachineProps {
  getClientListFunction: lambda.IFunction;
  generateReportFunction: lambda.IFunction;
}

export class ReportSchedulerStateMachine extends Construct {
  public readonly stateMachine: sfn.StateMachine;

  constructor(
    scope: Construct,
    id: string,
    props: ReportSchedulerStateMachineProps,
  ) {
    super(scope, id);

    const logsKey = new kms.Key(this, 'LogsKey', {
      description: 'KMS key for Step Functions logs encryption',
      enableKeyRotation: true,
    });

    // CloudWatch Logs requires explicit permission to use the KMS key
    logsKey.addToResourcePolicy(
      new iam.PolicyStatement({
        actions: [
          'kms:Encrypt*',
          'kms:Decrypt*',
          'kms:ReEncrypt*',
          'kms:GenerateDataKey*',
          'kms:Describe*',
        ],
        principals: [
          new iam.ServicePrincipal(
            `logs.${cdk.Stack.of(this).region}.amazonaws.com`,
          ),
        ],
        resources: ['*'],
      }),
    );

    const logGroup = new logs.LogGroup(this, 'SchedulerLogs', {
      retention: logs.RetentionDays.ONE_MONTH,
      encryptionKey: logsKey,
    });

    // Fetch all client IDs from Redshift (split into test + remaining)
    const getClientList = new tasks.LambdaInvoke(this, 'GetClientList', {
      lambdaFunction: props.getClientListFunction,
      resultSelector: {
        'test_client_ids.$': '$.Payload.test_client_ids',
        'remaining_client_ids.$': '$.Payload.remaining_client_ids',
      },
      resultPath: '$.clientListResult',
    });

    getClientList.addRetry({
      errors: ['States.TaskFailed'],
      interval: Duration.seconds(2),
      maxAttempts: 2,
      backoffRate: 2.0,
    });

    // Terminal states
    const noClients = new sfn.Succeed(this, 'NoClients');
    const success = new sfn.Succeed(this, 'Success');
    const handleError = new sfn.Fail(this, 'HandleError', {
      error: 'ReportSchedulerError',
      cause: 'Failed to get client list',
    });
    const canaryFailed = new sfn.Fail(this, 'CanaryFailed', {
      error: 'CanaryTestFailed',
      causePath: '$.canaryError.Cause',
    });

    // --- Canary phase: test batch (sequential, fail-fast) ---
    // Uses a separate LambdaInvoke with NO catch — any failure stops execution
    const generateTestReport = new tasks.LambdaInvoke(
      this,
      'GenerateTestReport',
      {
        lambdaFunction: props.generateReportFunction,
        payloadResponseOnly: true,
      },
    );

    generateTestReport.addRetry({
      errors: ['States.TaskFailed'],
      interval: Duration.seconds(30),
      maxAttempts: 2,
      backoffRate: 2.0,
    });

    const testBatchMap = new sfn.Map(this, 'TestBatchMap', {
      maxConcurrency: 1,
      itemsPath: '$.clientListResult.test_client_ids',
      // Transform each string item into { client_id: "CLT-001" } for the Lambda
      itemSelector: {
        'client_id.$': '$$.Map.Item.Value',
      },
      resultPath: '$.testResults',
    });

    testBatchMap.itemProcessor(generateTestReport);

    // If any test report fails, abort the entire run
    testBatchMap.addCatch(canaryFailed, {
      errors: ['States.ALL'],
      resultPath: '$.canaryError',
    });

    // --- Full batch: remaining clients (parallel, fault-tolerant) ---
    const generateReport = new tasks.LambdaInvoke(this, 'GenerateReport', {
      lambdaFunction: props.generateReportFunction,
      payloadResponseOnly: true,
    });

    generateReport.addRetry({
      errors: ['States.TaskFailed'],
      interval: Duration.seconds(30),
      maxAttempts: 2,
      backoffRate: 2.0,
    });

    // Individual failures in full batch are logged but don't stop execution
    const reportFailed = new sfn.Pass(this, 'ReportFailed');

    generateReport.addCatch(reportFailed, {
      errors: ['States.ALL'],
      resultPath: '$.error',
    });

    const fullBatchMap = new sfn.Map(this, 'FullBatchMap', {
      maxConcurrency: 10,
      itemsPath: '$.clientListResult.remaining_client_ids',
      itemSelector: {
        'client_id.$': '$$.Map.Item.Value',
      },
      resultPath: '$.reports',
    });

    fullBatchMap.itemProcessor(generateReport);
    fullBatchMap.next(success);

    // --- Workflow wiring ---

    // After canary passes, check if there are remaining clients
    const checkRemainingClients = new sfn.Choice(this, 'CheckRemainingClients')
      .when(
        sfn.Condition.isPresent('$.clientListResult.remaining_client_ids[0]'),
        fullBatchMap,
      )
      .otherwise(success);

    testBatchMap.next(checkRemainingClients);

    // Skip everything if no clients at all
    const checkClientCount = new sfn.Choice(this, 'CheckClientCount')
      .when(
        sfn.Condition.isPresent('$.clientListResult.test_client_ids[0]'),
        testBatchMap,
      )
      .otherwise(noClients);

    getClientList.addCatch(handleError, {
      errors: ['States.ALL'],
      resultPath: '$.error',
    });

    // Entry: get clients → check count → canary → full batch
    const definition = getClientList.next(checkClientCount);

    this.stateMachine = new sfn.StateMachine(this, 'StateMachine', {
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      timeout: Duration.hours(2),
      logs: {
        destination: logGroup,
        level: sfn.LogLevel.ALL,
      },
    });
  }
}
