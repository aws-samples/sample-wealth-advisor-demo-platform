import { CfnOutput, RemovalPolicy, Stack } from 'aws-cdk-lib';
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

    const existingGraphId = this.node.tryGetContext('neptuneGraphId') as
      | string
      | undefined;
    let graphId: string;
    let graphArn: string;
    let graphEndpoint: string;

    if (existingGraphId) {
      // Reuse an existing graph/parameter pair discovered from SSM. This
      // avoids CloudFormation AlreadyExists failures on redeployments where
      // the graph predates the current application stack.
      graphId = existingGraphId;
      graphArn = `arn:aws:neptune-graph:${Stack.of(this).region}:${Stack.of(this).account}:graph/${existingGraphId}`;
      graphEndpoint = `https://${existingGraphId}.${Stack.of(this).region}.neptune-graph.amazonaws.com`;
    } else {
      // Neptune data-plane connectivity is private by default. Set the CDK
      // context key `neptunePublicConnectivity` to true only when the target
      // environment has a reviewed requirement for public graph connectivity.
      const publicConnectivity =
        this.node.tryGetContext('neptunePublicConnectivity') ?? false;

      const graph = new CfnGraph(this, 'Graph', {
        provisionedMemory: 16,
        graphName: 'wealth-mgmt-graph',
        publicConnectivity,
        deletionProtection: false,
        tags: [
          { key: 'Application', value: 'wealth-management-portal' },
          { key: 'Environment', value: 'development' },
        ],
      });
      graph.applyRemovalPolicy(RemovalPolicy.DESTROY);

      // Publish graph ID to SSM for local dev and CI scripts.
      new StringParameter(this, 'GraphIdParameter', {
        parameterName: '/wealth-management-portal/neptune-graph-id',
        stringValue: graph.attrGraphId,
        description: 'Neptune Analytics graph ID (CDK-managed)',
      });

      graphId = graph.attrGraphId;
      graphArn = graph.attrGraphArn;
      graphEndpoint = graph.attrEndpoint;
    }

    new CfnOutput(this, 'GraphId', {
      value: graphId,
      description: 'Neptune Analytics Graph ID',
    });

    new CfnOutput(this, 'GraphArn', {
      value: graphArn,
      description: 'Neptune Analytics Graph ARN',
    });

    new CfnOutput(this, 'GraphEndpoint', {
      value: graphEndpoint,
      description: 'Neptune Analytics Graph Endpoint',
    });

    this.graphId = graphId;
    this.graphArn = graphArn;
  }
}
