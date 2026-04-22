// Creates a Cognito user after CDK deployment.
// Auto-resolves the User Pool ID from CloudFormation stack outputs.
// No external dependencies — uses AWS CLI via child_process.
import { createInterface } from 'readline';
import { existsSync, readFileSync, writeFileSync, unlinkSync } from 'fs';
import { resolve, dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';
import { tmpdir } from 'os';

const __dirname = dirname(fileURLToPath(import.meta.url));

const rl = createInterface({ input: process.stdin, output: process.stdout });
const ask = (question) =>
  new Promise((res) => rl.question(`${question}: `, (a) => res(a.trim())));

// ── Region resolution ───────────────────────────────────────────────
function resolveRegion() {
  const envPath = resolve(__dirname, '../.env');
  if (existsSync(envPath)) {
    const match = readFileSync(envPath, 'utf8').match(/^AWS_REGION=(.+)$/m);
    if (match) return match[1].trim();
  }
  return 'us-west-2';
}

// ── Stage name resolution (mirrors resolveRegion pattern) ───────────
function resolveStageName() {
  const envPath = resolve(__dirname, '../.env');
  if (existsSync(envPath)) {
    const match = readFileSync(envPath, 'utf8').match(/^STAGE_NAME=(.+)$/m);
    if (match) return match[1].trim();
  }
  return 'sandbox';
}

// ── User Pool ID from CloudFormation outputs ────────────────────────
function resolveUserPoolId(region) {
  // Fix 1: construct stack name dynamically from STAGE_NAME instead of hardcoding 'sandbox'
  const stageName = resolveStageName();
  const STACK_NAME = `wealth-management-portal-infra-${stageName}-Application`;
  try {
    // Fix 2: match any OutputKey containing 'UserPoolId' — avoids fragile CDK-generated hash suffix
    const result = execSync(
      `aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${region}" --query "Stacks[0].Outputs[?contains(OutputKey,'UserPoolId')].OutputValue" --output text`,
      { stdio: ['pipe', 'pipe', 'pipe'] }
    );
    const id = result.toString().trim();
    if (!id || id === 'None') throw new Error('Output not found');
    return id;
  } catch (err) {
    throw new Error(
      `Could not resolve User Pool ID from stack "${STACK_NAME}": ${err.stderr?.toString().trim() || err.message}`
    );
  }
}

// ── Validation helpers ──────────────────────────────────────────────
const isValidEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
const isValidPassword = (v) => v.length >= 8;

async function main() {
  const args = {};
  for (const arg of process.argv.slice(2)) {
    const [key, ...rest] = arg.split('=');
    if (key.startsWith('--')) args[key.slice(2)] = rest.join('=');
  }

  console.log('\n=== Wealth Management Portal — Create Cognito User ===\n');

  const region = resolveRegion();
  console.log(`Region: ${region}`);

  let userPoolId;
  try {
    userPoolId = resolveUserPoolId(region);
    console.log(`User Pool: ${userPoolId}\n`);
  } catch (err) {
    console.error(`✗ ${err.message}`);
    rl.close();
    process.exit(1);
  }

  if (args.email && args.password) rl.close();

  // Prompt for email
  let email;
  if (args.email) {
    if (!isValidEmail(args.email)) { console.error('  \u2717 Invalid email format'); process.exit(1); }
    email = args.email;
  } else {
    while (true) {
      email = await ask('Email');
      if (isValidEmail(email)) break;
      console.log('  \u26a0 Invalid email format. Try again.');
    }
  }

  // Username must not be an email — Cognito is configured with email as alias
  const defaultUsername = email.split('@')[0];
  const username = args.username || (args.email ? defaultUsername : (await ask(`Username [${defaultUsername}]`) || defaultUsername));

  // Prompt for password
  let password;
  if (args.password) {
    if (!isValidPassword(args.password)) { console.error('  \u2717 Password must be at least 8 characters'); process.exit(1); }
    password = args.password;
  } else {
    while (true) {
      password = await ask('Password (min 8 chars)');
      if (isValidPassword(password)) break;
      console.log('  \u26a0 Password must be at least 8 characters. Try again.');
    }
  }

  if (!args.email || !args.password) rl.close();

  // Write CLI payloads to temp files instead of interpolating into shell commands.
  // This prevents shell injection — passwords with $, ", or backticks would be
  // expanded or executed if passed directly in a shell string.
  const tmpFile = join(tmpdir(), `cognito-${Date.now()}.json`);
  try {
    writeFileSync(tmpFile, JSON.stringify({
      UserPoolId: userPoolId,
      Username: username,
      UserAttributes: [
        { Name: 'email', Value: email },
        { Name: 'email_verified', Value: 'true' },
      ],
      MessageAction: 'SUPPRESS',
    }));
    execSync(
      `aws cognito-idp admin-create-user --region "${region}" --cli-input-json file://${tmpFile}`,
      { stdio: ['pipe', 'pipe', 'pipe'] }
    );
    console.log(`\n  ✓ User created: ${email}`);
  } catch (err) {
    const msg = err.stderr?.toString().trim() || err.message;
    if (msg.includes('UsernameExistsException')) {
      console.log(`\n  ⚠ User already exists: ${email}`);
    } else {
      console.error(`\n  ✗ Failed to create user: ${msg}`);
      process.exit(1);
    }
  } finally {
    try { unlinkSync(tmpFile); } catch {}
  }

  // Set permanent password (skips FORCE_CHANGE_PASSWORD flow)
  const tmpFile2 = join(tmpdir(), `cognito-pw-${Date.now()}.json`);
  try {
    writeFileSync(tmpFile2, JSON.stringify({
      UserPoolId: userPoolId,
      Username: username,
      Password: password,
      Permanent: true,
    }));
    execSync(
      `aws cognito-idp admin-set-user-password --region "${region}" --cli-input-json file://${tmpFile2}`,
      { stdio: ['pipe', 'pipe', 'pipe'] }
    );
    console.log('  ✓ Permanent password set\n');
  } catch (err) {
    const msg = err.stderr?.toString().trim() || err.message;
    if (msg.includes('InvalidPasswordException')) {
      console.error(`  ✗ Password does not meet Cognito policy: ${msg}`);
    } else {
      console.error(`  ✗ Failed to set password: ${msg}`);
    }
    process.exit(1);
  } finally {
    try { unlinkSync(tmpFile2); } catch {}
  }

  console.log(`User "${email}" is ready to sign in.\n`);
}

main().catch((err) => {
  console.error(err);
  rl.close();
  process.exit(1);
});
