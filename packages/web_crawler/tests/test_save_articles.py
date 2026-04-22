#!/usr/bin/env python3
"""
Test script to check Redshift and save articles
"""

import sys


def check_redshift_articles():
    """Check current articles in Redshift"""
    print("=" * 70)
    print("STEP 1: Checking current articles in Redshift")
    print("=" * 70)

    from wealth_management_portal_common_market_events.redshift import RedshiftClient

    try:
        client = RedshiftClient(
            workgroup="financial-advisor-wg",
            database="financial-advisor-db",
            region="us-west-2",
            profile_name="",  # Use environment variables
        )

        # Count articles
        sql = "SELECT COUNT(*) as count FROM articles"
        statement_id = client.execute_statement(sql)
        result = client.get_statement_result(statement_id)
        count = result[0]["count"] if result else 0

        print(f"\n✓ Current articles in Redshift: {count}")

        # Get sample articles
        if count > 0:
            sql = "SELECT title, source, published_date FROM articles ORDER BY created_at DESC LIMIT 5"
            statement_id = client.execute_statement(sql)
            articles = client.get_statement_result(statement_id)

            print("\nSample articles (latest 5):")
            for i, article in enumerate(articles, 1):
                print(f"  {i}. {article['title'][:60]}...")
                print(f"     Source: {article['source']}, Date: {article['published_date']}")

        return count

    except Exception as e:
        print(f"\n✗ Error checking Redshift: {e}")
        import traceback

        traceback.print_exc()
        return None


def save_articles_to_redshift():
    """Save new articles to Redshift"""
    print("\n" + "=" * 70)
    print("STEP 2: Crawling and saving new articles to Redshift")
    print("=" * 70)

    from wealth_management_portal_web_crawler.web_crawler_mcp.server import save_articles_to_redshift

    try:
        print("\nStarting crawl (RSS-only mode)...")
        print("This will take about 60-90 seconds...\n")

        result = save_articles_to_redshift(
            rss_only=True,
            workgroup="financial-advisor-wg",
            database="financial-advisor-db",
            region="us-west-2",
            profile_name="",  # Use environment variables
        )

        print(f"\n✓ Success: {result.get('success')}")
        print(f"  Articles saved: {result.get('articles_saved', 0)}")
        print(f"  Total crawled: {result.get('total_crawled', 0)}")
        print(f"  New articles: {result.get('new_articles', 0)}")
        print(f"  Duplicates skipped: {result.get('duplicates', 0)}")
        print(f"  Errors: {result.get('errors', 0)}")

        if result.get("sources"):
            print("\n  Sources breakdown:")
            for source, stats in result["sources"].items():
                print(f"    {source}: {stats.get('new', 0)} new, {stats.get('duplicates', 0)} duplicates")

        return result.get("success", False)

    except Exception as e:
        print(f"\n✗ Error saving articles: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_after_save():
    """Check articles count after saving"""
    print("\n" + "=" * 70)
    print("STEP 3: Verifying articles were saved")
    print("=" * 70)

    from wealth_management_portal_common_market_events.redshift import RedshiftClient

    try:
        client = RedshiftClient(
            workgroup="financial-advisor-wg",
            database="financial-advisor-db",
            region="us-west-2",
            profile_name="",
        )

        # Count articles
        sql = "SELECT COUNT(*) as count FROM articles"
        statement_id = client.execute_statement(sql)
        result = client.get_statement_result(statement_id)
        count = result[0]["count"] if result else 0

        print(f"\n✓ Total articles in Redshift: {count}")

        # Get latest articles
        sql = "SELECT title, source, published_date, created_at FROM articles ORDER BY created_at DESC LIMIT 10"
        statement_id = client.execute_statement(sql)
        articles = client.get_statement_result(statement_id)

        print("\nLatest 10 articles:")
        for i, article in enumerate(articles, 1):
            print(f"  {i}. {article['title'][:60]}...")
            print(f"     Source: {article['source']}, Published: {article['published_date']}")

        return count

    except Exception as e:
        print(f"\n✗ Error checking Redshift: {e}")
        return None


def main():
    """Run the complete test"""
    print("\n" + "=" * 70)
    print("WEB CRAWLER - SAVE ARTICLES TO REDSHIFT TEST")
    print("=" * 70)

    # Step 1: Check current state
    before_count = check_redshift_articles()

    if before_count is None:
        print("\n✗ Failed to connect to Redshift. Check your AWS credentials.")
        sys.exit(1)

    # Step 2: Save new articles
    success = save_articles_to_redshift()

    if not success:
        print("\n✗ Failed to save articles to Redshift.")
        sys.exit(1)

    # Step 3: Verify
    after_count = check_after_save()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Articles before: {before_count}")
    print(f"  Articles after: {after_count}")
    print(f"  New articles added: {after_count - before_count if after_count and before_count else 'Unknown'}")
    print("\n✓ Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
