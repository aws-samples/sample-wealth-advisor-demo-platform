import { Duration } from 'aws-cdk-lib';
import { Code, Function, Runtime, Tracing } from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';
import * as url from 'url';

export interface ThemeSchedulerGeneratePortfolioThemesProps {
  readonly redshiftWorkgroup: string;
  readonly redshiftDatabase: string;
  readonly webCrawlerMcpArn: string;
}

export class ThemeSchedulerGeneratePortfolioThemes extends Function {
  constructor(
    scope: Construct,
    id: string,
    props: ThemeSchedulerGeneratePortfolioThemesProps,
  ) {
    super(scope, id, {
      timeout: Duration.minutes(15),
      memorySize: 512,
      runtime: Runtime.PYTHON_3_12,
      handler:
        'wealth_management_portal_scheduler_tools.lambda_functions.generate_portfolio_themes.lambda_handler',
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
        REDSHIFT_WORKGROUP: props.redshiftWorkgroup,
        REDSHIFT_DATABASE: props.redshiftDatabase,
        WEB_CRAWLER_MCP_ARN: props.webCrawlerMcpArn,
        THEME_BEDROCK_MODEL_ID:
          scope.node.tryGetContext('themeBedrockModelId') ??
          'us.anthropic.claude-sonnet-4-5-20250929-v1:0',
        TOP_N_STOCKS: '5',
        THEMES_PER_STOCK: '3',
        THEME_HOURS: '48',
      },
    });
  }
}
