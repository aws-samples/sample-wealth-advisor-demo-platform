import { Lazy, Names, RemovalPolicy } from 'aws-cdk-lib';
import { Platform } from 'aws-cdk-lib/aws-ecr-assets';
import {
  Bucket,
  BlockPublicAccess,
  BucketEncryption,
} from 'aws-cdk-lib/aws-s3';
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
import { suppressRules } from '../../../core/checkov.js';

export type ReportAgentProps = Omit<
  RuntimeProps,
  'runtimeName' | 'protocolConfiguration' | 'agentRuntimeArtifact'
>;

export class ReportAgent extends Construct {
  public readonly dockerImage: AgentRuntimeArtifact;
  public readonly agentCoreRuntime: Runtime;
  public readonly reportBucket: Bucket;

  constructor(scope: Construct, id: string, props: ReportAgentProps) {
    super(scope, id);

    const { environmentVariables, ...runtimeProps } = props;

    // Access logging bucket for report storage audit trail
    const accessLogsBucket = new Bucket(this, 'ReportAccessLogsBucket', {
      versioned: false,
      enforceSSL: true,
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      encryption: BucketEncryption.S3_MANAGED,
      removalPolicy: RemovalPolicy.RETAIN,
    });
    suppressRules(
      accessLogsBucket,
      ['CKV_AWS_21'],
      'Access log bucket does not need versioning enabled',
    );
    suppressRules(
      accessLogsBucket,
      ['CKV_AWS_18'],
      'Access log bucket does not need its own access log bucket',
    );

    this.reportBucket = new Bucket(this, 'ReportBucket', {
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      encryption: BucketEncryption.S3_MANAGED,
      versioned: true,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.RETAIN,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 'report-bucket-logs/',
    });

    this.dockerImage = AgentRuntimeArtifact.fromAsset(
      path.dirname(url.fileURLToPath(new URL(import.meta.url))),
      {
        platform: Platform.LINUX_ARM64,
        extraHash: execSync(
          `docker inspect wealth-management-portal-report-agent:latest --format '{{.Id}}'`,
          { encoding: 'utf-8' },
        ).trim(),
      },
    );

    this.agentCoreRuntime = new Runtime(this, 'ReportAgent', {
      runtimeName: Lazy.string({
        produce: () =>
          Names.uniqueResourceName(this.agentCoreRuntime, { maxLength: 40 }),
      }),
      protocolConfiguration: ProtocolType.HTTP,
      agentRuntimeArtifact: this.dockerImage,
      ...runtimeProps,
      environmentVariables: {
        ...environmentVariables,
        REPORT_S3_BUCKET: this.reportBucket.bucketName,
        REPORT_BEDROCK_MODEL_ID: this.node.tryGetContext(
          'reportBedrockModelId',
        ),
      },
    });

    this.reportBucket.grantPut(this.agentCoreRuntime.role);
  }
}
