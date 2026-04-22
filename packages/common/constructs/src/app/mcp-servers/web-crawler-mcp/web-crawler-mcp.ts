import { Lazy, Names } from 'aws-cdk-lib';
import { Platform } from 'aws-cdk-lib/aws-ecr-assets';
import { Construct } from 'constructs';
import * as fs from 'fs';
import * as path from 'path';
import * as url from 'url';
import {
  AgentRuntimeArtifact,
  ProtocolType,
  Runtime,
  RuntimeProps,
} from '@aws-cdk/aws-bedrock-agentcore-alpha';

export type WebCrawlerMcpProps = Omit<
  RuntimeProps,
  'runtimeName' | 'protocolConfiguration' | 'agentRuntimeArtifact'
>;

export class WebCrawlerMcp extends Construct {
  public readonly dockerImage: AgentRuntimeArtifact;
  public readonly agentCoreRuntime: Runtime;

  constructor(scope: Construct, id: string, props?: WebCrawlerMcpProps) {
    super(scope, id);

    // Build the Docker image directly from the bundle output directory.
    // CDK hashes the entire build context (including bundle-arm/) so the
    // ECR image is always rebuilt when dependencies change — no stale
    // images from a cached `docker inspect` ID.
    const thisDir = path.dirname(url.fileURLToPath(new URL(import.meta.url)));
    const workspaceRoot = path.resolve(thisDir, '../../../../../../..');
    const bundleDir = path.join(workspaceRoot, 'dist/packages/web_crawler');

    // Copy the Dockerfile into the build context so CDK can find it.
    fs.copyFileSync(
      path.join(thisDir, 'Dockerfile'),
      path.join(bundleDir, 'Dockerfile'),
    );

    this.dockerImage = AgentRuntimeArtifact.fromAsset(bundleDir, {
      platform: Platform.LINUX_ARM64,
    });

    this.agentCoreRuntime = new Runtime(this, 'WebCrawlerMcp', {
      runtimeName: Lazy.string({
        produce: () =>
          Names.uniqueResourceName(this.agentCoreRuntime, { maxLength: 40 }),
      }),
      protocolConfiguration: ProtocolType.MCP,
      agentRuntimeArtifact: this.dockerImage,
      ...props,
    });
  }
}
