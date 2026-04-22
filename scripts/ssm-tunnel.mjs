// Cross-platform SSM tunnel to Redshift Serverless.
// No-op when REDSHIFT_HOST is not set (direct connectivity or cloud environment).
import { execSync, spawn } from 'child_process';
import dotenv from 'dotenv';

dotenv.config();

if (!process.env.REDSHIFT_HOST) {
  console.log('REDSHIFT_HOST not set — skipping SSM tunnel');
  // Keep process alive for continuous Nx task
  setInterval(() => {}, 1 << 30);
} else {
  // Resolve bastion instance ID from env or CloudFormation
  let bastionInstanceId = process.env.BASTION_INSTANCE_ID;
  
  if (!bastionInstanceId) {
    try {
      bastionInstanceId = execSync(
        "aws cloudformation describe-stacks --stack-name wealth-management-portal-infra-sandbox-Bastion --query \"Stacks[0].Outputs[?OutputKey=='BastionInstanceId'].OutputValue\" --output text",
        { encoding: 'utf-8' },
      ).trim();
    } catch (error) {
      console.error('Failed to fetch bastion instance ID from CloudFormation');
    }
  }

  // Resolve Redshift endpoint from env or AWS
  let redshiftEndpoint = process.env.REDSHIFT_ENDPOINT;
  
  if (!redshiftEndpoint) {
    try {
      redshiftEndpoint = execSync(
        `aws redshift-serverless get-workgroup --workgroup-name ${process.env.REDSHIFT_WORKGROUP || 'financial-advisor-wg'} --query "workgroup.endpoint.address" --output text`,
        { encoding: 'utf-8' },
      ).trim();
    } catch (error) {
      console.error('Failed to fetch Redshift endpoint from AWS');
    }
  }

  if (!bastionInstanceId || !redshiftEndpoint || bastionInstanceId === 'skip-during-build') {
    console.error(
      'Could not resolve BASTION_INSTANCE_ID or REDSHIFT_ENDPOINT. Set them in .env or deploy the Bastion stack.',
    );
    console.log('Skipping SSM tunnel - keeping process alive for build');
    setInterval(() => {}, 1 << 30);
  } else {
    const localPort = process.env.REDSHIFT_PORT || '5439';
    console.log(
      `SSM tunnel: localhost:${localPort} → ${redshiftEndpoint}:5439`,
    );

    // Start the SSM session, forwarding stdio so the user sees connection status
    const params = JSON.stringify({
      host: [redshiftEndpoint],
      portNumber: ['5439'],
      localPortNumber: [localPort],
    });

    // Spawn aws directly (no shell) so JSON args pass through without quote mangling.
    // AWS CLI v2 provides aws.exe on Windows, aws on Unix.
    const awsBin = process.platform === 'win32' ? 'aws.exe' : 'aws';
    const child = spawn(
      awsBin,
      [
        'ssm',
        'start-session',
        '--target',
        bastionInstanceId,
        '--document-name',
        'AWS-StartPortForwardingSessionToRemoteHost',
        '--parameters',
        params,
      ],
      { stdio: 'inherit' },
    );

    child.on('exit', (code) => process.exit(code ?? 1));
  }
}
