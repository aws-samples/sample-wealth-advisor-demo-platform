import { Stage, StageProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { ApplicationStack } from '../stacks/application-stack.js';
import { BastionStack } from '../stacks/bastion-stack.js';

/**
 * Defines a collection of CDK Stacks which make up your application
 */
export class ApplicationStage extends Stage {
  constructor(scope: Construct, id: string, props?: StageProps) {
    super(scope, id, props);

    new ApplicationStack(this, 'Application', {
      crossRegionReferences: true,
    });

    // Deploy bastion only when explicitly enabled via cdk.json context
    if (this.node.tryGetContext('deployBastion') === true) {
      new BastionStack(this, 'Bastion');
    }
  }
}
