// Interactive setup script — generates .env from .env.example annotations.
// No external dependencies beyond Node.js built-ins.
import { createInterface } from 'readline';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ENV_PATH = resolve(__dirname, '../.env');
const EXAMPLE_PATH = resolve(__dirname, '../.env.example');

const rl = createInterface({ input: process.stdin, output: process.stdout });
const ask = (question, defaultValue) =>
  new Promise((res) => {
    const hint = defaultValue ? ` [${defaultValue}]` : '';
    rl.question(`${question}${hint}: `, (answer) => res(answer.trim() || defaultValue || ''));
  });

// Data-platform SSM import config — resolved once on first @ssm encounter
let dataPlatformConfig = undefined; // undefined = not asked yet, null = user declined, {app, env} = enabled
let _execSync;
async function getExecSync() {
  if (!_execSync) {
    const cp = await import('child_process');
    _execSync = cp.execSync;
  }
  return _execSync;
}

/** Auto-detect data-platform APP and ENV from set-env-vars.sh */
function detectDataPlatformConfig() {
  const setEnvPath = resolve(__dirname, '../data-platform/set-env-vars.sh');
  if (!existsSync(setEnvPath)) return {};
  const content = readFileSync(setEnvPath, 'utf8');
  const rawApp = content.match(/^export APP_NAME="([^"]+)"/m)?.[1];
  const rawEnv = content.match(/^export ENV_NAME="([^"]+)"/m)?.[1];
  return {
    app: rawApp && !rawApp.startsWith('###') ? rawApp : undefined,
    env: rawEnv && !rawEnv.startsWith('###') ? rawEnv : undefined,
  };
}

/** Ask once whether to import from data-platform SSM */
async function resolveDataPlatformImport() {
  const answer = await ask('\nImport settings from data-platform SSM parameters? (yes/no)', 'no');
  if (answer.toLowerCase() !== 'yes') { dataPlatformConfig = null; return; }
  const detected = detectDataPlatformConfig();
  const app = await ask('data-platform APP name', detected.app);
  const env = await ask('data-platform ENV name', detected.env);
  if (!app || !env) {
    console.log('  ⚠ APP and ENV are required — skipping SSM import.');
    dataPlatformConfig = null;
    return;
  }
  dataPlatformConfig = { app, env };
  console.log(`  ✓ Will fetch from SSM prefix: /${app}/${env}/`);
}

/** Fetch the AWS account ID from the current credentials */
function fetchAwsAccountId() {
  try {
    const result = _execSync(
      'aws sts get-caller-identity --query Account --output text',
      { stdio: ['pipe', 'pipe', 'pipe'] }
    );
    return result.toString().trim() || null;
  } catch {
    return null;
  }
}

/** Fetch a single SSM parameter value, returns null on any failure */
function fetchSsmValue(path) {
  try {
    const result = _execSync(
      `aws ssm get-parameter --name "${path}" --with-decryption --query 'Parameter.Value' --output text`,
      { stdio: ['pipe', 'pipe', 'pipe'] }
    );
    return result.toString().trim() || null;
  } catch (e) {
    const msg = e.stderr?.toString() || '';
    if (msg.includes('AccessDeniedException') || msg.includes('kms:Decrypt')) {
      console.log(`  ⚠ Cannot decrypt SSM ${path} — check KMS permissions. Enter value manually.`);
    }
    return null;
  }
}

/** Determine section mode from header text */
function sectionMode(header) {
  if (/Required/i.test(header) && !/Deployment/i.test(header)) return 'always';
  // "Post-Deployment" is passthrough; bare "Deployment" sections are deploy-only
  if (/(?<!Post-)Deployment/i.test(header)) return 'deploy';
  return 'passthrough';
}

/** Parse .env.example into sections: [{ header, mode, lines }] */
function parseExample(text) {
  const sections = [];
  let current = { header: '', mode: 'passthrough', lines: [] };
  for (const raw of text.split('\n')) {
    const headerMatch = raw.match(/^#\s*─+\s*(.+?)\s*─+/);
    if (headerMatch) {
      sections.push(current);
      current = { header: headerMatch[1], mode: sectionMode(headerMatch[1]), lines: [] };
    }
    current.lines.push(raw);
  }
  sections.push(current);
  return sections.filter((s) => s.lines.length > 0);
}

/** Extract variable info from a (possibly commented) variable line */
function parseVarLine(line) {
  // commented: # KEY=value
  const commented = line.match(/^#\s*([A-Z_][A-Z0-9_]*)=(.*)/);
  if (commented) return { key: commented[1], value: commented[2], isCommented: true };
  // uncommented: KEY=value
  const plain = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)/);
  if (plain) return { key: plain[1], value: plain[2], isCommented: false };
  return null;
}

/** True if value is a placeholder like <...> */
const isPlaceholder = (v) => /^<.*>$/.test(v.trim());

// ── Post-run actions ────────────────────────────────────────────────
// Keyed by the name used in `# @post-run <name>` annotations.

/** Verify (or create) an SES email identity via AWS CLI */
async function verifySesIdentity(email, answers) {
  const region = answers.get('AWS_REGION') || 'us-west-2';
  const execSync = await getExecSync();

  // Check if identity already exists and is verified
  try {
    const status = execSync(
      `aws sesv2 get-email-identity --email-identity "${email}" --region "${region}" --query "VerifiedForSendingStatus" --output text`,
      { stdio: ['pipe', 'pipe', 'pipe'] }
    ).toString().trim();
    if (status === 'True') {
      console.log(`  ✅ ${email} is already verified in ${region}.`);
      return;
    }
    console.log(`  ⏳ ${email} exists but is not yet verified. Check your inbox for the verification link.`);
    return;
  } catch { /* identity does not exist — create it */ }

  try {
    execSync(
      `aws sesv2 create-email-identity --email-identity "${email}" --region "${region}"`,
      { stdio: ['pipe', 'pipe', 'pipe'] }
    );
    console.log(`  📧 Verification email sent to ${email}. Click the link in your inbox to complete setup.`);
  } catch (err) {
    console.error(`  ✗ Failed to create SES identity: ${err.stderr?.toString().trim() || err.message}`);
  }
}

const POST_RUN_ACTIONS = {
  'verify-ses-identity': verifySesIdentity,
};

// Track answers across all sections for cross-section auto-detection
const allAnswers = new Map();

/** Derive the AZ of the first private subnet via EC2 describe */
function fetchSubnetAz(subnetIds) {
  const first = subnetIds.split(',')[0].trim();
  if (!first) return null;
  try {
    const result = _execSync(
      `aws ec2 describe-subnets --subnet-ids ${first} --query "Subnets[0].AvailabilityZone" --output text`,
      { stdio: ['pipe', 'pipe', 'pipe'] }
    );
    return result.toString().trim() || null;
  } catch {
    return null;
  }
}

async function processSection(section, isDeploying, existingValues) {
  const { mode, lines } = section;
  const active = mode === 'always' || (mode === 'deploy' && isDeploying);
  const output = [];
  let pendingPrompt = null;
  let pendingSkipIf = null;
  let pendingSsm = null;
  let pendingSsmPrefix = null;
  let pendingPostRun = null;
  // Track answers within this section for @skip-if evaluation
  const answers = new Map();

  for (const line of lines) {
    if (/^#\s*@prompt\s+/.test(line)) {
      pendingPrompt = line.replace(/^#\s*@prompt\s+/, '');
      continue; // consume annotation, don't emit it
    }

    // Consume @skip-if annotation
    const skipMatch = line.match(/^#\s*@skip-if\s+([A-Z_][A-Z0-9_]*)=(.+)/);
    if (skipMatch) {
      pendingSkipIf = { key: skipMatch[1], value: skipMatch[2].trim() };
      continue;
    }

    // Consume @ssm annotation
    const ssmMatch = line.match(/^#\s*@ssm\s+(\S+)/);
    if (ssmMatch) {
      pendingSsm = ssmMatch[1];
      continue;
    }

    // Consume @ssm-prefix annotation
    const ssmPrefixMatch = line.match(/^#\s*@ssm-prefix\s+(\S+)/);
    if (ssmPrefixMatch) {
      pendingSsmPrefix = ssmPrefixMatch[1];
      continue;
    }

    // Consume @post-run annotation
    const postRunMatch = line.match(/^#\s*@post-run\s+(\S+)/);
    if (postRunMatch) {
      pendingPostRun = postRunMatch[1];
      continue;
    }

    if (!active || pendingPrompt === null) {
      output.push(line);
      pendingPrompt = null;
      pendingSkipIf = null;
      pendingSsm = null;
      pendingSsmPrefix = null;
      pendingPostRun = null;
      continue;
    }

    // Active section with a pending @prompt — interact
    const info = parseVarLine(line);
    if (!info) {
      output.push(line);
      pendingPrompt = null;
      pendingSkipIf = null;
      pendingSsm = null;
      pendingSsmPrefix = null;
      pendingPostRun = null;
      continue;
    }

    // Check @skip-if condition — omit this variable entirely if met
    if (pendingSkipIf && answers.get(pendingSkipIf.key) === pendingSkipIf.value) {
      pendingPrompt = null;
      pendingSkipIf = null;
      pendingSsm = null;
      pendingSsmPrefix = null;
      pendingPostRun = null;
      continue;
    }
    pendingSkipIf = null;

    // Resolve SSM default if annotation present
    let ssmDefault = null;
    if (pendingSsm) {
      if (dataPlatformConfig === undefined) {
        await resolveDataPlatformImport();
        await getExecSync();
      }
      if (dataPlatformConfig) {
        const path = pendingSsm
          .replace('{APP}', dataPlatformConfig.app)
          .replace('{ENV}', dataPlatformConfig.env);
        const fetched = fetchSsmValue(path);
        if (fetched) ssmDefault = (pendingSsmPrefix || '') + fetched;
      }
    }
    pendingSsm = null;
    pendingSsmPrefix = null;

    const exampleDefault = (!info.isCommented && !isPlaceholder(info.value)) ? info.value : '';
    // Auto-detect well-known values from AWS APIs
    let autoDefault = null;
    if (info.key === 'AWS_ACCOUNT_ID') {
      await getExecSync();
      autoDefault = fetchAwsAccountId();
    } else if (info.key === 'PRIVATE_SUBNET_AZ') {
      const subnets = allAnswers.get('PRIVATE_SUBNET_IDS');
      if (subnets) { await getExecSync(); autoDefault = fetchSubnetAz(subnets); }
    }
    const defaultVal = ssmDefault ?? autoDefault ?? existingValues.get(info.key) ?? exampleDefault;
    const answer = await ask(pendingPrompt, defaultVal);
    pendingPrompt = null;

    if (answer === '') {
      // User skipped — write commented form
      const commentedLine = info.isCommented ? line : `# ${line}`;
      output.push(commentedLine);
    } else {
      output.push(`${info.key}=${answer}`);
      answers.set(info.key, answer);
      allAnswers.set(info.key, answer);

      // Run post-action if annotated
      if (pendingPostRun && POST_RUN_ACTIONS[pendingPostRun]) {
        await POST_RUN_ACTIONS[pendingPostRun](answer, answers);
      }
    }
    pendingPostRun = null;
  }

  return output;
}

async function main() {
  console.log('\n=== Wealth Management Portal — Environment Setup ===\n');

  let existingValues = new Map();
  if (existsSync(ENV_PATH)) {
    const overwrite = await ask('.env already exists. Overwrite? (yes/no)', 'no');
    if (overwrite.toLowerCase() !== 'yes') {
      console.log('Aborted. Existing .env was not modified.');
      rl.close();
      return;
    }
    existingValues = new Map(
      readFileSync(ENV_PATH, 'utf8').split('\n')
        .filter((l) => l.trim() && !l.startsWith('#'))
        .map((l) => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; })
    );
  }

  const example = readFileSync(EXAMPLE_PATH, 'utf8');
  const sections = parseExample(example);

  const deployAnswer = await ask('\nAre you setting up for deployment? (yes/no)', 'no');
  const isDeploying = deployAnswer.toLowerCase() === 'yes';

  const outputLines = [];
  for (const section of sections) {
    const lines = await processSection(section, isDeploying, existingValues);
    outputLines.push(...lines);
  }

  // Trim trailing blank lines then add single newline
  const content = outputLines.join('\n').trimEnd() + '\n';
  writeFileSync(ENV_PATH, content);

  console.log(`\n✓ .env written to ${ENV_PATH}`);

  // Offer to create SSM parameters for CI pipeline
  if (isDeploying) {
    await maybeCreateSsmParams();
  }

  console.log('\nNext steps:');
  console.log('  Local dev:  pnpm nx serve-local @wealth-management-portal/ui');
  console.log('  Deploy:     pnpm nx deploy @wealth-management-portal/infra\n');

  rl.close();
}

// Env var → SSM parameter path mapping (must match ci-stack.ts)
const SSM_PARAMS = {
  AWS_REGION: '/wealth-management-portal/aws-region',
  REDSHIFT_VPC_ID: '/wealth-management-portal/redshift-vpc-id',
  PRIVATE_SUBNET_IDS: '/wealth-management-portal/private-subnet-ids',
  REDSHIFT_SECURITY_GROUP_ID: '/wealth-management-portal/redshift-security-group-id',
  PRIVATE_ROUTE_TABLE_ID: '/wealth-management-portal/private-route-table-id',
  REDSHIFT_WORKGROUP: '/wealth-management-portal/redshift-workgroup',
  REDSHIFT_DATABASE: '/wealth-management-portal/redshift-database',
  SES_SENDER_EMAIL: '/wealth-management-portal/ses-sender-email',
  REPORT_BEDROCK_MODEL_ID: '/wealth-management-portal/report-bedrock-model-id',
  TAVILY_API_KEY: '/wealth-management-portal/tavily-api-key',
  THEME_BEDROCK_MODEL_ID: '/wealth-management-portal/theme-bedrock-model-id',
  DEPLOY_BASTION: '/wealth-management-portal/deploy-bastion',
  PRIVATE_SUBNET_AZ: '/wealth-management-portal/private-subnet-az',
  ENABLE_COMPLIANCE_REPORTING: '/wealth-management-portal/enable-compliance-reporting',
  COMPLIANCE_REPORTING_BUCKET: '/wealth-management-portal/compliance-reporting-bucket',
};

/** Read the just-written .env and create SSM parameters for CI */
async function maybeCreateSsmParams() {
  const setupCi = await ask('\nCreate SSM parameters for CI pipeline? (yes/no)', 'no');
  if (setupCi.toLowerCase() !== 'yes') return;

  // Parse the .env we just wrote
  const envValues = new Map(
    readFileSync(ENV_PATH, 'utf8').split('\n')
      .filter((l) => l.trim() && !l.startsWith('#'))
      .map((l) => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; })
  );

  const { execSync } = await import('child_process');
  let created = 0;

  for (const [envKey, ssmPath] of Object.entries(SSM_PARAMS)) {
    const value = envValues.get(envKey);
    if (!value || isPlaceholder(value)) continue;

    // SecureString for secrets, String for everything else
    const type = envKey === 'TAVILY_API_KEY' ? 'SecureString' : 'String';
    try {
      execSync(
        `aws ssm put-parameter --name "${ssmPath}" --value "${value}" --type ${type} --overwrite`,
        { stdio: 'pipe' }
      );
      console.log(`  ✓ ${ssmPath}`);
      created++;
    } catch (err) {
      console.error(`  ✗ ${ssmPath}: ${err.stderr?.toString().trim() || err.message}`);
    }
  }

  console.log(`\n${created} SSM parameter(s) created/updated.`);
}

main().catch((err) => {
  console.error(err);
  rl.close();
  process.exit(1);
});
