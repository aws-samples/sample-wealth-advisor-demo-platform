import { App } from 'aws-cdk-lib';
import { BastionStack } from './stacks/bastion-stack.js';

const app = new App();

new BastionStack(app, 'wealth-management-portal-bastion', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: app.node.tryGetContext('region'),
  },
});

app.synth();
