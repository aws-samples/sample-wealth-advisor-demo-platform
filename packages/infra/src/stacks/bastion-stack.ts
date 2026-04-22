import { CfnOutput, CfnResource, Stack, StackProps, Tags } from 'aws-cdk-lib';
import {
  Vpc,
  Subnet,
  SecurityGroup,
  Instance,
  InstanceType,
  InstanceClass,
  InstanceSize,
  MachineImage,
  AmazonLinuxCpuType,
  Port,
  Peer,
  CfnSecurityGroupIngress,
  InterfaceVpcEndpoint,
  InterfaceVpcEndpointAwsService,
} from 'aws-cdk-lib/aws-ec2';
import { ManagedPolicy, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import {
  CfnDocument,
  CfnAssociation,
  CfnResourceDataSync,
  CfnPatchBaseline,
} from 'aws-cdk-lib/aws-ssm';
import {
  AwsCustomResource,
  AwsCustomResourcePolicy,
  PhysicalResourceId,
} from 'aws-cdk-lib/custom-resources';
import { Construct, IConstruct } from 'constructs';
import { suppressRules } from ':wealth-management-portal/common-constructs';

export class BastionStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Import existing VPC and resources from context
    const vpc = Vpc.fromLookup(this, 'Vpc', {
      vpcId: this.node.getContext('redshiftVpcId'),
    });

    const privateSubnetIds: string[] = this.node.getContext('privateSubnetIds');
    const privateRouteTableId = this.node.getContext('privateRouteTableId');

    // Imported subnet with AZ for EC2 instance placement
    const bastionSubnet = Subnet.fromSubnetAttributes(this, 'BastionSubnet', {
      subnetId: privateSubnetIds[0],
      availabilityZone: this.node.getContext('privateSubnetAz'),
      routeTableId: privateRouteTableId,
    });

    const redshiftSg = SecurityGroup.fromSecurityGroupId(
      this,
      'RedshiftSg',
      this.node.getContext('redshiftSecurityGroupId'),
    );

    // Create bastion security group
    const bastionSg = new SecurityGroup(this, 'BastionSg', {
      vpc,
      description: 'Security group for bastion host',
      allowAllOutbound: false,
    });

    const ssmEndpointSg = new SecurityGroup(this, 'SsmEndpointSg', {
      vpc,
      description: 'Security group for SSM VPC endpoints',
      allowAllOutbound: false,
    });

    // Configure security group rules
    bastionSg.addEgressRule(redshiftSg, Port.tcp(5439), 'Access to Redshift');
    bastionSg.addEgressRule(
      ssmEndpointSg,
      Port.tcp(443),
      'Access to SSM endpoints',
    );

    // Add ingress rule to Redshift SG (using CfnSecurityGroupIngress for imported SG)
    new CfnSecurityGroupIngress(this, 'RedshiftIngressFromBastion', {
      groupId: redshiftSg.securityGroupId,
      sourceSecurityGroupId: bastionSg.securityGroupId,
      ipProtocol: 'tcp',
      fromPort: 5439,
      toPort: 5439,
      description: 'Access from bastion host',
    });

    // Add ingress rule to SSM endpoint SG to allow bastion access
    new CfnSecurityGroupIngress(this, 'SsmEndpointIngressFromBastion', {
      groupId: ssmEndpointSg.securityGroupId,
      sourceSecurityGroupId: bastionSg.securityGroupId,
      ipProtocol: 'tcp',
      fromPort: 443,
      toPort: 443,
      description: 'Access from bastion host',
    });

    // Create IAM role for bastion
    const bastionRole = new Role(this, 'BastionRole', {
      assumedBy: new ServicePrincipal('ec2.amazonaws.com'),
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore'),
      ],
    });

    // Place instance in subnet with AZ info
    const bastionInstance = new Instance(this, 'BastionInstance', {
      vpc,
      vpcSubnets: { subnets: [bastionSubnet] },
      instanceType: InstanceType.of(InstanceClass.T4G, InstanceSize.NANO),
      machineImage: MachineImage.latestAmazonLinux2023({
        cpuType: AmazonLinuxCpuType.ARM_64,
      }),
      securityGroup: bastionSg,
      role: bastionRole,
    });

    // Outputs
    new CfnOutput(this, 'BastionInstanceId', {
      value: bastionInstance.instanceId,
      description: 'Bastion instance ID for SSM tunneling',
    });

    new CfnOutput(this, 'SsmTunnelCommand', {
      value: `aws ssm start-session --target ${bastionInstance.instanceId} --document-name AWS-StartPortForwardingSessionToRemoteHost --parameters '{"host":["<REDSHIFT_ENDPOINT>"],"portNumber":["5439"],"localPortNumber":["5439"]}'`,
      description:
        'SSM tunnel command — replace <REDSHIFT_ENDPOINT> with your workgroup endpoint',
    });

    // Compliance reporting: SSM inventory collection and sync
    const inventoryDocument = new CfnDocument(
      this,
      'InventoryCollectionDocument',
      {
        name: 'InventoryCollectionDocument',
        documentType: 'Command',
        content: {
          schemaVersion: '2.2',
          description: 'Collect software inventory and kernel information',
          parameters: {
            applications: {
              type: 'String',
              default: 'Enabled',
              description:
                '(Optional) Collect data for installed applications.',
              allowedValues: ['Enabled', 'Disabled'],
            },
            awsComponents: {
              type: 'String',
              default: 'Enabled',
              description:
                '(Optional) Collect data for AWS Components like amazon-ssm-agent.',
              allowedValues: ['Enabled', 'Disabled'],
            },
            files: {
              type: 'String',
              default: '',
              description:
                '(Optional, requires SSMAgent version 2.2.64.0 and above) File inventory configuration.',
              displayType: 'textarea',
            },
            networkConfig: {
              type: 'String',
              default: 'Enabled',
              description:
                '(Optional) Collect data for Network configurations.',
              allowedValues: ['Enabled', 'Disabled'],
            },
            windowsUpdates: {
              type: 'String',
              default: 'Enabled',
              description:
                '(Optional, Windows OS only) Collect data for all Windows Updates.',
              allowedValues: ['Enabled', 'Disabled'],
            },
            instanceDetailedInformation: {
              type: 'String',
              default: 'Enabled',
              description:
                '(Optional) Collect additional information about the instance, including the CPU model, speed, and the number of cores, to name a few.',
              allowedValues: ['Enabled', 'Disabled'],
            },
            services: {
              type: 'String',
              default: 'Enabled',
              description:
                '(Optional, Windows OS only, requires SSMAgent version 2.2.64.0 and above) Collect data for service configurations.',
              allowedValues: ['Enabled', 'Disabled'],
            },
            windowsRegistry: {
              type: 'String',
              default: '',
              description:
                '(Optional, Windows OS only, requires SSMAgent version 2.2.64.0 and above) Windows registry configuration.',
              displayType: 'textarea',
            },
            windowsRoles: {
              type: 'String',
              default: 'Enabled',
              description:
                '(Optional, Windows OS only, requires SSMAgent version 2.2.64.0 and above) Collect data for Microsoft Windows role configurations.',
              allowedValues: ['Enabled', 'Disabled'],
            },
            customInventory: {
              type: 'String',
              default: 'Enabled',
              description: '(Optional) Collect data for custom inventory.',
              allowedValues: ['Enabled', 'Disabled'],
            },
            billingInfo: {
              type: 'String',
              default: 'Enabled',
              description:
                '(Optional) Collect billing info for license included applications.',
              allowedValues: ['Enabled', 'Disabled'],
            },
          },
          mainSteps: [
            {
              action: 'aws:runShellScript',
              name: 'collectCustomInventoryItems',
              inputs: {
                timeoutSeconds: 7200,
                runCommand: [
                  '#!/bin/bash',
                  'token=$(curl --silent --show-error --retry 3 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")',
                  'instance_id=$(curl --silent --show-error --retry 3 -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/instance-id)',
                  'kernel_version=$(uname -r)',
                  'content="{\\"SchemaVersion\\": \\"1.0\\", \\"TypeName\\": \\"Custom:SystemInfo\\", \\"Content\\": {\\"KernelVersion\\": \\"$kernel_version\\"}}"',
                  'dir_path="/var/lib/amazon/ssm/$instance_id/inventory/custom"',
                  'mkdir -p $dir_path',
                  'echo $content > $dir_path/CustomSystemInfo.json',
                ],
              },
            },
            {
              action: 'aws:softwareInventory',
              name: 'collectSoftwareInventoryItems',
              inputs: {
                applications: '{{ applications }}',
                awsComponents: '{{ awsComponents }}',
                networkConfig: '{{ networkConfig }}',
                files: '{{ files }}',
                services: '{{ services }}',
                windowsRoles: '{{ windowsRoles }}',
                windowsRegistry: '{{ windowsRegistry}}',
                windowsUpdates: '{{ windowsUpdates }}',
                instanceDetailedInformation:
                  '{{ instanceDetailedInformation }}',
                billingInfo: '{{ billingInfo }}',
                customInventory: '{{ customInventory }}',
              },
            },
          ],
        },
      },
    );

    // Run inventory collection every 12 hours on all instances with a Name tag
    new CfnAssociation(this, 'InventoryCollection', {
      name: inventoryDocument.ref,
      associationName: `${this.account}-InventoryCollection`,
      scheduleExpression: 'rate(12 hours)',
      targets: [{ key: 'tag-key', values: ['Name'] }],
    });

    // Sync inventory data to the compliance reporting S3 bucket (internal AWS only)
    const enableComplianceReporting =
      this.node.tryGetContext('enableComplianceReporting') === true;
    if (enableComplianceReporting) {
      const bucketPattern = this.node.tryGetContext(
        'complianceReportingBucket',
      ) as string;
      if (!bucketPattern) {
        throw new Error(
          'complianceReportingBucket context key is required when enableComplianceReporting is true',
        );
      }
      const bucketName = bucketPattern.replace('{region}', this.region);
      new CfnResourceDataSync(this, 'ComplianceReporting', {
        bucketName,
        bucketRegion: this.region,
        syncFormat: 'JsonSerDe',
        syncName: `${this.account}-ComplianceReporting`,
      });
    }

    // Step 1: Bastion SG egress for package downloads
    // S3 gateway VPC endpoint is expected to already exist (created by data-platform VPC module)
    bastionSg.addEgressRule(
      Peer.anyIpv4(),
      Port.tcp(443),
      'S3 access for patching',
    );

    // Step 2: AL2023 patch baseline + register as default
    const patchBaseline = new CfnPatchBaseline(this, 'AL2023PatchBaseline', {
      name: 'DefaultAmazonLinux2023PatchBaseline',
      operatingSystem: 'AMAZON_LINUX_2023',
      approvedPatchesEnableNonSecurity: true,
      approvedPatches: ['kernel*'],
      description: `Default Amazon Linux 2023 Patch Baseline for Account: ${this.account}`,
      approvalRules: {
        patchRules: [
          {
            enableNonSecurity: false,
            approveAfterDays: 0,
            patchFilterGroup: {
              patchFilters: [
                {
                  values: ['Security'],
                  key: 'CLASSIFICATION',
                },
              ],
            },
          },
        ],
      },
      sources: [
        {
          name: 'AMAZONLINUX',
          products: ['*'],
          configuration:
            '[amazonlinux]\nname=Amazon Linux 2023 repository\nmirrorlist=https://al2023-repos-$awsregion-de612dc2.s3$dualstack.$awsregion.$awsdomain/core/mirrors/$releasever/$basearch/$mirrorlist\npriority=10\nenabled=1\nrepo_gpgcheck=0\ntype=rpm\ngpgcheck=1\ngpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-amazon-linux-2023',
        },
      ],
    });

    const registerDefaultBaseline = new AwsCustomResource(
      this,
      'RegisterDefaultPatchBaseline',
      {
        onCreate: {
          service: 'SSM',
          action: 'registerDefaultPatchBaseline',
          parameters: { BaselineId: patchBaseline.ref },
          physicalResourceId: PhysicalResourceId.of(patchBaseline.ref),
        },
        onUpdate: {
          service: 'SSM',
          action: 'registerDefaultPatchBaseline',
          parameters: { BaselineId: patchBaseline.ref },
          physicalResourceId: PhysicalResourceId.of(patchBaseline.ref),
        },
        policy: AwsCustomResourcePolicy.fromSdkCalls({
          resources: AwsCustomResourcePolicy.ANY_RESOURCE,
        }),
      },
    );

    // Step 3: Weekly patching association
    const patchAssociation = new CfnAssociation(this, 'PatchWeekly', {
      name: 'AWS-RunPatchBaseline',
      associationName: `${this.account}-PatchWeekly`,
      scheduleExpression: 'rate(7 days)',
      parameters: { Operation: ['Install'] },
      targets: [{ key: 'InstanceIds', values: [bastionInstance.instanceId] }],
    });

    patchAssociation.addDependency(patchBaseline);

    // Step 4: CollectRunningKernel document and association
    const kernelDocument = new CfnDocument(
      this,
      'CollectRunningKernelDocument',
      {
        name: 'CollectRunningKernel',
        documentType: 'Command',
        content: {
          schemaVersion: '2.2',
          description: 'Collect Running Kernel Version on Instance',
          mainSteps: [
            {
              precondition: {
                StringEquals: ['platformType', 'Linux'],
              },
              action: 'aws:runShellScript',
              name: 'CollectRunningKernel',
              inputs: {
                runCommand: [
                  '#!/bin/bash',
                  'token=$(curl --silent --show-error --retry 3 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")',
                  'instance_id=$(curl --silent --show-error --retry 3 -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/instance-id)',
                  'kernel_version=$(uname -r)',
                  'content="{\\"SchemaVersion\\": \\"1.0\\", \\"TypeName\\": \\"Custom:SystemInfo\\", \\"Content\\": {\\"KernelVersion\\": \\"$kernel_version\\"}}"',
                  'dir_path="/var/lib/amazon/ssm/$instance_id/inventory/custom"',
                  'mkdir -p $dir_path',
                  'echo $content > $dir_path/CustomSystemInfo.json',
                ],
              },
            },
          ],
        },
      },
    );

    new CfnAssociation(this, 'CollectRunningKernelAssociation', {
      name: kernelDocument.ref,
      associationName: `${this.account}-CollectRunningKernel`,
      scheduleExpression: 'rate(2 hours)',
      targets: [{ key: 'InstanceIds', values: [bastionInstance.instanceId] }],
    });

    // Step 5: SSM interface VPC endpoints for SSM connectivity
    const endpointSubnets = { subnets: [bastionSubnet] };

    new InterfaceVpcEndpoint(this, 'SsmEndpoint', {
      vpc,
      service: InterfaceVpcEndpointAwsService.SSM,
      subnets: endpointSubnets,
      securityGroups: [ssmEndpointSg],
      privateDnsEnabled: true,
    });

    new InterfaceVpcEndpoint(this, 'SsmMessagesEndpoint', {
      vpc,
      service: InterfaceVpcEndpointAwsService.SSM_MESSAGES,
      subnets: endpointSubnets,
      securityGroups: [ssmEndpointSg],
      privateDnsEnabled: true,
    });

    new InterfaceVpcEndpoint(this, 'Ec2MessagesEndpoint', {
      vpc,
      service: InterfaceVpcEndpointAwsService.EC2_MESSAGES,
      subnets: endpointSubnets,
      securityGroups: [ssmEndpointSg],
      privateDnsEnabled: true,
    });

    // Step 6: Patch Group tag and baseline registration
    Tags.of(bastionInstance).add('Patch Group', 'bastion-al2023');

    const registerPatchGroup = new AwsCustomResource(
      this,
      'RegisterPatchGroup',
      {
        onCreate: {
          service: 'SSM',
          action: 'registerPatchBaselineForPatchGroup',
          parameters: {
            BaselineId: patchBaseline.ref,
            PatchGroup: 'bastion-al2023',
          },
          physicalResourceId: PhysicalResourceId.of('bastion-al2023'),
        },
        onUpdate: {
          service: 'SSM',
          action: 'registerPatchBaselineForPatchGroup',
          parameters: {
            BaselineId: patchBaseline.ref,
            PatchGroup: 'bastion-al2023',
          },
          physicalResourceId: PhysicalResourceId.of('bastion-al2023'),
        },
        onDelete: {
          service: 'SSM',
          action: 'deregisterPatchBaselineForPatchGroup',
          parameters: {
            BaselineId: patchBaseline.ref,
            PatchGroup: 'bastion-al2023',
          },
        },
        policy: AwsCustomResourcePolicy.fromSdkCalls({
          resources: AwsCustomResourcePolicy.ANY_RESOURCE,
        }),
      },
    );

    registerPatchGroup.node.addDependency(patchBaseline);

    // SSM patch APIs do not support resource-level permissions
    const iamPolicyPredicate = (c: IConstruct) =>
      CfnResource.isCfnResource(c) && c.cfnResourceType === 'AWS::IAM::Policy';
    suppressRules(
      registerDefaultBaseline,
      ['CKV_AWS_111'],
      'ssm:RegisterDefaultPatchBaseline does not support resource-level permissions',
      iamPolicyPredicate,
    );
    suppressRules(
      registerPatchGroup,
      ['CKV_AWS_111'],
      'ssm:RegisterPatchBaselineForPatchGroup does not support resource-level permissions',
      iamPolicyPredicate,
    );
  }
}
