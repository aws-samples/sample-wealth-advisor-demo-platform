import { Stage, StageProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { CiStack } from '../stacks/ci-stack.js';

export class CiStage extends Stage {
  constructor(scope: Construct, id: string, props?: StageProps) {
    super(scope, id, props);
    new CiStack(this, 'Ci');
  }
}
