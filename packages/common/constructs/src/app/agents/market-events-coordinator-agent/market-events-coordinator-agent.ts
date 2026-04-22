import { Lazy, Names } from 'aws-cdk-lib';
import { Platform } from 'aws-cdk-lib/aws-ecr-assets';
import { Construct } from 'constructs';
import { execSync } from 'child_process';
import * as path from 'path';
import * as url from 'url';
import {
  AgentRuntimeArtifact,
  ProtocolType,
  Runtime,
  RuntimeProps,
} from '@aws-cdk/aws-bedrock-agentcore-alpha';

export type MarketEventsCoordinatorAgentProps = Omit<
  RuntimeProps,
  'runtimeName' | 'protocolConfiguration' | 'agentRuntimeArtifact'
>;

export class MarketEventsCoordinatorAgent extends Construct {
  public readonly dockerImage: AgentRuntimeArtifact;
  public readonly agentCoreRuntime: Runtime;

  constructor(
    scope: Construct,
    id: string,
    props?: MarketEventsCoordinatorAgentProps,
  ) {
    super(scope, id);

    this.dockerImage = AgentRuntimeArtifact.fromAsset(
      path.dirname(url.fileURLToPath(new URL(import.meta.url))),
      {
        platform: Platform.LINUX_ARM64,
        extraHash: execSync(
          `docker inspect wealth-management-portal-market-events-coordinator-agent:latest --format '{{.Id}}'`,
          { encoding: 'utf-8' },
        ).trim(),
      },
    );

    this.agentCoreRuntime = new Runtime(this, 'MarketEventsCoordinatorAgent', {
      runtimeName: Lazy.string({
        produce: () =>
          Names.uniqueResourceName(this.agentCoreRuntime, { maxLength: 40 }),
      }),
      protocolConfiguration: ProtocolType.HTTP,
      agentRuntimeArtifact: this.dockerImage,
      ...props,
    });
  }
}
