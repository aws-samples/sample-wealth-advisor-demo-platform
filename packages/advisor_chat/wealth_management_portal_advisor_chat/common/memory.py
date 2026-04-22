"""AgentCore Memory helper — STM (1-day conversation) + LTM (30-day schema/SQL artifacts).

Based on: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/strands-sdk-memory.html
and: https://github.com/aws-samples/sample-strands-agent-with-agentcore
"""

import logging
import os

logger = logging.getLogger(__name__)


def sanitize_messages(messages: list) -> list:
    """Fix toolUse/toolResult mismatches that cause Bedrock ValidationException.

    Ensures every toolResult message is preceded by an assistant message
    containing the matching toolUse block(s). Drops orphaned toolResult
    messages that would otherwise cause:
      "The number of toolResult blocks ... exceeds the number of toolUse blocks"
    """
    if not messages:
        return messages

    sanitized = []
    for i, msg in enumerate(messages):
        role = msg.get("role", "")
        content = msg.get("content", [])

        if role == "user":
            # Count toolResult blocks in this user message
            tool_result_ids = {
                block["toolResult"]["toolUseId"]
                for block in content
                if isinstance(block, dict) and "toolResult" in block
            }
            if tool_result_ids:
                # Find toolUse ids in the previous assistant message
                prev_tool_use_ids = set()
                if sanitized and sanitized[-1].get("role") == "assistant":
                    for block in sanitized[-1].get("content", []):
                        if isinstance(block, dict) and "toolUse" in block:
                            prev_tool_use_ids.add(block["toolUse"]["toolUseId"])

                orphaned = tool_result_ids - prev_tool_use_ids
                if orphaned:
                    logger.warning(
                        "Dropping %d orphaned toolResult(s) from message %d",
                        len(orphaned),
                        i,
                    )
                    # Keep only non-orphaned content blocks
                    cleaned = [
                        block
                        for block in content
                        if not (
                            isinstance(block, dict)
                            and "toolResult" in block
                            and block["toolResult"]["toolUseId"] in orphaned
                        )
                    ]
                    if not cleaned:
                        continue  # skip entirely empty message
                    msg = {**msg, "content": cleaned}

        sanitized.append(msg)

    return sanitized


_stm_id: str | None = None
_ltm_id: str | None = None

STM_NAME = "WealthMgmt_STM"
LTM_NAME = "WealthMgmt_LTM"


def _get_client():
    from bedrock_agentcore.memory import MemoryClient

    return MemoryClient(region_name=os.environ.get("AWS_REGION", "us-west-2"))


def _find_by_name(client, name: str) -> str | None:
    """Find a memory by name. The list API doesn't return a 'name' field,
    so we match on 'id' which is formatted as '{name}-{suffix}'."""
    result = client.list_memories()
    memories = result if isinstance(result, list) else result.get("memories", [])
    for m in memories:
        mid = m.get("id") if isinstance(m, dict) else getattr(m, "id", None)
        n = m.get("name") if isinstance(m, dict) else getattr(m, "name", None)
        # Match on explicit name field, or id prefix (id format: '{name}-{suffix}')
        if n == name or (mid and mid.startswith(f"{name}-")):
            return mid
    return None


def get_stm_id() -> str:
    """Short-term memory — raw conversation turns, recycled daily."""
    global _stm_id
    env_id = os.environ.get("AGENTCORE_STM_ID", "")
    if env_id:
        return env_id
    if _stm_id is not None:
        return _stm_id
    try:
        client = _get_client()
        found = _find_by_name(client, STM_NAME)
        if found:
            _stm_id = found
        else:
            result = client.create_memory(
                name=STM_NAME,
                description="Short-term conversation memory (3-day)",
                strategies=[],
                # API minimum is 3 days (was 1, rejected since SDK validation change)
                event_expiry_days=3,
            )
            _stm_id = result["id"]
            logger.info("Created STM: %s", _stm_id)
    except Exception:
        logger.exception("Failed to get/create STM")
        _stm_id = ""
    return _stm_id or ""


def get_ltm_id() -> str:
    """Long-term memory — schema and SQL artifacts with semantic extraction, 30-day retention."""
    global _ltm_id
    env_id = os.environ.get("AGENTCORE_LTM_ID", "")
    if env_id:
        return env_id
    if _ltm_id is not None:
        return _ltm_id
    try:
        client = _get_client()
        found = _find_by_name(client, LTM_NAME)
        if found:
            _ltm_id = found
        else:
            result = client.create_memory_and_wait(
                name=LTM_NAME,
                description="Long-term schema and SQL artifact memory",
                strategies=[
                    {
                        "semanticMemoryStrategy": {
                            "name": "SchemaAndSQL",
                            "namespaces": ["/knowledge/{actorId}/"],
                        }
                    },
                    {
                        "summaryMemoryStrategy": {
                            "name": "SessionSummarizer",
                            "namespaces": ["/summaries/{actorId}/{sessionId}/"],
                        }
                    },
                ],
                event_expiry_days=30,
            )
            _ltm_id = result["id"]
            logger.info("Created LTM: %s", _ltm_id)
    except Exception:
        logger.exception("Failed to get/create LTM")
        _ltm_id = ""
    return _ltm_id or ""


# Backward compat — routing agent calls this
def get_or_create_memory_id() -> str:
    """Return STM id (used by routing agent for conversation memory)."""
    return get_stm_id()


def list_session_events(max_results: int = 50) -> list[dict]:
    """List memory events for conversation history. Returns list of event dicts."""
    try:
        memory_id = get_ltm_id() or get_stm_id()
        if not memory_id:
            return []
        client = _get_client()
        result = client.list_memory_events(memory_id=memory_id, max_results=max_results)
        events = result if isinstance(result, list) else result.get("events", [])
        return [ev if isinstance(ev, dict) else vars(ev) for ev in events]
    except Exception:
        logger.debug("Failed to list session events", exc_info=True)
        return []


def close_session(session_id: str) -> None:
    """Signal session end — triggers memory consolidation."""
    try:
        ltm_id = get_ltm_id()
        if not ltm_id:
            return
        client = _get_client()
        client.save_memory_event(
            memory_id=ltm_id,
            session_id=session_id,
            actor_id=session_id,
            messages=[{"role": "user", "content": [{"text": "[session closed]"}]}],
        )
    except Exception:
        logger.debug("Failed to close session %s", session_id, exc_info=True)


def create_ltm_session_manager(session_id: str):
    """Create an AgentCoreMemorySessionManager wired to LTM for a specialist agent.

    Returns None if LTM is unavailable.
    """
    try:
        ltm_id = get_ltm_id()
        if not ltm_id:
            return None
        from bedrock_agentcore.memory.integrations.strands.config import (
            AgentCoreMemoryConfig,
            RetrievalConfig,
        )
        from bedrock_agentcore.memory.integrations.strands.session_manager import (
            AgentCoreMemorySessionManager,
        )

        config = AgentCoreMemoryConfig(
            memory_id=ltm_id,
            session_id=session_id,
            actor_id=session_id,
            retrieval_config={
                "/knowledge/{actorId}/": RetrievalConfig(top_k=10, relevance_score=0.3),
                "/summaries/{actorId}/{sessionId}/": RetrievalConfig(top_k=3, relevance_score=0.5),
            },
        )
        region = os.environ.get("AWS_REGION", "us-west-2")
        return AgentCoreMemorySessionManager(agentcore_memory_config=config, region_name=region)
    except Exception:
        logger.debug("Could not create LTM session manager", exc_info=True)
        return None
