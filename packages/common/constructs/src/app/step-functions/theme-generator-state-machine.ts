import * as cdk from 'aws-cdk-lib';
import { Duration } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Construct } from 'constructs';

export interface ThemeGeneratorStateMachineProps {
  generateGeneralThemesFunction: lambda.IFunction;
  getClientListFunction: lambda.IFunction;
  generatePortfolioThemesFunction: lambda.IFunction;
}

export class ThemeGeneratorStateMachine extends Construct {
  public readonly stateMachine: sfn.StateMachine;

  constructor(
    scope: Construct,
    id: string,
    props: ThemeGeneratorStateMachineProps,
  ) {
    super(scope, id);

    const logsKey = new kms.Key(this, 'LogsKey', {
      description: 'KMS key for Theme Generator Step Functions logs encryption',
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

    const logGroup = new logs.LogGroup(this, 'ThemeGeneratorLogs', {
      retention: logs.RetentionDays.ONE_MONTH,
      encryptionKey: logsKey,
    });

    // Step 1: Generate General Market Themes (once per run)
    const generateGeneralThemes = new tasks.LambdaInvoke(
      this,
      'GenerateGeneralThemes',
      {
        lambdaFunction: props.generateGeneralThemesFunction,
        resultPath: '$.generalThemesResult',
      },
    );

    generateGeneralThemes.addRetry({
      errors: ['States.TaskFailed'],
      interval: Duration.seconds(30),
      maxAttempts: 2,
      backoffRate: 2.0,
    });

    // Step 2: Fetch all client IDs from Redshift (split into test + remaining)
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
      error: 'ThemeGeneratorError',
      cause: 'Failed to generate themes',
    });
    const canaryFailed = new sfn.Fail(this, 'CanaryFailed', {
      error: 'CanaryTestFailed',
      causePath: '$.canaryError.Cause',
    });

    // --- Canary phase: test batch (sequential, fail-fast) ---
    const generateTestPortfolioThemes = new tasks.LambdaInvoke(
      this,
      'GenerateTestPortfolioThemes',
      {
        lambdaFunction: props.generatePortfolioThemesFunction,
        payloadResponseOnly: true,
      },
    );

    generateTestPortfolioThemes.addRetry({
      errors: ['States.TaskFailed'],
      interval: Duration.seconds(30),
      maxAttempts: 2,
      backoffRate: 2.0,
    });

    const testBatchMap = new sfn.Map(this, 'TestBatchMap', {
      maxConcurrency: 1,
      itemsPath: '$.clientListResult.test_client_ids',
      itemSelector: {
        'client_id.$': '$$.Map.Item.Value',
      },
      resultPath: '$.testResults',
    });

    testBatchMap.itemProcessor(generateTestPortfolioThemes);

    // If any test portfolio theme fails, abort the entire run
    testBatchMap.addCatch(canaryFailed, {
      errors: ['States.ALL'],
      resultPath: '$.canaryError',
    });

    // --- Full batch: remaining clients (parallel, fault-tolerant) ---
    const generatePortfolioThemes = new tasks.LambdaInvoke(
      this,
      'GeneratePortfolioThemes',
      {
        lambdaFunction: props.generatePortfolioThemesFunction,
        payloadResponseOnly: true,
      },
    );

    generatePortfolioThemes.addRetry({
      errors: ['States.TaskFailed'],
      interval: Duration.seconds(30),
      maxAttempts: 2,
      backoffRate: 2.0,
    });

    // Individual failures in full batch are logged but don't stop execution
    const portfolioThemeFailed = new sfn.Pass(this, 'PortfolioThemeFailed');

    generatePortfolioThemes.addCatch(portfolioThemeFailed, {
      errors: ['States.ALL'],
      resultPath: '$.error',
    });

    const fullBatchMap = new sfn.Map(this, 'FullBatchMap', {
      maxConcurrency: 10,
      itemsPath: '$.clientListResult.remaining_client_ids',
      itemSelector: {
        'client_id.$': '$$.Map.Item.Value',
      },
      resultPath: '$.portfolioThemesResults',
    });

    fullBatchMap.itemProcessor(generatePortfolioThemes);
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

    // Skip portfolio themes if no clients at all
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

    // Entry: generate general themes → get clients → canary → full batch
    const definition = generateGeneralThemes
      .next(getClientList)
      .next(checkClientCount);

    this.stateMachine = new sfn.StateMachine(this, 'StateMachine', {
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      timeout: Duration.hours(3),
      logs: {
        destination: logGroup,
        level: sfn.LogLevel.ALL,
      },
    });
  }
}
