import {
  Stack,
  StackProps,
  Duration,
  RemovalPolicy,
  CfnOutput,
  CfnParameter,
} from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as codebuild from 'aws-cdk-lib/aws-codebuild';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class CiStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const gitlabGroup = new CfnParameter(this, 'GitLabGroup', {
      type: 'String',
      default: 'taehyunh',
    });

    const gitlabProject = new CfnParameter(this, 'GitLabProject', {
      type: 'String',
      default: 'wealth-management-portal',
    });

    // S3 source bucket
    const sourceBucket = new s3.Bucket(this, 'SourceBucket', {
      lifecycleRules: [
        {
          expiration: Duration.days(7),
          noncurrentVersionExpiration: Duration.days(1),
        },
      ],
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // CodeBuild project
    const project = new codebuild.Project(this, 'DeployProject', {
      projectName: 'wealth-mgmt-deploy',
      source: codebuild.Source.s3({
        bucket: sourceBucket,
        path: 'source.zip',
      }),
      buildSpec: codebuild.BuildSpec.fromObject({
        version: '0.2',
        phases: { build: { commands: ['echo override'] } },
      }),
      environment: {
        buildImage: codebuild.LinuxArmBuildImage.fromCodeBuildImageId(
          'aws/codebuild/amazonlinux2-aarch64-standard:3.0',
        ),
        computeType: codebuild.ComputeType.MEDIUM,
        privileged: true,
      },
      timeout: Duration.minutes(30),
      environmentVariables: {
        STAGE_NAME: { value: 'sandbox' },
        AWS_REGION: {
          value: '/wealth-management-portal/aws-region',
          type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
        },
        // Infrastructure vars (VPC, subnets, Redshift workgroup, etc.) are
        // auto-discovered by scripts/generate-env-from-ssm.sh at build time
        // from data-platform SSM params (/{APP_NAME}/{ENV_NAME}/...).
        APP_NAME: {
          value: '/wealth-management-portal/platform/app-name',
          type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
        },
        ENV_NAME: {
          value: '/wealth-management-portal/platform/env-name',
          type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
        },
        REDSHIFT_DATABASE: {
          value: '/wealth-management-portal/redshift-database',
          type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
        },
        SES_SENDER_EMAIL: {
          value: '/wealth-management-portal/ses-sender-email',
          type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
        },
        REPORT_BEDROCK_MODEL_ID: {
          value: '/wealth-management-portal/report-bedrock-model-id',
          type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
        },
        TAVILY_API_KEY: {
          value: '/wealth-management-portal/tavily-api-key',
          type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
        },
        THEME_BEDROCK_MODEL_ID: {
          value: '/wealth-management-portal/theme-bedrock-model-id',
          type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
        },
        DEPLOY_BASTION: {
          value: '/wealth-management-portal/deploy-bastion',
          type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
        },
      },
      cache: codebuild.Cache.local(
        codebuild.LocalCacheMode.DOCKER_LAYER,
        codebuild.LocalCacheMode.SOURCE,
      ),
    });

    // Grant CodeBuild admin access + S3 read
    project.role!.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess'),
    );
    sourceBucket.grantRead(project);

    // Phase 1: data-platform deployment via Terraform make targets
    const platformProject = new codebuild.Project(
      this,
      'PlatformDeployProject',
      {
        projectName: 'wealth-mgmt-platform-deploy',
        source: codebuild.Source.s3({
          bucket: sourceBucket,
          path: 'source.zip',
        }),
        buildSpec: codebuild.BuildSpec.fromObject({
          version: '0.2',
          phases: { build: { commands: ['echo override'] } },
        }),
        environment: {
          buildImage: codebuild.LinuxArmBuildImage.fromCodeBuildImageId(
            'aws/codebuild/amazonlinux2-aarch64-standard:3.0',
          ),
          computeType: codebuild.ComputeType.LARGE,
          privileged: true,
        },
        timeout: Duration.hours(4),
        environmentVariables: {
          ACCOUNT_ID: {
            value: '/wealth-management-portal/platform/account-id',
            type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
          },
          APP_NAME: {
            value: '/wealth-management-portal/platform/app-name',
            type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
          },
          ENV_NAME: {
            value: '/wealth-management-portal/platform/env-name',
            type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
          },
          PRIMARY_REGION: {
            value: '/wealth-management-portal/platform/primary-region',
            type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
          },
          SECONDARY_REGION: {
            value: '/wealth-management-portal/platform/secondary-region',
            type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
          },
          ADMIN_ROLE: {
            value: '/wealth-management-portal/platform/admin-role',
            type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
          },
        },
        cache: codebuild.Cache.local(
          codebuild.LocalCacheMode.DOCKER_LAYER,
          codebuild.LocalCacheMode.SOURCE,
        ),
      },
    );

    platformProject.role!.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess'),
    );
    sourceBucket.grantRead(platformProject);

    // GitLab trigger role (assumed by Credential Vendor)
    const triggerPrincipal = new iam.ArnPrincipal(
      'arn:aws:iam::979517299116:role/gitlab-runners-prod',
    ).withConditions({
      StringEquals: {
        'aws:PrincipalTag/GitLab:Group': gitlabGroup.valueAsString,
        'aws:PrincipalTag/GitLab:Project': gitlabProject.valueAsString,
        // TODO: Re-enable after validating pipeline — requires main branch protection in GitLab
        // 'aws:PrincipalTag/GitLab:Project:ProtectedBranch': 'Yes',
      },
    });

    const triggerRole = new iam.Role(this, 'GitLabTriggerRole', {
      assumedBy: triggerPrincipal,
    });

    // Credential Vendor requires sts:TagSession to pass session tags
    triggerRole.assumeRolePolicy!.addStatements(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        principals: [
          new iam.ArnPrincipal(
            'arn:aws:iam::979517299116:role/gitlab-runners-prod',
          ),
        ],
        actions: ['sts:TagSession'],
      }),
    );

    triggerRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['codebuild:StartBuild', 'codebuild:BatchGetBuilds'],
        resources: [project.projectArn, platformProject.projectArn],
      }),
    );
    triggerRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['s3:PutObject'],
        resources: [sourceBucket.arnForObjects('*')],
      }),
    );

    new CfnOutput(this, 'GitLabTriggerRoleArn', { value: triggerRole.roleArn });
    new CfnOutput(this, 'SourceBucketName', { value: sourceBucket.bucketName });
    new CfnOutput(this, 'CodeBuildProjectName', { value: project.projectName });
    new CfnOutput(this, 'PlatformCodeBuildProjectName', {
      value: platformProject.projectName,
    });
  }
}
