import { CfnOutput, RemovalPolicy } from 'aws-cdk-lib';
import { CfnGraph } from 'aws-cdk-lib/aws-neptunegraph';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

/**
 * Neptune Analytics graph with SSM parameter for graph ID discovery.
 * Creates a stable-named graph and publishes its ID to SSM for
 * local dev and CI consumption.
 */
export class NeptuneGraph extends Construct {
  public readonly graphId: string;
  public readonly graphArn: string;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    const graph = new CfnGraph(this, 'Graph', {
      provisionedMemory: 16,
      graphName: 'wealth-mgmt-graph',
      publicConnectivity: true,
      deletionProtection: false,
      tags: [
        { key: 'Application', value: 'wealth-management-portal' },
        { key: 'Environment', value: 'development' },
      ],
    });
    graph.applyRemovalPolicy(RemovalPolicy.DESTROY);

    // Publish graph ID to SSM for local dev and CI scripts
    new StringParameter(this, 'GraphIdParameter', {
      parameterName: '/wealth-management-portal/neptune-graph-id',
      stringValue: graph.attrGraphId,
      description: 'Neptune Analytics graph ID (CDK-managed)',
    });

    new CfnOutput(this, 'GraphId', {
      value: graph.attrGraphId,
      description: 'Neptune Analytics Graph ID',
    });

    new CfnOutput(this, 'GraphArn', {
      value: graph.attrGraphArn,
      description: 'Neptune Analytics Graph ARN',
    });

    new CfnOutput(this, 'GraphEndpoint', {
      value: graph.attrEndpoint,
      description: 'Neptune Analytics Graph Endpoint',
    });

    this.graphId = graph.attrGraphId;
    this.graphArn = graph.attrGraphArn;
  }
}
