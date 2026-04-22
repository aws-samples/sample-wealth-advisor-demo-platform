import { CiStage } from './stages/ci-stage.js';
import { App } from 'aws-cdk-lib';

const app = new App();

new CiStage(app, 'wealth-management-portal-ci-infra', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});

app.synth();
