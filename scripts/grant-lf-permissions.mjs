// Grants Lake Formation permissions to all Redshift-consuming IAM roles.
// Replaces the manual bash loop in README Step 3b.
// Run after CDK deploy. Caller must be a Lake Formation admin.
import { existsSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DRY_RUN = process.argv.includes('--dry-run');
// --self: skip ROLE_PATTERNS discovery and grant to the caller's own IAM role instead
const SELF = process.argv.includes('--self');

const S3_TABLE_CATALOG = 'financial-advisor-s3table';
const LF_DATABASE = 'financial_advisor';

// IAM role name prefixes to search for (CDK truncates role names)
const ROLE_PATTERNS = [
  'ApiRouterHandlerServiceRo',
  'PortfolioGatewayHandlerSe',
  'SmartChatDataAccessHandle',
  'RedshiftDataAccessExecuti',
  'GetClientListServiceRole',
  'GenerateGeneralThemesServ',
  'GeneratePortfolioThemesSe',
  // Redshift namespace role (created by DataZone/SageMaker environment blueprint)
  'datazone_usr_role',
];

function resolveRegion() {
  const envPath = resolve(__dirname, '../.env');
  if (existsSync(envPath)) {
    const match = readFileSync(envPath, 'utf8').match(/^AWS_REGION=(.+)$/m);
    if (match) return match[1].trim();
  }
  return 'us-west-2';
}

function exec(cmd) {
  return execSync(cmd, { stdio: ['pipe', 'pipe', 'pipe'] }).toString().trim();
}

function getAccountId(region) {
  return exec(`aws sts get-caller-identity --region "${region}" --query Account --output text`);
}

function getCallerArn(region) {
  return exec(`aws sts get-caller-identity --region "${region}" --query Arn --output text`);
}

function checkLfAdmin(region, callerArn) {
  const raw = exec(`aws lakeformation get-data-lake-settings --region "${region}" --query "DataLakeSettings.DataLakeAdmins" --output json`);
  const admins = JSON.parse(raw);
  // Match by full ARN or by assumed-role base ARN (strip session suffix for assumed roles)
  const baseArn = callerArn.replace(/:sts:/, ':iam:').replace(/assumed-role\/([^/]+)\/.*/, 'role/$1');
  return admins.some((a) => a.DataLakePrincipalIdentifier === callerArn || a.DataLakePrincipalIdentifier === baseArn);
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
        `aws iam list-roles --region "${region}" --query "Roles[?contains(RoleName,'${pattern}')].Arn" --output json`
      );
      const arns = JSON.parse(raw);
      if (arns.length === 0) {
        console.warn(`  ⚠ No role found matching pattern: ${pattern}`);
      } else {
        found.push(...arns);
      }
    } catch (err) {
      console.warn(`  ⚠ Error searching for pattern "${pattern}": ${err.stderr?.toString().trim() || err.message}`);
    }
  }
  return found;
}

function grantPermissions(region, roleArn, catalogId, parentCatalogId) {
  const principal = `DataLakePrincipalIdentifier=${roleArn}`;

  // 0. DESCRIBE on parent s3tablescatalog catalog (required for hierarchy traversal)
  exec(
    `aws lakeformation grant-permissions --region "${region}" ` +
    `--principal "${principal}" ` +
    `--resource '{"Catalog": {"Id": "${parentCatalogId}"}}' ` +
    `--permissions DESCRIBE`
  );

  // 1. DESCRIBE on sub-catalog (table bucket)
  exec(
    `aws lakeformation grant-permissions --region "${region}" ` +
    `--principal "${principal}" ` +
    `--resource '{"Catalog": {"Id": "${catalogId}"}}' ` +
    `--permissions DESCRIBE`
  );

  // 2. DESCRIBE on database
  exec(
    `aws lakeformation grant-permissions --region "${region}" ` +
    `--principal "${principal}" ` +
    `--resource '{"Database": {"CatalogId": "${catalogId}", "Name": "${LF_DATABASE}"}}' ` +
    `--permissions DESCRIBE`
  );

  // 3. SELECT + DESCRIBE on all tables (wildcard)
  exec(
    `aws lakeformation grant-permissions --region "${region}" ` +
    `--principal "${principal}" ` +
    `--resource '{"Table": {"CatalogId": "${catalogId}", "DatabaseName": "${LF_DATABASE}", "TableWildcard": {}}}' ` +
    `--permissions SELECT DESCRIBE`
  );
}

async function main() {
  console.log(`\n=== Wealth Management Portal — Grant Lake Formation Permissions${DRY_RUN ? ' [DRY RUN]' : ''} ===\n`);

  const region = resolveRegion();
  console.log(`Region:  ${region}`);

  const accountId = getAccountId(region);
  console.log(`Account: ${accountId}`);

  const catalogId = `${accountId}:s3tablescatalog/${S3_TABLE_CATALOG}`;
  const parentCatalogId = `${accountId}:s3tablescatalog`;
  console.log(`Catalog: ${catalogId}`);
  console.log(`Parent:  ${parentCatalogId}`);
  console.log(`DB:      ${LF_DATABASE}\n`);

  // Verify caller is LF admin
  const callerArn = getCallerArn(region);
  console.log(`Caller:  ${callerArn}`);
  let isAdmin = false;
  try {
    isAdmin = checkLfAdmin(region, callerArn);
  } catch (err) {
    console.error(`\n✗ Could not verify LF admin status: ${err.stderr?.toString().trim() || err.message}`);
    console.error('  Ensure you have lakeformation:GetDataLakeSettings permission.');
    process.exit(1);
  }
  if (!isAdmin) {
    if (SELF) {
      // Auto-promote caller to LF admin so the grant can proceed
      const iamArn = stsArnToIamArn(callerArn);
      console.log(`  (--self) Adding ${iamArn} as Lake Formation admin...`);
      const raw = exec(`aws lakeformation get-data-lake-settings --region "${region}" --output json`);
      const settings = JSON.parse(raw);
      settings.DataLakeSettings.DataLakeAdmins.push({ DataLakePrincipalIdentifier: iamArn });
      exec(
        `aws lakeformation put-data-lake-settings --region "${region}" --cli-input-json '${JSON.stringify({ DataLakeSettings: settings.DataLakeSettings })}'`
      );
      console.log('  ✓ Added as LF admin');
    } else {
      console.error('\n✗ Current principal is NOT a Lake Formation admin.');
      console.error('  To fix: add this principal as an LF admin in the AWS Console or via:');
      console.error(`  aws lakeformation put-data-lake-settings --region ${region} ...`);
      console.error('  Or run this script as the datapipeline IAM user / Admin role from Phase 1.');
      process.exit(1);
    }
  }
  console.log('✓ LF admin check passed\n');

  // Discover roles — or resolve caller's own role when --self is passed
  console.log('Discovering IAM roles...');
  let roleArns;
  if (SELF) {
    roleArns = [stsArnToIamArn(callerArn)];
    console.log(`  (--self) Resolved to: ${roleArns[0]}`);
  } else {
    roleArns = findRoles(region, ROLE_PATTERNS);
  }

  if (roleArns.length === 0) {
    console.error('\n✗ No matching roles found. Has CDK been deployed?');
    process.exit(1);
  }

  console.log(`\nFound ${roleArns.length} role(s):\n`);
  for (const arn of roleArns) {
    console.log(`  ${arn}`);
  }

  if (DRY_RUN) {
    console.log('\n[DRY RUN] Would grant DESCRIBE on catalog, DESCRIBE on database,');
    console.log(`          and SELECT+DESCRIBE on all tables in "${LF_DATABASE}" for each role above.`);
    console.log('\nRe-run without --dry-run to apply grants.\n');
    return;
  }

  // Apply grants
  console.log('\nApplying Lake Formation grants...\n');
  let ok = 0;
  let failed = 0;
  for (const roleArn of roleArns) {
    process.stdout.write(`  Granting → ${roleArn} ... `);
    try {
      grantPermissions(region, roleArn, catalogId, parentCatalogId);
      console.log('✓');
      ok++;
    } catch (err) {
      const msg = err.stderr?.toString().trim() || err.message;
      console.log(`✗\n    ${msg}`);
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
