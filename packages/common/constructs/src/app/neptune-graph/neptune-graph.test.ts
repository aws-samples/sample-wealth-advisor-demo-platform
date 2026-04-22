import { App, Stack } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { NeptuneGraph } from './neptune-graph.js';

describe('NeptuneGraph', () => {
  let template: Template;

  beforeAll(() => {
    const app = new App();
    const stack = new Stack(app, 'TestStack');
    new NeptuneGraph(stack, 'TestGraph');
    template = Template.fromStack(stack);
  });

  it('creates a Neptune Analytics graph with expected properties', () => {
    template.hasResourceProperties('AWS::NeptuneGraph::Graph', {
      GraphName: 'wealth-mgmt-graph',
      ProvisionedMemory: 16,
      PublicConnectivity: true,
      DeletionProtection: false,
    });
  });

  it('creates an SSM parameter for the graph ID', () => {
    template.hasResourceProperties('AWS::SSM::Parameter', {
      Name: '/wealth-management-portal/neptune-graph-id',
      Type: 'String',
    });
  });

  it('outputs the graph ID', () => {
    template.hasOutput('*', {
      Description: 'Neptune Analytics Graph ID',
    });
  });
});
