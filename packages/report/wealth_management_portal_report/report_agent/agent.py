import logging
import os

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)

# Bedrock Converse with forced tool use + 7 narrative sections can take 60-120s
# at Claude Sonnet 4.5 output rates. Default boto3 read_timeout is 60s. Step
# Functions handles orchestration-level retries, so no client-side retries here.
_BEDROCK_CLIENT_CONFIG = Config(
    read_timeout=600,
    connect_timeout=10,
    retries={"max_attempts": 1, "mode": "standard"},
)

# The 7 narrative keys the model must return.
# The first two (last_interaction_summary, recent_highlights) are embedded in the
# deterministic client summary table; the remaining 5 are appended in this order.
NARRATIVE_KEYS = (
    "last_interaction_summary",
    "recent_highlights",
    "portfolio_narrative",
    "financial_analysis",
    "opportunities",
    "relationship_context",
    "action_items",
)


def invoke_narrative_generator(components: dict) -> dict:
    """Call Bedrock Converse with forced submit_narratives tool use.

    Uses toolChoice: {"tool": {"name": "submit_narratives"}} so Bedrock enforces
    that the model invokes the tool. JSON structural validity is guaranteed by
    Bedrock's deserialization layer — eliminating the malformed-JSON failure class.

    IMPORTANT: Bedrock does NOT enforce non-empty values. The JSON Schema `required`
    and `minLength` keywords are advisory to the model only (verified in spike at
    bedrock-tooluse-spike.md, Experiment A). Client-side validation below is essential.

    Args:
        components: dict with key "synthesis_prompts" mapping section names to prompt strings.

    Returns:
        dict with exactly the 7 NARRATIVE_KEYS as non-empty string values.

    Raises:
        RuntimeError: if the model did not invoke submit_narratives.
        ValueError: if any required key is missing, empty, or non-string.
    """
    # Build system prompt from synthesis prompts only — no JSON instructions, no format talk
    synthesis_block = "\n".join(f"{name}: {prompt}" for name, prompt in components["synthesis_prompts"].items())
    system_prompt = (
        "You are a wealth management report writer. "
        "Call submit_narratives with the narrative sections.\n\n"
        f"Synthesis prompts:\n{synthesis_block}"
    )

    # Tool schema: minLength is advisory to the model; Bedrock does not enforce it
    tool_config = {
        "tools": [
            {
                "toolSpec": {
                    "name": "submit_narratives",
                    "description": "Submit the seven narrative sections for the client report.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "required": list(NARRATIVE_KEYS),
                            "properties": {k: {"type": "string", "minLength": 1} for k in NARRATIVE_KEYS},
                        }
                    },
                }
            }
        ],
        "toolChoice": {"tool": {"name": "submit_narratives"}},
    }

    logger.info("Narrative generation started: sections=%d", len(components["synthesis_prompts"]))

    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        config=_BEDROCK_CLIENT_CONFIG,
    )
    response = bedrock.converse(
        modelId=os.environ.get("REPORT_BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": "Submit the narrative sections."}]}],
        toolConfig=tool_config,
        # maxTokens is required — no default. 8192 covers 7 sections of ~2500 chars each;
        # tune upward if sections are truncated in production.
        inferenceConfig={"maxTokens": 8192},
    )

    # Iterate content defensively — with forced toolChoice there is usually one block,
    # but future model versions may prepend a text block (spike gotcha 8.4)
    content = response["output"]["message"]["content"]
    tool_use_block = next((b["toolUse"] for b in content if "toolUse" in b), None)

    if tool_use_block is None:
        raise RuntimeError(
            f"Model did not invoke submit_narratives tool; "
            f"stopReason={response.get('stopReason')!r}; content={content!r}"
        )

    narratives = tool_use_block["input"]

    # Client-side validation — Bedrock does not enforce non-empty values (see docstring)
    missing = [k for k in NARRATIVE_KEYS if k not in narratives]
    if missing:
        raise ValueError(f"Narrative JSON missing required keys: {missing}")

    non_string = [k for k in NARRATIVE_KEYS if not isinstance(narratives[k], str)]
    if non_string:
        raise ValueError(f"Narrative JSON has null/empty values for: {non_string}")

    empty = [k for k in NARRATIVE_KEYS if not narratives[k]]
    if empty:
        raise ValueError(f"Narrative JSON has null/empty values for: {empty}")

    logger.info(
        "Narrative generation completed: lengths=%s",
        {k: len(narratives[k]) for k in NARRATIVE_KEYS},
    )
    return {k: narratives[k] for k in NARRATIVE_KEYS}


def assemble_markdown(deterministic_sections: str, narratives: dict) -> str:
    """Assemble the final report markdown from deterministic sections and model narratives.

    Fills {{ last_interaction_summary }} and {{ recent_highlights }} placeholders,
    inserts chart image references at sentinel tokens placed by the template,
    then appends the 5 fully-narrative sections in report order.
    """
    # Verify sentinel tokens are present before replacing (fail loud on template drift)
    if "<!-- CHART:allocation -->" not in deterministic_sections:
        raise ValueError("Missing sentinel <!-- CHART:allocation --> in deterministic_sections")
    if "<!-- CHART:cash_flow -->" not in deterministic_sections:
        raise ValueError("Missing sentinel <!-- CHART:cash_flow --> in deterministic_sections")

    # Fill the two placeholders the client summary template leaves for model output
    sections = deterministic_sections.replace(
        "{{ last_interaction_summary }}", narratives["last_interaction_summary"]
    ).replace("{{ recent_highlights }}", narratives["recent_highlights"])

    # Replace sentinel tokens with chart image references
    sections = sections.replace("<!-- CHART:allocation -->", "![allocation](allocation.svg)")
    sections = sections.replace("<!-- CHART:cash_flow -->", "![cash_flow](cash_flow.svg)")

    # Append the 5 purely narrative sections in required report order
    narrative_sections = "\n\n".join(
        [
            narratives["portfolio_narrative"],
            narratives["financial_analysis"],
            narratives["opportunities"],
            narratives["relationship_context"],
            narratives["action_items"],
        ]
    )

    return sections + "\n\n" + narrative_sections
