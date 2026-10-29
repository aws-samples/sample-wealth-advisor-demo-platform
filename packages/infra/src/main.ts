import dotenv from 'dotenv';
import { CfnResource } from 'aws-cdk-lib';
import path from 'path';
import { fileURLToPath } from 'url';
import { ApplicationStage } from './stages/application-stage.js';
import {
  App,
  suppressRules,
} from ':wealth-management-portal/common-constructs';

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
  ddKnowledgeBaseId: process.env.DD_KNOWLEDGE_BASE_ID,
  ddBedrockModelId: process.env.DD_BEDROCK_MODEL_ID,
  routingBedrockModelId: process.env.ROUTING_BEDROCK_MODEL_ID,
  subagentBedrockModelId: process.env.SUBAGENT_BEDROCK_MODEL_ID,
  stockAgentBedrockModelId: process.env.STOCK_AGENT_BEDROCK_MODEL_ID,
  neptunePublicConnectivity: process.env.NEPTUNE_PUBLIC_CONNECTIVITY,
  neptuneGraphId: process.env.NEPTUNE_GRAPH_ID,
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

if (process.env.NEPTUNE_PUBLIC_CONNECTIVITY !== undefined) {
  app.node.setContext(
    'neptunePublicConnectivity',
    process.env.NEPTUNE_PUBLIC_CONNECTIVITY === 'true',
  );
}

const stageName = app.node.tryGetContext('stageName') ?? 'sandbox';

new ApplicationStage(app, `wealth-management-portal-infra-${stageName}`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: app.node.tryGetContext('region'),
  },
});

app.node.addValidation({
  validate: () => {
    for (const node of app.node.findAll()) {
      if (
        CfnResource.isCfnResource(node) &&
        node.cfnResourceType === 'AWS::Lambda::Function' &&
        node.node.path.includes('CustomCrossRegionExport')
      ) {
        suppressRules(
          node,
          ['CKV_AWS_115', 'CKV_AWS_116', 'CKV_AWS_117'],
          'CDK cross-region reference custom-resource Lambda is framework-managed; it runs synchronously during deployment and is not an application data-plane function.',
        );
      }
    }
    return [];
  },
});

app.synth();
