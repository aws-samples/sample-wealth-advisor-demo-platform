import { Lazy, Names, Stack } from 'aws-cdk-lib';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Platform } from 'aws-cdk-lib/aws-ecr-assets';
import { SecurityGroup, Subnet, Vpc } from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';
import { execSync } from 'child_process';
import * as path from 'path';
import * as url from 'url';
import {
  AgentRuntimeArtifact,
  ProtocolType,
  Runtime,
  RuntimeNetworkConfiguration,
} from '@aws-cdk/aws-bedrock-agentcore-alpha';

export interface RedshiftDataAccessProps {
  vpcId: string;
  privateSubnetIds: string[];
  privateRouteTableId: string;
  /** Security group that allows egress to Redshift + VPC endpoints (reuse from PortfolioDataAccess) */
  mcpSecurityGroup: SecurityGroup;
  redshiftWorkgroup: string;
  redshiftDatabase: string;
}

export class RedshiftDataAccess extends Construct {
  public readonly agentCoreRuntime: Runtime;

  constructor(scope: Construct, id: string, props: RedshiftDataAccessProps) {
    super(scope, id);

    const {
      vpcId,
      privateSubnetIds,
      privateRouteTableId,
      mcpSecurityGroup,
      redshiftWorkgroup,
      redshiftDatabase,
    } = props;

    const vpc = Vpc.fromLookup(this, 'Vpc', { vpcId });
    const privateSubnets = privateSubnetIds.map((subnetId, index) =>
      Subnet.fromSubnetAttributes(this, `PrivateSubnet${index + 1}`, {
        subnetId,
        routeTableId: privateRouteTableId,
      }),
    );

    const dockerImage = AgentRuntimeArtifact.fromAsset(
      path.dirname(url.fileURLToPath(new URL(import.meta.url))),
      {
        platform: Platform.LINUX_ARM64,
        extraHash: execSync(
          `docker inspect wealth-management-portal-redshift-data-access:latest --format '{{.Id}}'`,
          { encoding: 'utf-8' },
        ).trim(),
      },
    );

    this.agentCoreRuntime = new Runtime(this, 'RedshiftDataAccess', {
      runtimeName: Lazy.string({
        produce: () =>
          Names.uniqueResourceName(this.agentCoreRuntime, { maxLength: 40 }),
      }),
      protocolConfiguration: ProtocolType.MCP,
      agentRuntimeArtifact: dockerImage,
      networkConfiguration: RuntimeNetworkConfiguration.usingVpc(this, {
        vpc,
        vpcSubnets: { subnets: privateSubnets },
        securityGroups: [mcpSecurityGroup],
      }),
      environmentVariables: {
        REDSHIFT_WORKGROUP: redshiftWorkgroup,
        REDSHIFT_DATABASE: redshiftDatabase,
        REDSHIFT_REGION: Stack.of(this).region,
      },
    });

    // Required for Redshift to resolve federated S3 Tables catalog views via Lake Formation
    this.agentCoreRuntime.role.addToPrincipalPolicy(
      new PolicyStatement({
        actions: [
          'lakeformation:GetDataAccess',
          'glue:GetTable',
          'glue:GetTables',
          'glue:GetDatabase',
          'glue:GetDatabases',
          'glue:GetCatalog',
        ],
        resources: ['*'],
      }),
    );
  }
}
