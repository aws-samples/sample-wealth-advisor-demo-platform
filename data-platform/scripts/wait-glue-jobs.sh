#!/usr/bin/env bash
set -euo pipefail

TABLES=(
  clients advisors accounts portfolios securities transactions holdings
  market_data performance fees goals interactions documents compliance
  research articles client_income_expense client_investment_restrictions
  client_reports crawl_log portfolio_config recommended_products
  theme_article_associations themes
)

REGION="${AWS_PRIMARY_REGION:-${PRIMARY_REGION:-}}"
if [[ -z "$REGION" ]]; then
  echo "ERROR: AWS_PRIMARY_REGION or PRIMARY_REGION must be set" >&2
  exit 1
fi

TIMEOUT="${GLUE_WAIT_TIMEOUT:-3600}"
TERMINAL_STATES="SUCCEEDED FAILED STOPPED ERROR TIMEOUT"
TOTAL=${#TABLES[@]}
START=$(date +%s)

# Associative array to track last known state per table
declare -A states
for t in "${TABLES[@]}"; do states[$t]="PENDING"; done

get_state() {
  local job="financial-advisor-load-$1"
  local out
  out=$(aws glue get-job-runs --job-name "$job" --max-results 1 \
        --region "$REGION" --output json 2>/dev/null)
  local s
  s=$(echo "$out" | python3 -c \
      "import sys,json; runs=json.load(sys.stdin).get('JobRuns',[]); \
       print(runs[0]['JobRunState'] if runs else 'PENDING')" 2>/dev/null || echo "PENDING")
  echo "$s"
}

is_terminal() {
  [[ " $TERMINAL_STATES " == *" $1 "* ]]
}

while true; do
  now=$(date +%s)
  elapsed=$(( now - START ))
  if (( elapsed >= TIMEOUT )); then
    echo "ERROR: overall timeout of ${TIMEOUT}s exceeded" >&2
    exit 1
  fi

  # Poll all non-terminal jobs in parallel
  declare -A pids
  for t in "${TABLES[@]}"; do
    if ! is_terminal "${states[$t]}"; then
      ( get_state "$t" ) > "/tmp/glue_state_$t" &
      pids[$t]=$!
    fi
  done

  # Collect results
  for t in "${!pids[@]}"; do
    wait "${pids[$t]}" 2>/dev/null || true
    states[$t]=$(cat "/tmp/glue_state_$t" 2>/dev/null || echo "PENDING")
    rm -f "/tmp/glue_state_$t"
  done
  unset pids

  # Count done / succeeded / failed
  done_count=0; succeeded=0; failed=0
  for t in "${TABLES[@]}"; do
    s="${states[$t]}"
    if is_terminal "$s"; then
      done_count=$(( done_count + 1 ))
      if [[ "$s" == "SUCCEEDED" ]]; then
        succeeded=$(( succeeded + 1 ))
      else
        failed=$(( failed + 1 ))
      fi
    fi
  done

  # Build progress line
  status_parts=()
  for t in "${TABLES[@]}"; do status_parts+=("$t: ${states[$t]}"); done
  printf "[%d/%d] Waiting... %s\n" "$done_count" "$TOTAL" "$(IFS=', '; echo "${status_parts[*]}")"

  if (( done_count == TOTAL )); then
    echo "Done: ${succeeded} succeeded, ${failed} failed."
    [[ $failed -eq 0 ]] && exit 0 || exit 1
  fi

  sleep 30
done
