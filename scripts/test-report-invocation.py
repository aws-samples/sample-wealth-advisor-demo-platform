"""Invoke the deployed report agent to validate end-to-end report generation.

Calls /invocations with a real client ID, then verifies:
1. The response contains report_id, s3_path, status
2. The PDF exists in S3
3. The record exists in the client_reports Redshift table

Usage:
    python scripts/test-report-invocation.py --stack-name <CFN_STACK> --client-id <CLIENT_ID>
"""

import argparse
import json
import os
import signal
import time
import uuid

import boto3
import botocore.config
import botocore.exceptions

# Hard wall-clock timeout for the entire invocation
INVOKE_TIMEOUT_SECONDS = 660


def discover_runtime(cfn, stack_name: str) -> str:
    """Find the ReportAgent AgentCore runtime ARN from stack resources."""
    sts = boto3.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    region = cfn.meta.region_name

    paginator = cfn.get_paginator("list_stack_resources")
    for page in paginator.paginate(StackName=stack_name):
        for r in page["StackResourceSummaries"]:
            # Match only the ReportAgent runtime, not other runtimes in the stack
            if r["ResourceType"] == "AWS::BedrockAgentCore::Runtime" and "ReportAgent" in r["LogicalResourceId"]:
                runtime_id = r["PhysicalResourceId"]
                return f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{runtime_id}"
    raise RuntimeError(f"No ReportAgent AgentCore Runtime found in stack {stack_name}")


def discover_s3_bucket(agentcore_ctrl, runtime_id: str) -> str:
    """Get the REPORT_S3_BUCKET env var from the runtime config."""
    resp = agentcore_ctrl.get_agent_runtime(agentRuntimeId=runtime_id)
    return resp["environmentVariables"]["REPORT_S3_BUCKET"]


def _read_dotenv(key: str) -> str | None:
    """Read a value from the .env file at the repo root."""
    env_path = os.path.join(os.path.dirname(__file__), os.pardir, ".env")
    if not os.path.isfile(env_path):
        return None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return None


def discover_redshift_config(cfn, stack_name: str) -> tuple[str, str]:
    """Find Redshift workgroup and database from stack outputs, falling back to .env."""
    resp = cfn.describe_stacks(StackName=stack_name)
    outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
    workgroup = outputs.get("RedshiftWorkgroup") or _read_dotenv("REDSHIFT_WORKGROUP")
    database = outputs.get("RedshiftDatabase") or _read_dotenv("REDSHIFT_DATABASE") or "dev"
    if not workgroup:
        raise RuntimeError(
            "Cannot determine Redshift workgroup: not in stack outputs and REDSHIFT_WORKGROUP not set in .env"
        )
    return workgroup, database


def invoke_report_agent(agentcore, runtime_arn: str, client_id: str) -> dict:
    """Call the report agent /invocations endpoint via AgentCore runtime."""
    payload = json.dumps({"client_id": client_id})
    session_id = f"report-test-{uuid.uuid4().hex}"

    print(f"Invoking report agent for client {client_id}...")
    print(f"Session ID: {session_id}")
    print(f"Invoking report agent (timeout: {INVOKE_TIMEOUT_SECONDS}s)...")

    response = agentcore.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=session_id,
        payload=payload,
    )
    return json.loads(response["response"].read())


def verify_s3(s3, bucket: str, key: str) -> bool:
    """Check that the PDF exists in S3."""
    try:
        resp = s3.head_object(Bucket=bucket, Key=key)
        print(f"  S3 object exists: s3://{bucket}/{key} ({resp['ContentLength'] / 1024:.1f} KB)")
        return True
    except s3.exceptions.ClientError:
        print(f"  S3 object NOT found: s3://{bucket}/{key}")
        return False


def verify_redshift(rs_data, workgroup: str, database: str, report_id: str) -> bool:
    """Check that the report record exists in client_reports."""
    exec_resp = rs_data.execute_statement(
        WorkgroupName=workgroup,
        Database=database,
        Sql=f"SELECT report_id, client_id, s3_path, status, next_best_action FROM public.client_reports WHERE report_id = '{report_id}'",
    )
    stmt_id = exec_resp["Id"]

    # Poll until the statement finishes
    while True:
        desc = rs_data.describe_statement(Id=stmt_id)
        status = desc["Status"]
        if status in ("FINISHED", "FAILED", "ABORTED"):
            break
        time.sleep(1)

    if status != "FINISHED":
        print(f"  Redshift query {status}: {desc.get('Error', 'unknown error')}")
        return False

    rows = rs_data.get_statement_result(Id=stmt_id).get("Records", [])
    if rows:
        print(f"  Redshift record found: {rows[0]}")
        # Check NBA column (5th field)
        nba_field = rows[0][4] if len(rows[0]) > 4 else None
        nba_value = nba_field.get("stringValue") if isinstance(nba_field, dict) else None
        if nba_value:
            print(f"  Next Best Action: {nba_value}")
        else:
            print("  ⚠ Next Best Action is NULL")
        return True
    print(f"  Redshift record NOT found for report_id={report_id}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Validate report agent end-to-end")
    parser.add_argument("--stack-name", required=True, help="CloudFormation stack name")
    parser.add_argument("--client-id", default="CL00014", help="Client ID to generate report for")
    args = parser.parse_args()

    region = boto3.session.Session().region_name or "us-west-2"
    cfn = boto3.client("cloudformation", region_name=region)
    agentcore_ctrl = boto3.client("bedrock-agentcore-control", region_name=region)
    agentcore = boto3.client("bedrock-agentcore", region_name=region, config=botocore.config.Config(read_timeout=600))
    s3 = boto3.client("s3", region_name=region)
    rs_data = boto3.client("redshift-data", region_name=region)

    # Discover resources from the stack
    print(f"Discovering resources from stack: {args.stack_name}")
    runtime_arn = discover_runtime(cfn, args.stack_name)
    runtime_id = runtime_arn.rsplit("/", 1)[-1]
    s3_bucket = discover_s3_bucket(agentcore_ctrl, runtime_id)
    workgroup, database = discover_redshift_config(cfn, args.stack_name)

    print(f"  Runtime ARN:  {runtime_arn}")
    print(f"  S3 Bucket:    {s3_bucket}")
    print(f"  Redshift:     {workgroup}/{database}")

    # Hard timeout — os._exit kills the process even when blocked in C-level I/O
    def timeout_handler(signum, frame):
        print(f"\n❌ Report agent invocation timed out after {INVOKE_TIMEOUT_SECONDS}s")
        os._exit(1)

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(INVOKE_TIMEOUT_SECONDS)

    try:
        # Step 1: Invoke the agent
        response = invoke_report_agent(agentcore, runtime_arn, args.client_id)
        signal.alarm(0)  # Cancel alarm
        print(f"\nAgent response: {json.dumps(response, indent=2)}")

        report_id = response.get("report_id")
        s3_path = response.get("s3_path")
        status = response.get("status")

        # Step 2: Validate response
        print("\n--- Validation ---")
        assert report_id, "Missing report_id in response"
        assert s3_path, "Missing s3_path in response"
        assert status == "complete", f"Expected status 'complete', got '{status}'"
        print(f"  Response fields OK (report_id={report_id}, status={status})")

        # Step 3: Verify S3 and Redshift
        s3_ok = verify_s3(s3, s3_bucket, s3_path)
        rs_ok = verify_redshift(rs_data, workgroup, database, report_id)

        # Summary
        print("\n--- Summary ---")
        print(f"  Agent invocation: PASS")
        print(f"  S3 PDF upload:    {'PASS' if s3_ok else 'FAIL'}")
        print(f"  Redshift record:  {'PASS' if rs_ok else 'FAIL'}")
        print(f"\n{'✅ End-to-end validation PASSED' if s3_ok and rs_ok else '❌ End-to-end validation FAILED'}")
        if not (s3_ok and rs_ok):
            exit(1)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
