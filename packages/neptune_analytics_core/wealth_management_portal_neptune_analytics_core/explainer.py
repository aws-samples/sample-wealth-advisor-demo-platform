"""LLM-powered column explanation for search results."""

import json
import logging

import boto3

from .client import AWS_REGION, BEDROCK_MODEL_ID

logger = logging.getLogger(__name__)


class ColumnExplainer:
    """Generates LLM-powered explanations for search result column fields."""

    _cache: dict[tuple, dict[str, str]] = {}

    def __init__(self, model_id: str = BEDROCK_MODEL_ID, region: str = AWS_REGION):
        self.model_id = model_id
        self.region = region
        self.client = boto3.client("bedrock-runtime", region_name=region)

    def explain(self, field_names: list[str]) -> dict[str, str]:
        """Generate a short explanation for each field name.

        Explanations are generic (not query-specific) so they can be cached
        per field-set and reused across searches for the same node type.
        """
        try:
            if not field_names:
                return {}
            cache_key = tuple(sorted(field_names))
            if cache_key in ColumnExplainer._cache:
                return ColumnExplainer._cache[cache_key]
            prompt = self._build_prompt(field_names)
            response_text = self._invoke_bedrock(prompt)
            result = self._parse_response(response_text, field_names)
            ColumnExplainer._cache[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"Column explanation failed: {e}")
            return {}

    def _build_prompt(self, field_names: list[str]) -> str:
        fields_list = ", ".join(field_names)
        return (
            "You are a helpful assistant for a financial knowledge graph application.\n\n"
            "The search results table displays the following data fields:\n"
            f"{fields_list}\n\n"
            "For each field, provide a short explanation (one sentence) of what that "
            "field represents in a financial advisor context. Return your response as a JSON "
            "object mapping each field name to its explanation string.\n\n"
            "Return ONLY valid JSON, no other text. Example format:\n"
            '{"field1": "explanation1", "field2": "explanation2"}'
        )

    def _invoke_bedrock(self, prompt: str) -> str:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

    def _parse_response(self, response_text: str, field_names: list[str]) -> dict[str, str]:
        text = response_text.strip()
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()

        parsed = json.loads(text)

        explanations: dict[str, str] = {}
        for f in field_names:
            if f in parsed and isinstance(parsed[f], str):
                explanations[f] = parsed[f]
            else:
                explanations[f] = f"Data field: {f}"
        return explanations
