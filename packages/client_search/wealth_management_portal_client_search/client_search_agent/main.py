import logging
import re

import uvicorn
from bedrock_agentcore.runtime.models import PingStatus
from pydantic import BaseModel

from .agent import get_agent
from .init import app

logger = logging.getLogger(__name__)


class InvokeInput(BaseModel):
    query: str
    table_schema: str


class InvokeOutput(BaseModel):
    sql: str


def _extract_sql(text: str) -> str | None:
    """Extract a SELECT statement from LLM output."""
    cleaned = re.sub(r"```sql\s*", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned)
    match = re.search(r"(SELECT\s+.+?LIMIT\s+\d+)", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"(SELECT\s+.+)", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip().rstrip(";")
    return None


@app.post("/invocations")
async def invoke(input: InvokeInput) -> InvokeOutput:
    """Generate SQL from natural language query."""
    with get_agent(schema=input.table_schema) as agent:
        result = str(agent(input.query))
    sql = _extract_sql(result) or "SELECT * FROM clients WHERE status = 'Active' LIMIT 100"
    logger.info("Generated SQL: %s", sql)
    return InvokeOutput(sql=sql)


@app.get("/ping")
def ping() -> str:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    uvicorn.run("wealth_management_portal_client_search.client_search_agent.main:app", host="0.0.0.0", port=8080)
