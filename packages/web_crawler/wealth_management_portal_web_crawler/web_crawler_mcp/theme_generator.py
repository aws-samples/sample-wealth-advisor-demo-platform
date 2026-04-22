"""
Theme Generator - Identifies, ranks, and summarizes themes from articles
Copied from market_events_coordinator for use in web crawler batch processing
"""

import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import datetime

import boto3
from botocore.config import Config
from wealth_management_portal_common_market_events.models import Article, Theme

from wealth_management_portal_web_crawler.web_crawler_mcp.mcp_client_helper import (
    build_tool_name_map,
    extract_mcp_data,
    get_portfolio_mcp_client,
)

logger = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from LLM responses."""
    return re.sub(r"^```(?:json)?\s*\n?", "", re.sub(r"\n?```\s*$", "", text.strip()))


def _build_save_theme_args(theme: "Theme") -> dict:
    """Build the arguments dict for the save_theme MCP tool.

    Required fields are always included. Optional fields (ticker, score_breakdown,
    relevance_score, combined_score, matched_tickers, relevance_reasoning) are omitted
    when their value is None because the AgentCore Gateway schema parser does not
    support the null type.
    """
    sources_str = json.dumps(theme.sources) if isinstance(theme.sources, list) else (theme.sources or "[]")
    matched_tickers_str = (
        json.dumps(theme.matched_tickers) if isinstance(theme.matched_tickers, list) else theme.matched_tickers
    )
    score_breakdown_str = (
        json.dumps(theme.score_breakdown) if isinstance(theme.score_breakdown, dict) else theme.score_breakdown
    )

    args: dict = {
        "theme_id": theme.theme_id,
        "client_id": theme.client_id,
        "title": theme.title,
        "sentiment": theme.sentiment,
        "article_count": theme.article_count,
        "sources": sources_str,
        "summary": theme.summary,
        "score": theme.score,
        "rank": theme.rank,
    }
    optional = {
        "ticker": theme.ticker,
        "score_breakdown": score_breakdown_str,
        "relevance_score": theme.relevance_score,
        "combined_score": theme.combined_score,
        "matched_tickers": matched_tickers_str,
        "relevance_reasoning": theme.relevance_reasoning,
    }
    for key, val in optional.items():
        if val is not None:
            args[key] = val
    return args


class ThemeProcessor:
    """Processes articles to identify, rank, and summarize themes using AWS Bedrock"""

    # High-impact keywords for ranking
    IMPACT_KEYWORDS = [
        "earnings",
        "fed",
        "inflation",
        "rate",
        "trillion",
        "record",
        "crisis",
        "breakthrough",
        "surge",
        "plunge",
        "rally",
        "crash",
        "soar",
        "tumble",
        "spike",
        "plummet",
        "skyrocket",
        "collapse",
        "boom",
        "bust",
    ]

    # Scoring weights (must sum to 100)
    WEIGHT_ARTICLE_COUNT = 30
    WEIGHT_SOURCE_DIVERSITY = 25
    WEIGHT_RECENCY = 25
    WEIGHT_KEYWORDS = 20

    def __init__(
        self,
        mcp_client,
        bedrock_region: str = "us-east-1",
        use_cross_region: bool = True,
    ):
        """
        Initialize theme processor

        Args:
            mcp_client: Portfolio Data MCP client for Redshift access
            bedrock_region: AWS region for Bedrock
            use_cross_region: Whether to use cross-region inference profile
        """
        # Store MCP client
        self.mcp_client = mcp_client

        # Initialize Bedrock client
        config = Config(region_name=bedrock_region, retries={"max_attempts": 3, "mode": "adaptive"})
        self.bedrock = boto3.client("bedrock-runtime", config=config)
        self.use_cross_region = use_cross_region

        # Model ID
        self.model_id = os.environ.get("THEME_BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

    def get_recent_articles(self, hours: int = 48) -> list[Article]:
        """
        Get articles from the last N hours from Redshift via MCP

        Args:
            hours: Number of hours to look back

        Returns:
            List of Article objects
        """
        with self.mcp_client as client:
            names = build_tool_name_map(client, ["get_recent_articles"])
            result = client.call_tool_sync("get_recent_articles_001", names["get_recent_articles"], {"hours": hours})
            response = extract_mcp_data(result)
            # Portfolio MCP returns {"ok": True, "articles": [...]}
            articles_data = response.get("articles", []) if isinstance(response, dict) else response
            return [Article(**article) for article in articles_data]

    def _create_theme_prompt(self, articles: list[Article]) -> str:
        """Create prompt for LLM to identify themes"""
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"{i}. {article.title}\n"
            articles_text += f"   Source: {article.source}\n"
            articles_text += f"   Summary: {article.summary[:200] if article.summary else ''}...\n\n"

        prompt = f"""Analyze these US market news articles and identify 5-6 major themes or hot topics.

Requirements:
- Each theme must be supported by at least 3 articles
- Themes should represent distinct topics (no overlap)
- Focus on market-moving events and trends
- Provide a concise title for each theme (10-15 words)
- Determine sentiment for each theme: bullish, bearish, or neutral

Articles ({len(articles)} total):
{articles_text}

Return your analysis in this exact JSON format:
{{
  "themes": [
    {{
      "title": "Concise theme title here (10-15 words)",
      "article_indices": [1, 5, 12],
      "sentiment": "bullish",
      "rationale": "Brief explanation of why these articles form a coherent theme"
    }}
  ]
}}

Important:
- Return ONLY the JSON, no other text
- Ensure article_indices reference the article numbers above
- Each theme must have at least 3 articles
- Identify between 5 and 6 themes
- Sentiment must be exactly: "bullish", "bearish", or "neutral"
"""
        return prompt

    def identify_themes(self, articles: list[Article]) -> list[dict]:
        """
        Identify themes from articles using Bedrock

        Args:
            articles: List of Article objects

        Returns:
            List of theme dictionaries with article_hashes and metadata
        """
        if len(articles) < 3:
            raise ValueError("Need at least 3 articles to identify themes")

        # Create prompt
        prompt = self._create_theme_prompt(articles)

        # Call Bedrock
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = self.bedrock.invoke_model(modelId=self.model_id, body=json.dumps(request_body))
        response_body = json.loads(response["body"].read())
        response_text = response_body["content"][0]["text"]

        # Parse JSON response
        themes_data = json.loads(_strip_code_fences(response_text))

        # Validate and enrich themes
        validated_themes = []
        for theme in themes_data.get("themes", []):
            if len(theme.get("article_indices", [])) < 3:
                continue

            # Get article hashes and sources
            article_hashes = []
            sources = set()

            for idx in theme.get("article_indices", []):
                if 1 <= idx <= len(articles):
                    article = articles[idx - 1]
                    article_hashes.append(article.content_hash)
                    if article.source:
                        sources.add(article.source)

            validated_themes.append(
                {
                    "title": theme["title"],
                    "sentiment": theme.get("sentiment", "neutral").lower(),
                    "article_hashes": article_hashes,
                    "article_count": len(article_hashes),
                    "sources": list(sources),
                }
            )

        return validated_themes

    def calculate_theme_score(self, theme_data: dict, articles: list[Article]) -> tuple[float, dict[str, float]]:
        """
        Calculate importance score for a theme

        Args:
            theme_data: Theme dictionary
            articles: List of Article objects for this theme

        Returns:
            Tuple of (total_score, score_breakdown)
        """
        # Article count score
        article_count_score = min(theme_data["article_count"] / 10, 1.0) * self.WEIGHT_ARTICLE_COUNT

        # Source diversity score
        unique_sources = len(set(theme_data["sources"]))
        source_diversity_score = min(unique_sources / 5, 1.0) * self.WEIGHT_SOURCE_DIVERSITY

        # Recency score
        now = datetime.now()
        total_age_hours = 0
        for article in articles:
            if article.published_date:
                age_hours = (now - article.published_date).total_seconds() / 3600
                total_age_hours += age_hours
            else:
                total_age_hours += 48

        avg_age_hours = total_age_hours / len(articles) if articles else 48
        recency_factor = max(0, 1 - (avg_age_hours / 48))
        recency_score = recency_factor * self.WEIGHT_RECENCY

        # Keyword score
        title_lower = theme_data["title"].lower()
        keyword_matches = sum(1 for keyword in self.IMPACT_KEYWORDS if keyword in title_lower)
        keyword_score = min(keyword_matches / 3, 1.0) * self.WEIGHT_KEYWORDS

        total_score = article_count_score + source_diversity_score + recency_score + keyword_score

        breakdown = {
            "article_count_score": round(article_count_score, 2),
            "source_diversity_score": round(source_diversity_score, 2),
            "recency_score": round(recency_score, 2),
            "keyword_score": round(keyword_score, 2),
        }

        return round(total_score, 2), breakdown

    def _create_summary_prompt(self, theme_data: dict, articles: list[Article]) -> str:
        """Create prompt for LLM to generate summary"""
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"{i}. {article.title}\n"
            articles_text += f"   Source: {article.source}\n"
            articles_text += f"   Summary: {article.summary[:300] if article.summary else ''}\n\n"

        prompt = f"""Write a professional 2-3 sentence summary for this US market theme.

Theme: {theme_data["title"]}
Sentiment: {theme_data["sentiment"]}
Number of articles: {theme_data["article_count"]}
Sources: {", ".join(theme_data["sources"])}

Supporting Articles:
{articles_text}

Requirements:
- Write exactly 2-3 sentences (no more, no less)
- Focus on: what happened, why it matters, and market impact
- Use professional financial news writing style
- Be specific and factual (include numbers, companies, or events when available)
- Match the sentiment: {theme_data["sentiment"]}
- Write in present tense for current events
- Do NOT use phrases like "this theme" or "these articles"
- Write as if you're a financial journalist reporting the news

Return ONLY the summary text, no other commentary or formatting."""

        return prompt

    def generate_summary(self, theme_data: dict, articles: list[Article]) -> str:
        """
        Generate summary for a theme using Bedrock

        Args:
            theme_data: Theme dictionary
            articles: List of Article objects for this theme

        Returns:
            Generated summary text
        """
        prompt = self._create_summary_prompt(theme_data, articles)

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "temperature": 0.5,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = self.bedrock.invoke_model(modelId=self.model_id, body=json.dumps(request_body))
        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"].strip()

    def process_themes(self, hours: int = 48, limit: int = 6) -> tuple[list[Theme], dict[str, list[str]]]:
        """
        Complete theme processing pipeline: identify, rank, and summarize

        Args:
            hours: Number of hours to look back for articles
            limit: Maximum number of themes to return

        Returns:
            Tuple of (list of Theme objects, dict mapping theme_id to article_hashes)
        """
        # Get recent articles
        articles = self.get_recent_articles(hours=hours)

        if len(articles) < 3:
            raise ValueError(f"Need at least 3 articles, found {len(articles)}")

        # Identify themes
        theme_dicts = self.identify_themes(articles)

        # Process each theme: score and summarize
        themes = []
        theme_articles_map = {}

        for i, theme_data in enumerate(theme_dicts, 1):
            # Get articles for this theme
            theme_articles = [a for a in articles if a.content_hash in theme_data["article_hashes"]]

            # Calculate score
            score, breakdown = self.calculate_theme_score(theme_data, theme_articles)

            # Generate summary
            summary = self.generate_summary(theme_data, theme_articles)

            # Create Theme object
            theme_id = f"theme_{int(datetime.now().timestamp())}_{i}"
            theme = Theme(
                theme_id=theme_id,
                client_id="__GENERAL__",
                title=theme_data["title"],
                sentiment=theme_data["sentiment"],
                article_count=theme_data["article_count"],
                sources=theme_data["sources"],
                created_at=datetime.now(),
                summary=summary,
                updated_at=datetime.now(),
                score=score,
                rank=0,  # Will be set after sorting
                score_breakdown=breakdown,
                generated_at=datetime.now(),
            )
            themes.append(theme)
            theme_articles_map[theme_id] = theme_data["article_hashes"]

        # Sort by score and assign ranks
        themes.sort(key=lambda t: t.score, reverse=True)
        for rank, theme in enumerate(themes[:limit], 1):
            theme.rank = rank

        return themes[:limit], {tid: theme_articles_map[tid] for tid in [t.theme_id for t in themes[:limit]]}

    def save_themes_to_redshift(self, themes: list[Theme], theme_articles_map: dict[str, list[str]]) -> None:
        """
        Save themes and associations to Redshift via MCP.
        Saves to: public.themes (via save_theme) and public.theme_article_associations.

        Args:
            themes: List of Theme objects
            theme_articles_map: Dict mapping theme_id to list of article_hashes
        """
        logger.info(
            "[ThemeProcessor.save_themes_to_redshift] starting — table=public.themes count=%d",
            len(themes),
        )
        with self.mcp_client as client:
            names = build_tool_name_map(client, ["save_theme", "save_theme_article_association"])
            for theme in themes:
                theme_dict = _build_save_theme_args(theme)
                logger.info(
                    "[ThemeProcessor.save_themes_to_redshift] calling save_theme"
                    " — table=public.themes theme_id=%s client_id=%s ticker=%s rank=%s score=%.4f",
                    theme.theme_id,
                    theme.client_id,
                    theme.ticker,
                    theme.rank,
                    theme.score or 0.0,
                )
                result = client.call_tool_sync(f"save_theme_{theme.theme_id}", names["save_theme"], theme_dict)
                result_json = extract_mcp_data(result)
                if isinstance(result_json, dict) and result_json.get("error"):
                    raise RuntimeError(
                        f"save_theme failed for theme_id={theme.theme_id}"
                        f" client_id={theme.client_id}"
                        f" table=public.themes: {result_json['error']}"
                    )
                logger.info(
                    "[ThemeProcessor.save_themes_to_redshift] saved theme_id=%s client_id=%s → table=public.themes OK",
                    theme.theme_id,
                    theme.client_id,
                )

                # Save associations
                article_hashes = theme_articles_map.get(theme.theme_id, [])
                logger.info(
                    "[ThemeProcessor.save_themes_to_redshift] saving %d article associations"
                    " → table=public.theme_article_associations theme_id=%s",
                    len(article_hashes),
                    theme.theme_id,
                )
                for article_hash in article_hashes:
                    assoc_result = client.call_tool_sync(
                        f"save_assoc_{theme.theme_id}_{article_hash[:8]}",
                        names["save_theme_article_association"],
                        {
                            "theme_id": theme.theme_id,
                            "article_hash": article_hash,
                            "client_id": "__GENERAL__",
                        },
                    )
                    try:
                        assoc_json = extract_mcp_data(assoc_result)
                    except RuntimeError:
                        assoc_json = {}
                    if isinstance(assoc_json, dict) and assoc_json.get("error"):
                        logger.warning(
                            "[ThemeProcessor.save_themes_to_redshift]"
                            " save_theme_article_association failed"
                            " — table=public.theme_article_associations theme_id=%s"
                            " article_hash=%s error=%s",
                            theme.theme_id,
                            article_hash[:8],
                            assoc_json["error"],
                        )
        logger.info(
            "[ThemeProcessor.save_themes_to_redshift] completed — table=public.themes saved %d themes",
            len(themes),
        )


class PortfolioThemeProcessor(ThemeProcessor):
    """Extends ThemeProcessor to filter and generate portfolio-specific themes"""

    def __init__(
        self,
        mcp_client,
        bedrock_region: str = "us-east-1",
        use_cross_region: bool = True,
    ):
        """Initialize portfolio theme processor"""
        super().__init__(mcp_client, bedrock_region, use_cross_region)

    def get_portfolio_relevant_articles(
        self, portfolio_tickers: list[str], hours: int = 48, min_relevance: int = 30
    ) -> list[Article]:
        """
        Filter articles by portfolio relevance using AI

        Args:
            portfolio_tickers: List of stock tickers in portfolio
            hours: Look back period in hours
            min_relevance: Minimum relevance score (0-100)

        Returns:
            List of portfolio-relevant Article objects
        """
        # Get all recent articles
        all_articles = self.get_recent_articles(hours=hours)

        if not all_articles:
            return []

        portfolio_articles = []

        # Batch articles for efficiency (process 5 at a time)
        batch_size = 5
        for i in range(0, len(all_articles), batch_size):
            batch = all_articles[i : i + batch_size]

            # Prepare batch prompt
            articles_text = ""
            for idx, article in enumerate(batch, 1):
                articles_text += f"{idx}. Title: {article.title}\n"
                articles_text += f"   Source: {article.source}\n"
                articles_text += f"   Summary: {article.summary[:300] if article.summary else 'N/A'}\n\n"

            prompt = f"""Analyze which articles are relevant to a stock portfolio.

Portfolio Stocks: {", ".join(portfolio_tickers)}

Articles:
{articles_text}

Task: For each article, determine if it's relevant to the portfolio.

Consider:
1. Direct mentions of portfolio companies (highest relevance)
2. Industry/sector relevance
3. Supply chain relationships
4. Competitive dynamics
5. Market trends affecting portfolio sectors

Scoring Guide:
- 80-100: Directly mentions portfolio companies
- 50-79: Discusses sector/industry of portfolio companies
- 30-49: Related market trends
- 0-29: Not relevant

Return ONLY valid JSON (no markdown, no extra text):
{{
  "articles": [
    {{"article_number": 1, "relevance_score": 0-100, "matched_tickers": ["AAPL"], "reasoning": "Brief explanation"}},
    {{"article_number": 2, "relevance_score": 0-100, "matched_tickers": [], "reasoning": "Brief explanation"}}
  ]
}}"""

            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = self.bedrock.invoke_model(modelId=self.model_id, body=json.dumps(request_body))
            response_body = json.loads(response["body"].read())
            response_text = response_body["content"][0]["text"].strip()

            # Clean response
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()

            result = json.loads(_strip_code_fences(response_text))

            # Filter articles by relevance
            for article_result in result.get("articles", []):
                article_idx = article_result["article_number"] - 1
                if article_idx < len(batch) and article_result["relevance_score"] >= min_relevance:
                    portfolio_articles.append(batch[article_idx])

        return portfolio_articles

    def generate_stock_specific_themes(
        self, client_id: str, ticker: str, hours: int = 48, themes_per_stock: int = 3, security_name: str = None
    ) -> tuple[list[Theme], dict[str, list[str]]]:
        """Synchronous wrapper — delegates to async implementation via a dedicated thread."""
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                self._generate_stock_specific_themes_async(
                    client_id=client_id,
                    ticker=ticker,
                    hours=hours,
                    themes_per_stock=themes_per_stock,
                    security_name=security_name,
                ),
            )
            return future.result()

    async def _generate_stock_specific_themes_async(
        self, client_id: str, ticker: str, hours: int = 48, themes_per_stock: int = 3, security_name: str = None
    ) -> tuple[list[Theme], dict[str, list[str]]]:
        """
        Async implementation: article scoring batches run concurrently, summaries run concurrently.

        Args:
            client_id: Client identifier
            ticker: Stock ticker symbol
            hours: Look back period in hours
            themes_per_stock: Number of themes to generate for this stock
            security_name: Optional security name for better context

        Returns:
            Tuple of (list of Theme objects for this stock, article associations map)
        """
        stock_articles = await self._get_stock_specific_articles_async(ticker, hours=hours, security_name=security_name)

        if len(stock_articles) < 3:
            logger.warning(
                "[generate_stock_specific_themes] ticker=%s only %d articles (need 3+)", ticker, len(stock_articles)
            )
            return [], {}

        themes_data = self.identify_themes_for_stock(stock_articles, ticker, themes_per_stock)

        loop = asyncio.get_running_loop()

        async def build_theme(theme_data: dict) -> tuple[Theme, list[str]]:
            score, score_breakdown = self.calculate_theme_score(theme_data, stock_articles)
            # Capture theme_data in default arg to avoid closure rebinding across concurrent calls
            summary = await loop.run_in_executor(None, lambda td=theme_data: self.generate_summary(td, stock_articles))
            title_hash = hashlib.md5(theme_data["title"].encode(), usedforsecurity=False).hexdigest()[:16]
            theme_id = f"stock_{client_id}_{ticker}_{title_hash}"
            theme = Theme(
                theme_id=theme_id,
                client_id=client_id,
                ticker=ticker,
                title=theme_data["title"],
                sentiment=theme_data["sentiment"],
                article_count=theme_data["article_count"],
                sources=theme_data["sources"],
                created_at=datetime.now(),
                summary=summary,
                updated_at=datetime.now(),
                score=score,
                rank=0,
                score_breakdown=score_breakdown,
                generated_at=datetime.now(),
                relevance_score=100.0,
                combined_score=score,
                matched_tickers=[ticker],
                relevance_reasoning=f"Theme generated specifically for {ticker} from articles mentioning this stock",
            )
            return theme, theme_data["article_hashes"]

        # Generate all summaries concurrently
        results = await asyncio.gather(*[build_theme(td) for td in themes_data], return_exceptions=True)

        stock_themes = []
        theme_articles_map = {}
        for result in results:
            if isinstance(result, Exception):
                logger.warning("[generate_stock_specific_themes] ticker=%s theme build failed: %s", ticker, result)
                continue
            theme, article_hashes = result
            stock_themes.append(theme)
            theme_articles_map[theme.theme_id] = article_hashes

        stock_themes.sort(key=lambda t: t.score, reverse=True)
        for rank, theme in enumerate(stock_themes[:themes_per_stock], 1):
            theme.rank = rank

        return stock_themes[:themes_per_stock], theme_articles_map

    def get_stock_specific_articles(self, ticker: str, hours: int = 48, security_name: str = None) -> list[Article]:
        """
        Synchronous wrapper — runs the async implementation.
        Uses a new event loop in a thread to avoid conflicts when called from an existing loop.
        """
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                self._get_stock_specific_articles_async(ticker, hours=hours, security_name=security_name),
            )
            return future.result()

    async def _get_stock_specific_articles_async(
        self, ticker: str, hours: int = 48, security_name: str = None
    ) -> list[Article]:
        """
        Async implementation: scores all article batches concurrently via thread pool.

        Args:
            ticker: Stock ticker symbol
            hours: Look back period in hours
            security_name: Optional security name for better context

        Returns:
            List of Article objects mentioning the ticker or relevant to its sector
        """
        all_articles = self.get_recent_articles(hours=hours)

        if not all_articles:
            return []

        security_context = f" ({security_name})" if security_name else ""
        batch_size = 10
        batches = [all_articles[i : i + batch_size] for i in range(0, len(all_articles), batch_size)]

        loop = asyncio.get_running_loop()

        async def score_batch(batch: list[Article]) -> list[Article]:
            articles_text = ""
            for idx, article in enumerate(batch, 1):
                articles_text += f"{idx}. Title: {article.title}\n"
                articles_text += f"   Source: {article.source}\n"
                articles_text += f"   Summary: {article.summary[:300] if article.summary else 'N/A'}\n\n"

            prompt = f"""Analyze which articles are relevant to the security {ticker}{security_context}.

Articles:
{articles_text}

Task: For each article, determine if it's relevant to {ticker}.

Consider BOTH:
1. DIRECT RELEVANCE (highest priority):
   - Direct mentions of ticker "{ticker}"
   - Mentions of the company/fund name
   - Discussion of the specific security's performance or news

2. SECTOR/CATEGORY RELEVANCE (for ETFs and funds):
   - For bond ETFs (VCSH, MINT): articles about corporate bonds, bond yields, fixed income, interest rates
   - For real estate ETFs (IYR): articles about real estate market, REITs, property sector
   - For dividend ETFs (SCHD): articles about dividend stocks, income investing, high-yield equities
   - For individual stocks (ACN): articles about the company's industry/sector

Scoring Guide:
- 80-100: Direct mention of {ticker} or primary focus on its exact sector
- 50-79: Discusses the broader sector/category that {ticker} represents
- 30-49: Related market trends that impact {ticker}'s sector
- 0-29: Not relevant

Return ONLY valid JSON (no markdown, no extra text):
{{
  "articles": [
    {{"article_number": 1, "relevance_score": 0-100, "reasoning": "Brief explanation"}},
    {{"article_number": 2, "relevance_score": 0-100, "reasoning": "Brief explanation"}}
  ]
}}"""

            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = await loop.run_in_executor(
                None,
                lambda: self.bedrock.invoke_model(modelId=self.model_id, body=json.dumps(request_body)),
            )
            response_body = json.loads(response["body"].read())
            response_text = response_body["content"][0]["text"].strip()

            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()

            result = json.loads(_strip_code_fences(response_text))

            matched = []
            for article_result in result.get("articles", []):
                article_idx = article_result["article_number"] - 1
                if article_idx < len(batch) and article_result["relevance_score"] >= 40:
                    matched.append(batch[article_idx])
            return matched

        # Fire all batches concurrently
        logger.info("[get_stock_specific_articles] ticker=%s scoring %d batches concurrently", ticker, len(batches))
        batch_results = await asyncio.gather(*[score_batch(b) for b in batches], return_exceptions=True)

        stock_articles = []
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.warning("[get_stock_specific_articles] ticker=%s batch %d failed: %s", ticker, i, result)
            else:
                stock_articles.extend(result)

        logger.info("[get_stock_specific_articles] ticker=%s found %d relevant articles", ticker, len(stock_articles))
        return stock_articles

    def identify_themes_for_stock(self, articles: list[Article], ticker: str, limit: int = 3) -> list[dict]:
        """
        Identify themes specifically for a stock from its articles.

        Args:
            articles: List of Article objects mentioning the stock
            ticker: Stock ticker symbol
            limit: Number of themes to generate

        Returns:
            List of theme dictionaries
        """
        if len(articles) < 3:
            raise ValueError(f"Need at least 3 articles for {ticker}, found {len(articles)}")

        # Create stock-specific prompt
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"{i}. {article.title}\n"
            articles_text += f"   Source: {article.source}\n"
            articles_text += f"   Summary: {article.summary[:200] if article.summary else ''}...\n\n"

        prompt = f"""Analyze these articles about {ticker} and identify {limit} major themes or topics.

Requirements:
- Each theme must be supported by at least 2 articles
- Themes should be SPECIFIC to {ticker} (not generic market trends)
- Focus on: company performance, product launches, strategic moves, financial results, market position
- Provide a concise title for each theme (10-15 words)
- Determine sentiment for each theme: bullish, bearish, or neutral

Articles about {ticker} ({len(articles)} total):
{articles_text}

Return your analysis in this exact JSON format:
{{
  "themes": [
    {{
      "title": "Concise {ticker}-specific theme title (10-15 words)",
      "article_indices": [1, 3],
      "sentiment": "bullish",
      "rationale": "Brief explanation of why these articles form a coherent theme about {ticker}"
    }}
  ]
}}

Important:
- Return ONLY the JSON, no other text
- Ensure article_indices reference the article numbers above
- Each theme must have at least 2 articles
- Identify exactly {limit} themes
- Sentiment must be exactly: "bullish", "bearish", or "neutral"
- Themes must be SPECIFIC to {ticker}, not general market themes
"""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = self.bedrock.invoke_model(modelId=self.model_id, body=json.dumps(request_body))
        response_body = json.loads(response["body"].read())
        response_text = response_body["content"][0]["text"]

        # Parse JSON response
        themes_data = json.loads(_strip_code_fences(response_text))

        # Validate and enrich themes
        validated_themes = []
        for theme in themes_data.get("themes", []):
            if len(theme.get("article_indices", [])) < 2:
                continue

            # Get article hashes and sources
            article_hashes = []
            sources = set()

            for idx in theme.get("article_indices", []):
                if 1 <= idx <= len(articles):
                    article = articles[idx - 1]
                    article_hashes.append(article.content_hash)
                    if article.source:
                        sources.add(article.source)

            validated_themes.append(
                {
                    "title": theme["title"],
                    "sentiment": theme.get("sentiment", "neutral").lower(),
                    "article_hashes": article_hashes,
                    "article_count": len(article_hashes),
                    "sources": list(sources),
                }
            )

        return validated_themes[:limit]

    def generate_portfolio_themes_by_stock(
        self, client_id: str, top_n_stocks: int = 5, hours: int = 48, themes_per_stock: int = 3
    ) -> tuple[list[Theme], dict[str, list[str]]]:
        """
        Generate themes for each of the top N stocks concurrently, saving each ticker's
        themes to Redshift as soon as they're ready (partial progress is preserved on restart).
        Runs async implementation in a dedicated thread to avoid event loop conflicts.
        """
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                self._generate_portfolio_themes_by_stock_async(
                    client_id=client_id,
                    top_n_stocks=top_n_stocks,
                    hours=hours,
                    themes_per_stock=themes_per_stock,
                ),
            )
            return future.result()

    async def _generate_portfolio_themes_by_stock_async(
        self, client_id: str, top_n_stocks: int = 5, hours: int = 48, themes_per_stock: int = 3
    ) -> tuple[list[Theme], dict[str, list[str]]]:
        """Async implementation: all tickers processed concurrently, saved per ticker."""
        # Get top holdings via MCP (sync call — fast, just a DB query)
        with self.mcp_client as client:
            names = build_tool_name_map(client, ["get_top_holdings_by_aum"])
            result = client.call_tool_sync(
                "get_top_holdings_001",
                names["get_top_holdings_by_aum"],
                {"client_id": client_id, "limit": top_n_stocks},
            )
            response = extract_mcp_data(result)
            top_holdings = response.get("holdings", []) if isinstance(response, dict) else response

        if not top_holdings:
            raise ValueError(f"No holdings found for client {client_id}")

        logger.info(
            "[generate_portfolio_themes_by_stock] client=%s processing %d tickers concurrently",
            client_id,
            len(top_holdings),
        )

        async def process_and_save_ticker(holding: dict) -> tuple[list[Theme], dict[str, list[str]]]:
            ticker = holding["ticker"]
            security_name = holding.get("security_name")
            try:
                themes, theme_articles_map = await self._generate_stock_specific_themes_async(
                    client_id=client_id,
                    ticker=ticker,
                    hours=hours,
                    themes_per_stock=themes_per_stock,
                    security_name=security_name,
                )
                if themes:
                    logger.info(
                        "[generate_portfolio_themes_by_stock] ticker=%s generated %d themes — saving now",
                        ticker,
                        len(themes),
                    )
                    # Each ticker gets its own MCP client — avoids shared connection state
                    # across concurrent saves.
                    # NOTE: We are already running inside a ThreadPoolExecutor thread
                    # (asyncio.run() was submitted via ThreadPoolExecutor in
                    # generate_portfolio_themes_by_stock). Calling _save_themes_with_client
                    # directly here is safe — it blocks this thread, not the Uvicorn event
                    # loop. Using run_in_executor here would nest blocking calls inside
                    # executor threads, risking thread-pool exhaustion / deadlock under
                    # concurrent ticker processing.
                    ticker_mcp = get_portfolio_mcp_client()
                    self._save_themes_with_client(themes, theme_articles_map, ticker_mcp)
                    logger.info("[generate_portfolio_themes_by_stock] ticker=%s saved to Redshift", ticker)
                else:
                    logger.warning("[generate_portfolio_themes_by_stock] ticker=%s no themes generated", ticker)
                return themes, theme_articles_map
            except Exception:
                logger.exception("[generate_portfolio_themes_by_stock] ticker=%s failed", ticker)
                return [], {}

        # All tickers run concurrently
        ticker_results = await asyncio.gather(*[process_and_save_ticker(h) for h in top_holdings])

        all_themes: list[Theme] = []
        all_theme_articles_map: dict[str, list[str]] = {}
        for themes, theme_articles_map in ticker_results:
            all_themes.extend(themes)
            all_theme_articles_map.update(theme_articles_map)

        return all_themes, all_theme_articles_map

    def _save_themes_with_client(
        self, themes: list[Theme], theme_articles_map: dict[str, list[str]], mcp_client
    ) -> None:
        """
        Save themes using an explicitly provided MCP client.
        Used by concurrent ticker processing to avoid shared mcp_client state.
        Saves to: public.themes (via save_theme) and
        public.theme_article_associations (via save_theme_article_association).
        """
        logger.info(
            "[_save_themes_with_client] starting — table=public.themes count=%d",
            len(themes),
        )
        with mcp_client as client:
            names = build_tool_name_map(client, ["save_theme", "save_theme_article_association"])
            for theme in themes:
                # Ensure list/dict fields are serialized to JSON strings —
                theme_dict = _build_save_theme_args(theme)
                logger.info(
                    "[_save_themes_with_client] calling save_theme — table=public.themes"
                    " theme_id=%s client_id=%s ticker=%s rank=%s score=%.4f",
                    theme.theme_id,
                    theme.client_id,
                    theme.ticker,
                    theme.rank,
                    theme.score or 0.0,
                )
                result = client.call_tool_sync(f"save_theme_{theme.theme_id}", names["save_theme"], theme_dict)
                # Surface save errors immediately rather than silently skipping
                result_json = extract_mcp_data(result)
                if isinstance(result_json, dict) and result_json.get("error"):
                    raise RuntimeError(
                        f"save_theme failed for theme_id={theme.theme_id}"
                        f" client_id={theme.client_id} ticker={theme.ticker}"
                        f" table=public.themes: {result_json['error']}"
                    )
                logger.info(
                    "[_save_themes_with_client] saved theme_id=%s client_id=%s ticker=%s → table=public.themes OK",
                    theme.theme_id,
                    theme.client_id,
                    theme.ticker,
                )

                article_hashes = theme_articles_map.get(theme.theme_id, [])
                logger.info(
                    "[_save_themes_with_client] saving %d article associations"
                    " → table=public.theme_article_associations theme_id=%s client_id=%s",
                    len(article_hashes),
                    theme.theme_id,
                    theme.client_id,
                )
                for article_hash in article_hashes:
                    assoc_result = client.call_tool_sync(
                        f"save_assoc_{theme.theme_id}_{article_hash[:8]}",
                        names["save_theme_article_association"],
                        {
                            "theme_id": theme.theme_id,
                            "article_hash": article_hash,
                            "client_id": theme.client_id,
                        },
                    )
                    try:
                        assoc_json = extract_mcp_data(assoc_result)
                    except RuntimeError:
                        assoc_json = {}
                    if isinstance(assoc_json, dict) and assoc_json.get("error"):
                        logger.warning(
                            "[_save_themes_with_client] save_theme_article_association failed"
                            " — table=public.theme_article_associations theme_id=%s"
                            " article_hash=%s client_id=%s error=%s",
                            theme.theme_id,
                            article_hash[:8],
                            theme.client_id,
                            assoc_json["error"],
                        )
        logger.info(
            "[_save_themes_with_client] completed — table=public.themes saved %d themes",
            len(themes),
        )

    def save_themes_to_redshift(self, themes: list[Theme], theme_articles_map: dict[str, list[str]]) -> None:
        """
        Save portfolio themes and associations to Redshift via MCP.
        Overrides parent method to use client_id from theme instead of __GENERAL__.
        Saves to: public.themes (via save_theme) and public.theme_article_associations.

        Args:
            themes: List of portfolio Theme objects
            theme_articles_map: Dict mapping theme_id to list of article_hashes
        """
        logger.info(
            "[PortfolioThemeProcessor.save_themes_to_redshift] starting — table=public.themes count=%d",
            len(themes),
        )
        with self.mcp_client as client:
            names = build_tool_name_map(client, ["save_theme", "save_theme_article_association"])
            for theme in themes:
                theme_dict = _build_save_theme_args(theme)
                logger.info(
                    "[PortfolioThemeProcessor.save_themes_to_redshift] calling save_theme"
                    " — table=public.themes theme_id=%s client_id=%s ticker=%s rank=%s score=%.4f",
                    theme.theme_id,
                    theme.client_id,
                    theme.ticker,
                    theme.rank,
                    theme.score or 0.0,
                )
                result = client.call_tool_sync(f"save_theme_{theme.theme_id}", names["save_theme"], theme_dict)
                result_json = extract_mcp_data(result)
                if isinstance(result_json, dict) and result_json.get("error"):
                    raise RuntimeError(
                        f"save_theme failed for theme_id={theme.theme_id}"
                        f" client_id={theme.client_id} ticker={theme.ticker}"
                        f" table=public.themes: {result_json['error']}"
                    )
                logger.info(
                    "[PortfolioThemeProcessor.save_themes_to_redshift] saved theme_id=%s"
                    " client_id=%s ticker=%s → table=public.themes OK",
                    theme.theme_id,
                    theme.client_id,
                    theme.ticker,
                )

                # Save associations with correct client_id
                article_hashes = theme_articles_map.get(theme.theme_id, [])
                logger.info(
                    "[PortfolioThemeProcessor.save_themes_to_redshift] saving %d article associations"
                    " → table=public.theme_article_associations theme_id=%s client_id=%s",
                    len(article_hashes),
                    theme.theme_id,
                    theme.client_id,
                )
                for article_hash in article_hashes:
                    assoc_result = client.call_tool_sync(
                        f"save_assoc_{theme.theme_id}_{article_hash[:8]}",
                        names["save_theme_article_association"],
                        {
                            "theme_id": theme.theme_id,
                            "article_hash": article_hash,
                            "client_id": theme.client_id,  # Use theme's client_id instead of __GENERAL__
                        },
                    )
                    try:
                        assoc_json = extract_mcp_data(assoc_result)
                    except RuntimeError:
                        assoc_json = {}
                    if isinstance(assoc_json, dict) and assoc_json.get("error"):
                        logger.warning(
                            "[PortfolioThemeProcessor.save_themes_to_redshift]"
                            " save_theme_article_association failed"
                            " — table=public.theme_article_associations theme_id=%s"
                            " article_hash=%s client_id=%s error=%s",
                            theme.theme_id,
                            article_hash[:8],
                            theme.client_id,
                            assoc_json["error"],
                        )
        logger.info(
            "[PortfolioThemeProcessor.save_themes_to_redshift] completed — table=public.themes saved %d themes",
            len(themes),
        )

    def delete_old_portfolio_themes(self, client_id: str, hours: int = 72) -> int:
        """
        Delete old portfolio themes for a client that are older than specified hours.

        This prevents accumulation of stale themes and ensures only fresh themes are displayed.

        Args:
            client_id: Client identifier
            hours: Delete themes older than this many hours (default: 72 = 3 days)

        Returns:
            Number of themes deleted
        """
        # Note: This requires adding a delete_portfolio_themes tool to Portfolio MCP
        # For now, we'll document this as a TODO
        # TODO: Add delete_portfolio_themes tool to Portfolio MCP
        _ = self.mcp_client  # Suppress unused warning
        return 0  # Not implemented yet

        return 0  # Placeholder until MCP tool is added

    def process_portfolio_themes(
        self,
        client_id: str,
        top_n_stocks: int = 5,
        themes_per_stock: int = 3,
        hours: int = 48,
    ) -> tuple[list[Theme], dict[str, list[str]]]:
        """
        Complete portfolio theme processing with per-stock generation.

        Args:
            client_id: Client identifier
            top_n_stocks: Number of top holdings by AUM to generate themes for (default: 5)
            themes_per_stock: Number of themes to generate per stock (default: 3)
            hours: Look back period in hours

        Returns:
            Tuple of (list of portfolio Theme objects, article associations map)
        """
        return self.generate_portfolio_themes_by_stock(
            client_id=client_id, top_n_stocks=top_n_stocks, hours=hours, themes_per_stock=themes_per_stock
        )

    def get_portfolio_themes(self, client_id: str, limit: int = 15) -> list[Theme]:
        """Get portfolio-specific themes from Redshift via MCP (grouped by stock)"""
        with self.mcp_client as client:
            names = build_tool_name_map(client, ["get_portfolio_themes"])
            result = client.call_tool_sync(
                "get_portfolio_themes_001", names["get_portfolio_themes"], {"client_id": client_id, "limit": limit}
            )
            themes_data = extract_mcp_data(result)
            return [Theme(**theme) for theme in themes_data]
