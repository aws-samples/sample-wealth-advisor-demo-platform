"""
Theme Processor - Identifies, ranks, and summarizes themes from articles
Combines theme identification, ranking, and summary generation
"""

import hashlib
import json
import os
import re
from datetime import datetime, timedelta

import boto3
from botocore.config import Config
from wealth_management_portal_common_market_events.models import Article, Theme, ThemeArticleAssociation
from wealth_management_portal_common_market_events.redshift import RedshiftClient


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from LLM responses."""
    return re.sub(r"^```(?:json)?\s*\n?", "", re.sub(r"\n?```\s*$", "", text.strip()))


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
        workgroup: str = "financial-advisor-wg",
        database: str = "financial-advisor-db",
        region: str = "us-west-2",
        bedrock_region: str = "us-east-1",
        use_cross_region: bool = True,
    ):
        """
        Initialize theme processor

        Args:
            workgroup: Redshift workgroup name
            database: Redshift database name
            region: AWS region for Redshift
            bedrock_region: AWS region for Bedrock
            use_cross_region: Whether to use cross-region inference profile
        """
        # Initialize Redshift client
        self.redshift = RedshiftClient(workgroup=workgroup, database=database, region=region)

        # Initialize Bedrock client
        config = Config(region_name=bedrock_region, retries={"max_attempts": 3, "mode": "adaptive"})
        self.bedrock = boto3.client("bedrock-runtime", config=config)
        self.use_cross_region = use_cross_region

        # Model ID
        self.model_id = os.environ.get("THEME_BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

    def get_recent_articles(self, hours: int = 48) -> list[Article]:
        """
        Get articles from the last N hours from Redshift

        Args:
            hours: Number of hours to look back

        Returns:
            List of Article objects
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        sql = f"""
        SELECT * FROM articles
        WHERE published_date >= '{cutoff.isoformat()}'
        ORDER BY published_date DESC
        """
        statement_id = self.redshift.execute_statement(sql)
        rows = self.redshift.get_statement_result(statement_id)
        return [Article(**row) for row in rows]

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
        Save themes and associations to Redshift

        Args:
            themes: List of Theme objects
            theme_articles_map: Dict mapping theme_id to list of article_hashes
        """
        for theme in themes:
            # Insert theme
            self.redshift.insert_theme(theme)

            # Insert associations
            article_hashes = theme_articles_map.get(theme.theme_id, [])
            for article_hash in article_hashes:
                association = ThemeArticleAssociation(
                    theme_id=theme.theme_id, article_hash=article_hash, client_id="__GENERAL__"
                )
                self.redshift.insert_theme_article_association(association)

    def get_general_themes(self, limit: int = 10) -> list[Theme]:
        """Get general market themes from Redshift"""
        return self.redshift.get_general_themes(limit=limit)


class PortfolioThemeProcessor(ThemeProcessor):
    """Extends ThemeProcessor to filter and generate portfolio-specific themes"""

    def __init__(
        self,
        workgroup: str = "financial-advisor-wg",
        database: str = "financial-advisor-db",
        region: str = "us-west-2",
        profile_name: str = "wealth_management",
        bedrock_region: str = "us-east-1",
        use_cross_region: bool = True,
    ):
        """Initialize portfolio theme processor"""
        # Note: profile_name is accepted but not used by parent class
        super().__init__(workgroup, database, region, bedrock_region, use_cross_region)

    def calculate_portfolio_relevance(
        self, theme: Theme, articles: list[Article], portfolio_tickers: list[str]
    ) -> dict[str, any]:
        """
        Calculate theme relevance to a portfolio using Bedrock

        Args:
            theme: Theme object
            articles: List of Article objects for this theme
            portfolio_tickers: List of stock tickers in portfolio

        Returns:
            Dict with relevance_score, matched_tickers, and reasoning
        """
        # Prepare article context (limit to 5 articles)
        articles_text = ""
        for i, article in enumerate(articles[:5], 1):
            articles_text += f"{i}. {article.title}\n"
            articles_text += f"   {article.summary[:200] if article.summary else ''}\n\n"

        prompt = f"""Analyze if this market theme is relevant to a stock portfolio.

Portfolio Stocks: {", ".join(portfolio_tickers)}

Theme Title: {theme.title}
Theme Summary: {theme.summary}
Theme Sentiment: {theme.sentiment}

Supporting Articles:
{articles_text}

Task: Determine relevance to the portfolio.

Consider:
1. Direct mentions of portfolio companies (highest relevance)
2. Industry/sector relevance (e.g., if portfolio has tech stocks and theme is about tech sector)
3. Supply chain relationships (e.g., TSMC supplies chips to Apple)
4. Competitive dynamics (e.g., competitors of portfolio companies)
5. Market trends affecting portfolio sectors

Scoring Guide:
- 80-100: Directly mentions portfolio companies or highly relevant to their business
- 50-79: Discusses sector/industry of portfolio companies
- 20-49: Tangentially related (e.g., broader market trends)
- 0-19: Not relevant to portfolio

Return ONLY valid JSON (no markdown, no extra text):
{{
  "relevance_score": 0-100,
  "matched_tickers": ["AAPL", "AMZN"],
  "reasoning": "Brief explanation of why relevant or not"
}}"""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
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
        return result

    def filter_themes_by_portfolio(
        self, client_id: str, portfolio_tickers: list[str], min_relevance: int = 30, limit: int = 5
    ) -> tuple[list[Theme], dict[str, list[str]]]:
        """
        Filter existing general themes by portfolio relevance

        Args:
            client_id: Client identifier
            portfolio_tickers: List of stock tickers in portfolio
            min_relevance: Minimum relevance score (0-100)
            limit: Maximum number of themes to return

        Returns:
            Tuple of (list of portfolio-relevant Theme objects, article associations map)
        """
        # Get general themes
        general_themes = self.redshift.get_general_themes(limit=20)

        if not general_themes:
            raise ValueError("No general themes found. Run process_market_themes first.")

        # Evaluate each theme for portfolio relevance
        portfolio_themes = []
        theme_articles_map = {}

        for theme in general_themes:
            # Get articles for this theme
            theme_articles = self.redshift.get_theme_articles(theme.theme_id, client_id="__GENERAL__")

            if not theme_articles:
                continue

            # Calculate portfolio relevance
            relevance = self.calculate_portfolio_relevance(theme, theme_articles, portfolio_tickers)

            if relevance["relevance_score"] >= min_relevance:
                # Create portfolio-specific theme
                portfolio_theme = Theme(
                    theme_id=f"portfolio_{client_id}_{theme.theme_id}",
                    client_id=client_id,
                    title=theme.title,
                    sentiment=theme.sentiment,
                    article_count=theme.article_count,
                    sources=theme.sources,
                    created_at=datetime.now(),
                    summary=theme.summary,
                    updated_at=datetime.now(),
                    score=theme.score,
                    rank=0,  # Will be set after sorting
                    score_breakdown=theme.score_breakdown,
                    generated_at=datetime.now(),
                    relevance_score=relevance["relevance_score"],
                    combined_score=(theme.score * 0.4) + (relevance["relevance_score"] * 0.6),
                    matched_tickers=relevance.get("matched_tickers", []),
                    relevance_reasoning=relevance.get("reasoning", ""),
                )
                portfolio_themes.append(portfolio_theme)
                theme_articles_map[portfolio_theme.theme_id] = [a.content_hash for a in theme_articles]

        # Sort by combined score
        portfolio_themes.sort(key=lambda t: t.combined_score, reverse=True)

        # Assign ranks
        for rank, theme in enumerate(portfolio_themes[:limit], 1):
            theme.rank = rank

        return portfolio_themes[:limit], theme_articles_map

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

    def generate_portfolio_themes_directly(
        self, client_id: str, portfolio_tickers: list[str], hours: int = 48, limit: int = 5
    ) -> tuple[list[Theme], dict[str, list[str]]]:
        """
        Generate themes directly from portfolio-relevant articles (Approach 2)

        Args:
            client_id: Client identifier
            portfolio_tickers: List of stock tickers in portfolio
            hours: Look back period in hours
            limit: Maximum number of themes to return

        Returns:
            Tuple of (list of portfolio Theme objects, article associations map)
        """
        # Step 1: Filter articles by portfolio relevance
        portfolio_articles = self.get_portfolio_relevant_articles(portfolio_tickers, hours=hours, min_relevance=30)

        if not portfolio_articles:
            raise ValueError(f"No portfolio-relevant articles found for client {client_id}")

        # Step 2: Generate themes from portfolio-relevant articles
        themes_data = self.identify_themes(portfolio_articles)

        # Step 3: Process themes
        portfolio_themes = []
        theme_articles_map = {}

        for theme_data in themes_data:
            # Calculate score
            score, score_breakdown = self.calculate_theme_score(theme_data, portfolio_articles)

            # Generate summary
            summary = self.generate_summary(theme_data, portfolio_articles)

            # Create theme
            title_hash = hashlib.md5(theme_data["title"].encode(), usedforsecurity=False).hexdigest()[:16]
            theme_id = f"portfolio_{client_id}_{title_hash}"
            theme = Theme(
                theme_id=theme_id,
                client_id=client_id,
                title=theme_data["title"],
                sentiment=theme_data["sentiment"],
                article_count=theme_data["article_count"],
                sources=theme_data["sources"],
                created_at=datetime.now(),
                summary=summary,
                updated_at=datetime.now(),
                score=score,
                rank=0,  # Will be set after sorting
                score_breakdown=score_breakdown,
                generated_at=datetime.now(),
                relevance_score=100.0,  # All articles are pre-filtered for relevance
                combined_score=score,  # No need to blend since all articles are relevant
                matched_tickers=portfolio_tickers,
                relevance_reasoning="Generated directly from portfolio-relevant articles",
            )
            portfolio_themes.append(theme)

            # Map articles using article_hashes from theme_data
            theme_articles_map[theme_id] = theme_data["article_hashes"]

        # Sort by score
        portfolio_themes.sort(key=lambda t: t.score, reverse=True)

        # Assign ranks
        for rank, theme in enumerate(portfolio_themes[:limit], 1):
            theme.rank = rank

        return portfolio_themes[:limit], theme_articles_map

    def process_portfolio_themes(
        self,
        client_id: str,
        portfolio_tickers: list[str] | None = None,
        generation_mode: str = "direct",
        min_relevance: int = 30,
        hours: int = 48,
        limit: int = 5,
    ) -> tuple[list[Theme], dict[str, list[str]]]:
        """
        Complete portfolio theme processing with multiple generation modes

        Args:
            client_id: Client identifier
            portfolio_tickers: List of stock tickers (optional - fetched from Redshift if not provided)
            generation_mode: "direct" (Approach 2) or "filter" (filter general themes)
            min_relevance: Minimum relevance score (0-100) - used in filter mode
            hours: Look back period in hours - used in direct mode
            limit: Maximum number of themes to return

        Returns:
            Tuple of (list of portfolio Theme objects, article associations map)
        """
        # If tickers not provided, fetch from Redshift
        if portfolio_tickers is None:
            portfolio_tickers = self.redshift.get_client_portfolio_tickers(client_id)
            if not portfolio_tickers:
                raise ValueError(f"No portfolio holdings found for client {client_id}")

        if generation_mode == "direct":
            # Approach 2: Generate themes directly from portfolio-relevant articles
            return self.generate_portfolio_themes_directly(client_id, portfolio_tickers, hours=hours, limit=limit)
        elif generation_mode == "filter":
            # Original approach: Filter general themes by portfolio relevance
            return self.filter_themes_by_portfolio(client_id, portfolio_tickers, min_relevance, limit)
        else:
            raise ValueError(f"Invalid generation_mode: {generation_mode}. Must be 'direct' or 'filter'")

    def get_portfolio_themes(self, client_id: str, limit: int = 10) -> list[Theme]:
        """Get portfolio-specific themes from Redshift"""
        return self.redshift.get_portfolio_themes(client_id, limit=limit)

    def save_themes_to_redshift(self, themes: list[Theme], theme_articles_map: dict[str, list[str]]) -> None:
        """
        Save portfolio themes and associations to Redshift

        Overrides parent method to use client_id from theme instead of __GENERAL__

        Args:
            themes: List of portfolio Theme objects
            theme_articles_map: Dict mapping theme_id to list of article_hashes
        """
        for theme in themes:
            # Insert theme
            self.redshift.insert_theme(theme)

            # Insert associations with correct client_id
            article_hashes = theme_articles_map.get(theme.theme_id, [])
            for article_hash in article_hashes:
                association = ThemeArticleAssociation(
                    theme_id=theme.theme_id,
                    article_hash=article_hash,
                    client_id=theme.client_id,  # Use theme's client_id instead of __GENERAL__
                )
                self.redshift.insert_theme_article_association(association)
