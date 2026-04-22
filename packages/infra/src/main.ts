import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { ApplicationStage } from './stages/application-stage.js';
import { App } from ':wealth-management-portal/common-constructs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(__dirname, '../../../.env') });

const app = new App();

// Env vars from .env override cdk.json context — single config surface
const envMapping: Record<string, string | undefined> = {
  region: process.env.AWS_REGION,
  redshiftVpcId: process.env.REDSHIFT_VPC_ID,
  redshiftSecurityGroupId: process.env.REDSHIFT_SECURITY_GROUP_ID,
  privateRouteTableId: process.env.PRIVATE_ROUTE_TABLE_ID,
  privateSubnetAz: process.env.PRIVATE_SUBNET_AZ,
  tavilyApiKey: process.env.TAVILY_API_KEY,
  sesSenderEmail: process.env.SES_SENDER_EMAIL,
  reportBedrockModelId: process.env.REPORT_BEDROCK_MODEL_ID,
  complianceReportingBucket: process.env.COMPLIANCE_REPORTING_BUCKET,
  stageName: process.env.STAGE_NAME,
  redshiftWorkgroup: process.env.REDSHIFT_WORKGROUP,
  redshiftDatabase: process.env.REDSHIFT_DATABASE,
  themeBedrockModelId: process.env.THEME_BEDROCK_MODEL_ID,
};

for (const [key, value] of Object.entries(envMapping)) {
  if (value !== undefined && value !== '') {
    app.node.setContext(key, value);
  }
}

// Special handling: CSV → array
if (process.env.PRIVATE_SUBNET_IDS) {
  app.node.setContext(
    'privateSubnetIds',
    process.env.PRIVATE_SUBNET_IDS.split(',').map((s) => s.trim()),
  );
}

// Special handling: string → boolean
if (process.env.DEPLOY_BASTION !== undefined) {
  app.node.setContext('deployBastion', process.env.DEPLOY_BASTION === 'true');
}
if (process.env.ENABLE_COMPLIANCE_REPORTING !== undefined) {
  app.node.setContext(
    'enableComplianceReporting',
    process.env.ENABLE_COMPLIANCE_REPORTING === 'true',
  );
}

const stageName = app.node.tryGetContext('stageName') ?? 'sandbox';

new ApplicationStage(app, `wealth-management-portal-infra-${stageName}`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: app.node.tryGetContext('region'),
  },
});

app.synth();
