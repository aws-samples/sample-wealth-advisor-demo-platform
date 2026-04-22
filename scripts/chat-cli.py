"""
Advisor Chat CLI — Step 7.1 (Interactive REPL) and Step 7.2 (Automated E2E).

Usage (run from packages/advisor_chat):
  cd packages/advisor_chat && uv run python ../../scripts/chat-cli.py
  cd packages/advisor_chat && uv run python ../../scripts/chat-cli.py --e2e
  cd packages/advisor_chat && uv run python ../../scripts/chat-cli.py --e2e-attachment
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from uuid import uuid4

# Resolve project root and advisor_chat package directory
_project_root = Path(__file__).resolve().parent.parent
_advisor_chat_dir = _project_root / "packages" / "advisor_chat"

# Add advisor_chat package dir to sys.path so the module is importable
# (the editable install .pth file may be empty when running scripts outside the package dir)
sys.path.insert(0, str(_advisor_chat_dir))

# Load .env from project root before any other imports
from dotenv import load_dotenv

load_dotenv(_project_root / ".env")

from wealth_management_portal_advisor_chat.routing_agent.agent import create_agent, current_user_id  # noqa: E402

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

USER_ID = "cli-test-user"


def strip_thinking(text: str) -> str:
    """Remove <thinking>...</thinking> blocks from agent responses."""
    return re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL).strip()


def ask(agent, message: str, verbose: bool = False) -> str:
    """Send a message to the agent and return clean text."""
    current_user_id.set(USER_ID)
    result = agent(message)
    response = strip_thinking(str(result))
    if verbose:
        print(f"{DIM}{response}{RESET}")
    return response


# ---------------------------------------------------------------------------
# Step 7.1 — Interactive REPL
# ---------------------------------------------------------------------------

BANNER = f"""
{BOLD}╔══════════════════════════════════════════════════════╗
║       Wealth Management Advisor Chat CLI             ║
╚══════════════════════════════════════════════════════╝{RESET}

{YELLOW}Manual test scenarios:{RESET}
  1. Schedule a daily market summary at 4pm, email to <your-email>
  2. List my schedules
  3. Pause that schedule
  4. Resume that schedule
  5. Delete schedule <schedule_id>

Type {BOLD}exit{RESET} or press Ctrl+C / Ctrl+D to quit.
"""


def _cli_callback(**kwargs):
    """Streaming callback — prints text chunks and tool calls as they happen."""
    # Tool call started
    tool = kwargs.get("event", {}).get("contentBlockStart", {}).get("start", {}).get("toolUse")
    if tool:
        print(f"\n  {YELLOW}⚡ calling {tool['name']}...{RESET}", flush=True)
    # Text chunk — stream in dim so final answer stands out
    data = kwargs.get("data")
    if data:
        print(f"{DIM}{data}{RESET}", end="", flush=True)
    # Final chunk
    if kwargs.get("complete"):
        print()


def run_repl() -> None:
    print(BANNER)
    # Unique session ID per REPL run — isolates memory from prior sessions
    session_id = f"cli-repl-{uuid4().hex[:8]}"
    print(f"  {YELLOW}session: {session_id}{RESET}\n")
    agent = create_agent(session_id=session_id)
    agent.callback_handler = _cli_callback
    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        if not user_input or user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        print()
        current_user_id.set(USER_ID)
        result = agent(user_input)
        # Print final consolidated response in cyan
        final = strip_thinking(str(result)) if result else ""
        if final:
            print(f"\n{CYAN}{BOLD}Agent:{RESET} {CYAN}{final}{RESET}\n")
        else:
            print()


# ---------------------------------------------------------------------------
# Step 7.2 — Automated E2E
# ---------------------------------------------------------------------------

import boto3  # noqa: E402


def _dynamo_query_gsi1(table_name: str, schedule_id: str, region: str) -> list:
    """Query DynamoDB GSI1 for a schedule."""
    table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    resp = table.query(
        IndexName="GSI1",
        KeyConditionExpression="GSI1PK = :pk",
        ExpressionAttributeValues={":pk": f"SCHEDULE#{schedule_id}"},
    )
    return resp.get("Items", [])


def _get_eb_schedule(schedule_id: str, region: str) -> dict:
    """Get EventBridge schedule state."""
    client = boto3.client("scheduler", region_name=region)
    return client.get_schedule(Name=f"user-schedule-{schedule_id}", GroupName="default")


def step_create(agent, ses_email: str, table_name: str, region: str) -> tuple[bool, str, str]:
    """Step 1: Create a schedule, then find the schedule_id from DynamoDB."""
    response = ask(agent, f"Schedule daily oil price details at 4pm, email to {ses_email}", verbose=True)

    # Try extracting UUID from agent response first
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", response, re.IGNORECASE)
    if match:
        return True, match.group(0), response[:200]

    # Agent summarized without the ID — query DynamoDB for the user's schedules
    table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    resp = table.query(
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": f"USER#{USER_ID}"},
        ScanIndexForward=False,
    )
    items = resp.get("Items", [])
    if not items:
        return False, "", f"Agent responded but no schedules found in DynamoDB: {response[:200]}"
    # Pick the most recently created schedule
    latest = max(items, key=lambda i: i.get("created_at", ""))
    sid = latest["schedule_id"]
    return True, sid, f"Found via DynamoDB lookup: {sid}"


def step_verify_dynamo_create(schedule_id: str, table_name: str, region: str) -> tuple[bool, str]:
    """Step 2: Verify schedule exists in DynamoDB with enabled=True and a cron expression."""
    items = _dynamo_query_gsi1(table_name, schedule_id, region)
    if not items:
        return False, "No items found in DynamoDB"
    item = items[0]
    if not item.get("enabled", False):
        return False, f"enabled={item.get('enabled')}, expected True"
    cron = item.get("cron_expression", "")
    if "cron(" not in cron and "rate(" not in cron:
        return False, f"cron_expression missing cron/rate: {cron!r}"
    return True, f"enabled=True, cron={cron!r}"


def step_verify_eb_enabled(schedule_id: str, region: str) -> tuple[bool, str]:
    """Step 3: Verify EventBridge schedule is ENABLED."""
    try:
        sched = _get_eb_schedule(schedule_id, region)
        state = sched.get("State", "")
        return state == "ENABLED", f"State={state}"
    except Exception as e:
        return False, str(e)


def step_list(agent, schedule_id: str) -> tuple[bool, str]:
    """Step 4: List schedules and verify schedule_id appears."""
    response = ask(agent, "List my schedules", verbose=True)
    if schedule_id in response:
        return True, "schedule_id found in list response"
    return False, f"schedule_id not found in: {response[:300]}"


def step_toggle_pause(agent, schedule_id: str, region: str) -> tuple[bool, str]:
    """Step 5: Pause the schedule and verify EventBridge is DISABLED."""
    ask(agent, "Pause that schedule", verbose=True)
    try:
        sched = _get_eb_schedule(schedule_id, region)
        state = sched.get("State", "")
        return state == "DISABLED", f"State={state}"
    except Exception as e:
        return False, str(e)


def step_toggle_resume(agent, schedule_id: str, region: str) -> tuple[bool, str]:
    """Step 6: Resume the schedule and verify EventBridge is ENABLED."""
    ask(agent, "Resume that schedule", verbose=True)
    try:
        sched = _get_eb_schedule(schedule_id, region)
        state = sched.get("State", "")
        return state == "ENABLED", f"State={state}"
    except Exception as e:
        return False, str(e)


def step_execute(schedule_id: str, region: str) -> tuple[bool, str]:
    """Step 7: Invoke the executor Lambda directly."""
    lambda_client = boto3.client("lambda", region_name=region)
    resp = lambda_client.invoke(
        FunctionName=os.environ["EXECUTOR_LAMBDA_ARN"],
        InvocationType="RequestResponse",
        Payload=json.dumps({"schedule_id": schedule_id}),
    )
    if resp.get("FunctionError"):
        payload = json.loads(resp["Payload"].read())
        return False, f"FunctionError: {resp['FunctionError']} — {payload}"
    payload = json.loads(resp["Payload"].read())
    return True, f"StatusCode={resp['StatusCode']}, payload={str(payload)[:200]}"


def step_verify_results(schedule_id: str, results_table: str, region: str) -> tuple[bool, str]:
    """Step 8: Verify at least one success result in the results table."""
    table = boto3.resource("dynamodb", region_name=region).Table(results_table)
    resp = table.query(
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": f"SCHEDULE#{schedule_id}"},
    )
    items = resp.get("Items", [])
    if not items:
        return False, "No result records found"
    success = [i for i in items if i.get("status") == "success"]
    if not success:
        statuses = [i.get("status") for i in items]
        return False, f"No success records; statuses={statuses}"
    return True, f"{len(success)} success record(s) found"


def step_delete(agent, schedule_id: str) -> tuple[bool, str]:
    """Step 9: Delete the schedule explicitly by ID."""
    response = ask(agent, f"Delete schedule {schedule_id}", verbose=True)
    return True, response[:200]


def step_verify_cleanup(schedule_id: str, table_name: str, region: str) -> tuple[bool, str]:
    """Step 10: Verify DynamoDB item gone and EventBridge schedule deleted."""
    items = _dynamo_query_gsi1(table_name, schedule_id, region)
    if items:
        return False, f"DynamoDB still has {len(items)} item(s)"
    try:
        _get_eb_schedule(schedule_id, region)
        return False, "EventBridge schedule still exists"
    except Exception as e:
        # boto3 raises ClientError with Code=ResourceNotFoundException when schedule is gone
        if "ResourceNotFoundException" not in str(e):
            return False, f"Unexpected error checking EventBridge: {e}"
    return True, "DynamoDB item gone, EventBridge schedule deleted"


def print_result(step: str, passed: bool, detail: str) -> None:
    icon = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
    status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  {icon} [{status}] {step}: {detail}")


def announce(step: str) -> None:
    print(f"\n{BOLD}▶ {step}{RESET}")


def run_e2e() -> None:
    region = os.environ.get("AWS_REGION", "us-west-2")
    schedules_table = os.environ["SCHEDULES_TABLE_NAME"]
    results_table = os.environ["SCHEDULE_RESULTS_TABLE_NAME"]
    ses_email = os.environ["SES_SENDER_EMAIL"]

    print(f"\n{BOLD}=== Scheduler E2E Test ==={RESET}\n")

    agent = create_agent(session_id=f"cli-e2e-{uuid4().hex[:8]}")
    agent.callback_handler = _cli_callback
    schedule_id = ""
    results: list[tuple[str, bool, str]] = []

    def record(name: str, passed: bool, detail: str) -> bool:
        results.append((name, passed, detail))
        print_result(name, passed, detail)
        return passed

    try:
        # Step 1: Create
        announce("1. Create schedule")
        ok, schedule_id, detail = step_create(agent, ses_email, schedules_table, region)
        record("1. Create schedule", ok, detail if ok else detail)
        if not ok:
            print(f"\n{RED}Cannot continue without schedule_id — aborting.{RESET}")
            return

        print(f"     {YELLOW}schedule_id: {schedule_id}{RESET}")

        # Step 2: Verify DynamoDB create
        announce("2. Verify DynamoDB (create)")
        ok, detail = step_verify_dynamo_create(schedule_id, schedules_table, region)
        record("2. Verify DynamoDB (create)", ok, detail)

        # Step 3: Verify EventBridge ENABLED
        announce("3. Verify EventBridge ENABLED")
        ok, detail = step_verify_eb_enabled(schedule_id, region)
        record("3. Verify EventBridge ENABLED", ok, detail)

        # Step 4: List
        announce("4. List schedules")
        ok, detail = step_list(agent, schedule_id)
        record("4. List schedules", ok, detail)

        # Step 5: Pause
        announce("5. Toggle pause (DISABLED)")
        ok, detail = step_toggle_pause(agent, schedule_id, region)
        record("5. Toggle pause (DISABLED)", ok, detail)

        # Step 6: Resume
        announce("6. Toggle resume (ENABLED)")
        ok, detail = step_toggle_resume(agent, schedule_id, region)
        record("6. Toggle resume (ENABLED)", ok, detail)

        # Step 7: Execute Lambda
        announce("7. Execute Lambda")
        ok, detail = step_execute(schedule_id, region)
        record("7. Execute Lambda", ok, detail)

        # Step 8: Verify results
        announce("8. Verify execution results")
        ok, detail = step_verify_results(schedule_id, results_table, region)
        record("8. Verify execution results", ok, detail)

        # Step 9: Delete
        announce("9. Delete schedule")
        ok, detail = step_delete(agent, schedule_id)
        record("9. Delete schedule", ok, detail)

        # Step 10: Verify cleanup
        announce("10. Verify cleanup")
        ok, detail = step_verify_cleanup(schedule_id, schedules_table, region)
        record("10. Verify cleanup", ok, detail)

    finally:
        # Always attempt cleanup if we have a schedule_id and delete wasn't run
        if schedule_id and not any(r[0].startswith("9.") for r in results):
            print(f"\n{YELLOW}Running cleanup...{RESET}")
            try:
                ask(agent, f"Delete schedule {schedule_id}")
                print(f"  {GREEN}Cleanup: deleted {schedule_id}{RESET}")
            except Exception as e:
                print(f"  {RED}Cleanup failed: {e}{RESET}")

        # Summary
        passed = sum(1 for _, ok, _ in results if ok)
        total = len(results)
        color = GREEN if passed == total else RED
        print(f"\n{BOLD}Result: {color}{passed}/{total} steps passed{RESET}\n")
        if passed < total:
            sys.exit(1)


# ---------------------------------------------------------------------------
# Step 7.3 — E2E Attachment Test
# ---------------------------------------------------------------------------


def run_e2e_attachment() -> None:
    region = os.environ.get("AWS_REGION", "us-west-2")
    ses_email = os.environ["SES_SENDER_EMAIL"]

    print(f"\n{BOLD}=== Attachment E2E Test ==={RESET}\n")

    agent = create_agent(session_id=f"cli-e2e-att-{uuid4().hex[:8]}")
    agent.callback_handler = _cli_callback
    results: list[tuple[str, bool, str]] = []

    def record(name: str, passed: bool, detail: str) -> bool:
        results.append((name, passed, detail))
        print_result(name, passed, detail)
        return passed

    try:
        # Step 1: Verify report exists (s3_path may or may not appear in final text —
        # the LLM sometimes strips it, but the routing agent sees it in the raw tool output)
        announce("1. Get report for CL00007")
        response = ask(agent, "Show me the report for client CL00007", verbose=True)
        has_report = "Client Report" in response or "CL00007" in response or "Download" in response
        if not has_report:
            record("1. Get report", False, "No report found in response")
            print(f"\n{RED}Cannot continue — no report exists for CL00007.{RESET}")
            return
        has_s3 = "s3_path: s3://" in response
        # Extract s3_path if present — pass it explicitly to step 2
        s3_match = re.search(r"s3_path: (s3://\S+)", response)
        s3_path = s3_match.group(1) if s3_match else ""
        record("1. Get report", True, f"Report found (s3_path in text: {has_s3})")

        # Step 2: Email with attachment
        announce("2. Email report with PDF attachment")
        if s3_path:
            # Pass the s3_path explicitly so the agent doesn't have to re-fetch or guess
            prompt = (f"Send an email to {ses_email} with subject 'CL00007 Client Report' "
                      f"and body 'Please find the attached client report for CL00007.' "
                      f"with attachment_url {s3_path}")
        else:
            prompt = f"Email the report for client CL00007 to {ses_email} with the PDF attached"
        response = ask(agent, prompt, verbose=True)
        # Check for failure indicators first
        failed = any(kw in response.lower() for kw in ("sorry", "error", "invalid", "couldn't", "could not", "failed"))
        sent = not failed and any(kw in response.lower() for kw in ("sent", "delivered", "✓", "success"))
        record("2. Email with attachment", sent, response[:200])

        # Step 3: Verify via SES (best-effort)
        announce("3. Verify via SES send statistics")
        try:
            ses = boto3.client("ses", region_name=region)
            stats = ses.get_send_statistics()
            datapoints = stats.get("SendDataPoints", [])
            if datapoints:
                latest = max(datapoints, key=lambda d: d["Timestamp"])
                detail = f"Latest datapoint: {latest} (check inbox manually)"
            else:
                detail = "No datapoints yet (check inbox manually)"
            record("3. SES statistics (best-effort)", True, detail)
        except Exception as e:
            record("3. SES statistics (best-effort)", True, f"Could not fetch stats: {e} (check inbox manually)")

    finally:
        passed = sum(1 for _, ok, _ in results if ok)
        total = len(results)
        color = GREEN if passed == total else RED
        print(f"\n{BOLD}Result: {color}{passed}/{total} steps passed{RESET}\n")
        if passed < total:
            sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Advisor Chat CLI")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--e2e", action="store_true", help="Run automated E2E test")
    group.add_argument("--e2e-attachment", action="store_true", help="Run E2E with attachment (not yet implemented)")
    args = parser.parse_args()

    if args.e2e_attachment:
        run_e2e_attachment()
    elif args.e2e:
        run_e2e()
    else:
        run_repl()
