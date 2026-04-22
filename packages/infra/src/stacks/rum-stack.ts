import * as cdk from 'aws-cdk-lib';
import * as rum from 'aws-cdk-lib/aws-rum';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface RumStackProps extends cdk.StackProps {
  appName: string;
  domain: string;
  identityPoolId?: string;
}

export class RumStack extends cdk.Stack {
  public readonly appMonitor: rum.CfnAppMonitor;

  constructor(scope: Construct, id: string, props: RumStackProps) {
    super(scope, id, props);

    const guestRole = new iam.Role(this, 'RumGuestRole', {
      assumedBy: new iam.ServicePrincipal('rum.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          'AmazonCloudWatchRUMFullAccess',
        ),
      ],
    });

    this.appMonitor = new rum.CfnAppMonitor(this, 'AppMonitor', {
      name: `${props.appName}-monitor`,
      domain: props.domain,

      appMonitorConfiguration: {
        allowCookies: true,
        enableXRay: true,
        sessionSampleRate: 1.0,
        telemetries: ['errors', 'performance', 'http'],
        identityPoolId: props.identityPoolId,
        guestRoleArn: guestRole.roleArn,
      },

      cwLogEnabled: true,
    });

    new cdk.CfnOutput(this, 'AppMonitorId', {
      value: this.appMonitor.ref,
    });

    new cdk.CfnOutput(this, 'RumScriptUrl', {
      value: `https://client.rum.${this.region}.amazonaws.com/1.x/cwr.js`,
    });
  }
}
