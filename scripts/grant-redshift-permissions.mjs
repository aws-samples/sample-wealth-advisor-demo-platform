// Grants Redshift SELECT on all public tables/views to all Lambda IAM roles.
// Runs as the admin superuser via Secrets Manager auth so grants cover
// objects owned by any user (e.g., views created by datapipeline).
// Run after both CDK deploy and deploy-redshift-ddl.
import { existsSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DRY_RUN = process.argv.includes('--dry-run');
// --self: skip ROLE_PATTERNS discovery and grant to the caller's own IAM role instead
const SELF = process.argv.includes('--self');

// IAM role name prefixes for Lambda functions that need Redshift access
const ROLE_PATTERNS = [
  'ApiRouterHandlerServiceRo',
  'PortfolioGatewayHandlerSe',
  'SmartChatDataAccessHandle',
  'RedshiftDataAccessExecuti',
  'GetClientListServiceRole',
  'GenerateGeneralThemesServ',
  'GeneratePortfolioThemesSe',
];

function resolveEnv(key) {
  const envPath = resolve(__dirname, '../.env');
  if (existsSync(envPath)) {
    const match = readFileSync(envPath, 'utf8').match(new RegExp(`^${key}=(.+)$`, 'm'));
    if (match) return match[1].trim();
  }
  return undefined;
}

function exec(cmd) {
  return execSync(cmd, { stdio: ['pipe', 'pipe', 'pipe'] }).toString().trim();
}

// Converts an STS assumed-role ARN to the underlying IAM role ARN.
// arn:aws:sts::ACCOUNT:assumed-role/ROLE/SESSION → arn:aws:iam::ACCOUNT:role/ROLE
function stsArnToIamArn(arn) {
  return arn.replace(/:sts:/, ':iam:').replace(/assumed-role\/([^/]+)\/.*/, 'role/$1');
}

function findRoles(region, patterns) {
  const found = [];
  for (const pattern of patterns) {
    try {
      const raw = exec(
        `aws iam list-roles --region "${region}" --query "Roles[?contains(RoleName,'${pattern}')].{name:RoleName,arn:Arn}" --output json`,
      );
      const roles = JSON.parse(raw);
      if (roles.length === 0) {
        console.warn(`  ⚠ No role found matching pattern: ${pattern}`);
      } else {
        found.push(...roles);
      }
    } catch (err) {
      console.warn(`  ⚠ Error searching for pattern "${pattern}": ${err.stderr?.toString().trim() || err.message}`);
    }
  }
  return found;
}

function findAdminSecret(region, workgroup) {
  // Look up the namespace and verify managed admin password is enabled
  const nsRaw = exec(
    `aws redshift-serverless get-workgroup --workgroup-name "${workgroup}" --region "${region}" --query "workgroup.namespaceName" --output text`,
  );
  const secretArn = exec(
    `aws redshift-serverless get-namespace --namespace-name "${nsRaw}" --region "${region}" --query "namespace.adminPasswordSecretArn" --output text`,
  );
  // adminPasswordSecretArn is only present when managed admin password is enabled
  if (!secretArn || secretArn === 'None') {
    throw new Error('Managed admin password is not enabled on this namespace');
  }
  return secretArn;
}

function executeAsAdmin(region, workgroup, database, secretArn, sql) {
  const stmtId = exec(
    `aws redshift-data execute-statement --workgroup-name "${workgroup}" --database "${database}" --secret-arn "${secretArn}" --sql '${sql.replace(/'/g, "'\\''")}' --region "${region}" --query Id --output text`,
  );
  // Wait for completion
  for (let i = 0; i < 30; i++) {
    const status = exec(
      `aws redshift-data describe-statement --id "${stmtId}" --region "${region}" --query Status --output text`,
    );
    if (status === 'FINISHED') return;
    if (status === 'FAILED') {
      const error = exec(
        `aws redshift-data describe-statement --id "${stmtId}" --region "${region}" --query Error --output text`,
      );
      throw new Error(error);
    }
    execSync('sleep 2');
  }
  throw new Error('Statement timed out');
}

async function main() {
  console.log(`\n=== Wealth Management Portal — Grant Redshift Permissions${DRY_RUN ? ' [DRY RUN]' : ''} ===\n`);

  const region = resolveEnv('AWS_REGION') ?? 'us-west-2';
  const workgroup = resolveEnv('REDSHIFT_WORKGROUP');
  const database = resolveEnv('REDSHIFT_DATABASE') ?? 'dev';

  if (!workgroup) {
    console.error('✗ REDSHIFT_WORKGROUP not set in .env');
    process.exit(1);
  }

  console.log(`Region:    ${region}`);
  console.log(`Workgroup: ${workgroup}`);
  console.log(`Database:  ${database}\n`);

  // Find admin secret — requires managed admin password on the namespace
  console.log('Looking up Redshift admin secret...');
  let secretArn;
  try {
    secretArn = findAdminSecret(region, workgroup);
  } catch (err) {
    // No managed admin secret → pre-existing environment; skip gracefully
    console.warn(`⚠ No managed admin secret found — skipping Redshift grants.`);
    console.warn(`  (Enable managed admin password on the namespace to use this step.)`);
    console.warn(`  Detail: ${err.message}`);
    process.exit(0);
  }
  console.log(`Secret:    ${secretArn}\n`);

  // Discover roles — or resolve caller's own role when --self is passed
  console.log('Discovering IAM roles...');
  let roles;
  if (SELF) {
    const callerArn = exec(`aws sts get-caller-identity --region "${region}" --query Arn --output text`);
    const iamArn = stsArnToIamArn(callerArn);
    // Extract role name from arn:aws:iam::ACCOUNT:role/ROLE_NAME
    const name = iamArn.split('/').pop();
    roles = [{ name, arn: iamArn }];
    console.log(`  (--self) Resolved to: ${iamArn}`);
  } else {
    roles = findRoles(region, ROLE_PATTERNS);
  }

  if (roles.length === 0) {
    console.error('\n✗ No matching roles found. Has CDK been deployed?');
    process.exit(1);
  }

  console.log(`\nFound ${roles.length} role(s):\n`);
  for (const r of roles) {
    console.log(`  ${r.name}`);
  }

  if (DRY_RUN) {
    console.log('\n[DRY RUN] Would run as admin for each role:');
    console.log('  GRANT USAGE ON SCHEMA public TO "IAMR:<role>";');
    console.log('  GRANT SELECT ON ALL TABLES IN SCHEMA public TO "IAMR:<role>";');
    console.log('  + GRANT INSERT, UPDATE, DELETE ON public.client_reports, public.articles, public.themes, public.theme_article_associations (PortfolioGateway only)');
    console.log('\nRe-run without --dry-run to apply.\n');
    return;
  }

  // Apply grants as admin superuser
  console.log('\nApplying Redshift grants as admin...\n');
  let ok = 0;
  let failed = 0;
  for (const r of roles) {
    const user = `IAMR:${r.name}`;
    process.stdout.write(`  Granting → ${user} ... `);
    try {
      // Create user if missing (ignore error if already exists)
      try {
        executeAsAdmin(region, workgroup, database, secretArn, `CREATE USER "${user}" PASSWORD DISABLE`);
      } catch (e) {
        if (!e.message.includes('already exists')) throw e;
      }
      let sql =
        `GRANT USAGE ON SCHEMA public TO "${user}"; ` +
        `GRANT SELECT ON ALL TABLES IN SCHEMA public TO "${user}";`;
      // PortfolioGateway needs write access to client_reports, articles, themes, and associations
      if (r.name.includes('PortfolioGatewayHandlerSe')) {
        sql += ` GRANT INSERT, UPDATE, DELETE ON public.client_reports, public.articles, public.themes, public.theme_article_associations TO "${user}";`;
      }
      executeAsAdmin(region, workgroup, database, secretArn, sql);
      console.log('✓');
      ok++;
    } catch (err) {
      console.log(`✗\n    ${err.message}`);
      failed++;
    }
  }

  console.log(`\n${ok} role(s) granted, ${failed} failed.\n`);
  if (failed > 0) process.exit(1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
