"""
Query Parser - Parse natural language queries about stocks
Uses AWS Bedrock Claude for intelligent query understanding
"""

import json
import re
from dataclasses import dataclass

import boto3
from botocore.config import Config


@dataclass
class ParsedQuery:
    """Parsed query structure"""

    intent: str  # compare, analyze, portfolio, trend, news
    tickers: list[str]
    time_range: str  # 1D, 5D, 1M, 6M, YTD, 1Y, 5Y, MAX
    comparison_type: str  # performance, fundamentals, technical
    context: dict
    confidence: float  # 0-1


class QueryParser:
    """Parse natural language stock queries using LLM"""

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize query parser

        Args:
            region: AWS region for Bedrock
        """
        config = Config(region_name=region, retries={"max_attempts": 3, "mode": "adaptive"})
        self.bedrock = boto3.client("bedrock-runtime", config=config)
        self.model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

        # Common stock symbols for reference
        self.common_stocks = {
            "tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
            "finance": ["JPM", "BAC", "WFC", "GS", "MS"],
            "healthcare": ["JNJ", "UNH", "PFE", "ABBV", "TMO"],
            "energy": ["XOM", "CVX", "COP", "SLB"],
            "consumer": ["WMT", "HD", "MCD", "NKE", "SBUX"],
        }

    def _call_bedrock(self, prompt: str, max_tokens: int = 1000) -> str:
        """Call AWS Bedrock Claude"""
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = self.bedrock.invoke_model(modelId=self.model_id, body=json.dumps(request_body))

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"].strip()

    def parse_query(self, query: str, portfolio_tickers: list[str] | None = None) -> ParsedQuery:
        """
        Parse natural language query

        Args:
            query: User's natural language query
            portfolio_tickers: User's portfolio stocks (for context)

        Returns:
            ParsedQuery object
        """
        # Build context
        context_info = ""
        if portfolio_tickers:
            context_info = f"\nUser's portfolio: {', '.join(portfolio_tickers)}"

        prompt = f"""Parse this stock market query into structured data.

Query: "{query}"{context_info}

Common stock categories:
- Tech: AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA
- Finance: JPM, BAC, WFC, GS, MS
- Healthcare: JNJ, UNH, PFE, ABBV, TMO
- Energy: XOM, CVX, COP, SLB
- Consumer: WMT, HD, MCD, NKE, SBUX

Task: Extract structured information from the query.

Intent types:
- "compare": Compare multiple stocks
- "analyze": Analyze single stock or sector
- "portfolio": Portfolio-related query
- "trend": Identify trends
- "news": Link to news/themes

Time ranges:
- 1D (today), 5D (5 days), 1M (1 month), 6M (6 months)
- YTD (year to date), 1Y (1 year), 5Y (5 years), MAX (all time)

Comparison types:
- "performance": Price performance comparison
- "fundamentals": Financial metrics comparison
- "technical": Technical analysis comparison

Instructions:
1. Identify the intent
2. Extract stock ticker symbols (use common stocks if query says "top 3 tech" etc.)
3. Determine time range (default: 1M if not specified)
4. Identify comparison type
5. Extract any additional context
6. Provide confidence score (0-1)

Return ONLY valid JSON (no markdown):
{{
  "intent": "compare",
  "tickers": ["AAPL", "MSFT", "GOOGL"],
  "time_range": "1M",
  "comparison_type": "performance",
  "context": {{
    "sector": "technology",
    "metric": "price",
    "notes": "User wants to see top 3 tech stocks"
  }},
  "confidence": 0.95
}}"""

        try:
            response = self._call_bedrock(prompt)

            # Clean response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

            # Parse JSON
            parsed_data = json.loads(response)

            # Create ParsedQuery object
            parsed_query = ParsedQuery(
                intent=parsed_data.get("intent", "analyze"),
                tickers=parsed_data.get("tickers", []),
                time_range=parsed_data.get("time_range", "1M"),
                comparison_type=parsed_data.get("comparison_type", "performance"),
                context=parsed_data.get("context", {}),
                confidence=parsed_data.get("confidence", 0.8),
            )

            return parsed_query

        except Exception as e:
            print(f"Error parsing query: {e}")

            # Fallback: basic parsing
            return self._fallback_parse(query, portfolio_tickers)

    def _fallback_parse(self, query: str, portfolio_tickers: list[str] | None = None) -> ParsedQuery:
        """
        Fallback parser when LLM fails
        Uses simple keyword matching
        """
        query_lower = query.lower()

        # Extract tickers (simple regex)
        ticker_pattern = r"\b[A-Z]{1,5}\b"
        tickers = re.findall(ticker_pattern, query.upper())

        # If no tickers found, check for keywords
        if not tickers:
            if "tech" in query_lower:
                tickers = ["AAPL", "MSFT", "GOOGL"]
            elif "portfolio" in query_lower and portfolio_tickers:
                tickers = portfolio_tickers

        # Determine intent
        intent = "analyze"
        if "compare" in query_lower or "vs" in query_lower:
            intent = "compare"
        elif "portfolio" in query_lower:
            intent = "portfolio"
        elif "trend" in query_lower:
            intent = "trend"
        elif "news" in query_lower:
            intent = "news"

        # Determine time range
        time_range = "1M"
        if "today" in query_lower or "1d" in query_lower:
            time_range = "1D"
        elif "week" in query_lower or "5d" in query_lower:
            time_range = "5D"
        elif "month" in query_lower or "1m" in query_lower:
            time_range = "1M"
        elif "year" in query_lower or "1y" in query_lower:
            time_range = "1Y"

        return ParsedQuery(
            intent=intent,
            tickers=tickers[:5],  # Limit to 5 stocks
            time_range=time_range,
            comparison_type="performance",
            context={"fallback": True},
            confidence=0.5,
        )
