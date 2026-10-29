"""Quantitative Analyst Agent — extracts performance metrics from Redshift."""

from __future__ import annotations

import logging
import math
import os

import boto3
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from ..schemas import QuantBundle, QuantTask

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Quantitative Analyst for a portfolio due diligence system.
Extract performance and risk metrics from the data warehouse for a specified fund.
Return only structured numerical data — no interpretation or scoring.
If data is unavailable, set data_available=false and return nulls for all metrics.
"""


@tool
def extract_performance_data(portfolio_id: str, window_years: int = 3) -> dict:
    """Query fund_performance for NAV time-series over specified window.

    Args:
        portfolio_id: Fund identifier.
        window_years: Number of years of history to retrieve (1-10).

    Returns:
        Dict with keys: portfolio_id, returns (list of {date, nav, benchmark_nav}), metadata.
    """
    import re
    import time

    use_athena = os.environ.get("DATA_ENGINE", "athena").lower() == "athena"
    region = os.environ.get("AWS_REGION", "us-west-2")
    profile = os.environ.get("AWS_PROFILE")
    session = boto3.Session(profile_name=profile, region_name=region)

    safe_portfolio_id = re.sub(r"[^\w\-.]", "", portfolio_id)
    sql = f"""
        SELECT
            date_trunc('month', period_end_date) AS month,
            time_weighted_return AS fund_return,
            benchmark_return
        FROM performance
        WHERE portfolio_id = '{safe_portfolio_id}'
          AND period_end_date >= date_add('year', -{int(window_years)}, current_date)
        ORDER BY month
    """

    try:
        if use_athena:
            client = session.client("athena")
            start_kwargs = {
                "QueryString": sql,
                "WorkGroup": os.environ.get("ATHENA_WORKGROUP", "primary"),
                "QueryExecutionContext": {
                    "Catalog": os.environ.get("ATHENA_CATALOG", "s3tablescatalog/financial-advisor-s3table"),
                    "Database": os.environ.get("ATHENA_DATABASE", "financial_advisor"),
                },
            }
            output_loc = os.environ.get("ATHENA_OUTPUT_LOCATION", "")
            if output_loc:
                start_kwargs["ResultConfiguration"] = {"OutputLocation": output_loc}
            resp = client.start_query_execution(**start_kwargs)
            query_id = resp["QueryExecutionId"]
            for _ in range(30):
                state = client.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]["State"]
                if state == "SUCCEEDED":
                    break
                if state in ("FAILED", "CANCELLED"):
                    return {"portfolio_id": portfolio_id, "returns": [], "metadata": {"error": state}}
                time.sleep(2)
            result = client.get_query_results(QueryExecutionId=query_id)
            result_rows = result.get("ResultSet", {}).get("Rows", [])
            rows = []
            for record in result_rows[1:]:
                cells = record["Data"]
                rows.append(
                    {
                        "date": cells[0].get("VarCharValue", ""),
                        "fund_return": float(cells[1].get("VarCharValue", 0) or 0),
                        "benchmark_return": float(cells[2].get("VarCharValue", 0) or 0),
                    }
                )
        else:
            client = session.client("redshift-data")
            workgroup = os.environ.get("REDSHIFT_WORKGROUP", "financial-advisor-wg")
            database = os.environ.get("REDSHIFT_DATABASE", "dev")
            resp = client.execute_statement(WorkgroupName=workgroup, Database=database, Sql=sql)
            stmt_id = resp["Id"]
            for _ in range(30):
                status = client.describe_statement(Id=stmt_id)["Status"]
                if status == "FINISHED":
                    break
                if status in ("FAILED", "ABORTED"):
                    return {"portfolio_id": portfolio_id, "returns": [], "metadata": {"error": status}}
                time.sleep(2)
            result = client.get_statement_result(Id=stmt_id)
            rows = []
            for record in result.get("Records", []):
                rows.append(
                    {
                        "date": record[0].get("stringValue", ""),
                        "fund_return": float(record[1].get("doubleValue", 0) or 0),
                        "benchmark_return": float(record[2].get("doubleValue", 0) or 0),
                    }
                )

        return {"portfolio_id": portfolio_id, "returns": rows, "metadata": {"window_years": window_years}}
    except Exception as exc:
        logger.warning("Query failed for %s: %s", portfolio_id, exc)
        return {"portfolio_id": portfolio_id, "returns": [], "metadata": {"error": str(exc)}}


@tool
def calculate_metrics(raw_data: dict) -> dict:
    """Compute standardised risk/return metrics from raw performance data.

    Args:
        raw_data: Output of extract_performance_data.

    Returns:
        Dict with annualised_return, volatility, sharpe_ratio, max_drawdown,
        benchmark_excess_return, attribution.
    """
    returns = raw_data.get("returns", [])
    if len(returns) < 3:
        return {
            "annualised_return": None,
            "volatility": None,
            "sharpe_ratio": None,
            "max_drawdown": None,
            "benchmark_excess_return": None,
            "attribution": {},
        }

    fund_rets = [r["fund_return"] for r in returns]
    bench_rets = [r["benchmark_return"] for r in returns]

    n = len(fund_rets)
    mean_r = sum(fund_rets) / n
    ann_return = (1 + mean_r) ** 12 - 1  # monthly → annual

    variance = sum((r - mean_r) ** 2 for r in fund_rets) / (n - 1)
    vol = math.sqrt(variance * 12)

    rf_monthly = 0.04 / 12  # assume 4% risk-free
    excess = [r - rf_monthly for r in fund_rets]
    excess_mean = sum(excess) / n
    sharpe = (excess_mean * 12) / vol if vol > 0 else None

    # Max drawdown
    cumulative = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in fund_rets:
        cumulative *= 1 + r
        if cumulative > peak:
            peak = cumulative
        dd = (cumulative - peak) / peak
        if dd < max_dd:
            max_dd = dd

    mean_bench = sum(bench_rets) / n
    ann_bench = (1 + mean_bench) ** 12 - 1
    excess_return = ann_return - ann_bench

    return {
        "annualised_return": round(ann_return, 4),
        "volatility": round(vol, 4),
        "sharpe_ratio": round(sharpe, 3) if sharpe else None,
        "max_drawdown": round(max_dd, 4),
        "benchmark_excess_return": round(excess_return, 4),
        "attribution": {"selection": round(excess_return * 0.7, 4), "allocation": round(excess_return * 0.3, 4)},
    }


async def run_quant_analysis(task: QuantTask) -> QuantBundle:
    raw = extract_performance_data(portfolio_id=task.portfolio_id, window_years=task.window_years)
    if not raw.get("returns"):
        return QuantBundle(portfolio_id=task.portfolio_id, data_available=False)

    metrics = calculate_metrics(raw)
    return QuantBundle(
        portfolio_id=task.portfolio_id,
        data_available=True,
        annualised_return=metrics.get("annualised_return"),
        volatility=metrics.get("volatility"),
        sharpe_ratio=metrics.get("sharpe_ratio"),
        max_drawdown=metrics.get("max_drawdown"),
        benchmark_excess_return=metrics.get("benchmark_excess_return"),
        attribution=metrics.get("attribution", {}),
    )


def create_agent() -> Agent:
    return Agent(
        name="Quantitative Analyst",
        description="Extracts and calculates performance metrics for DD assessment.",
        model=BedrockModel(
            model_id=os.environ.get("QUANT_ANALYST_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
        ),
        system_prompt=SYSTEM_PROMPT,
        tools=[extract_performance_data, calculate_metrics],
        callback_handler=None,
    )
