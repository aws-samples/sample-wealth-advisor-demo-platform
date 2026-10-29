-- Athena views for S3 Tables (Iceberg) catalog
-- Execute against catalog: s3tablescatalog/financial-advisor-s3table, database: financial_advisor
-- These views replicate the Redshift views from redshift-views-s3tables.sql with Athena-compatible syntax.

-- View: latest_themes
-- Returns themes from the most recent generation batch (within 5 minutes of max generated_at per client_id)
CREATE OR REPLACE VIEW latest_themes AS
SELECT t.*
FROM themes t
WHERE t.generated_at >= (
    SELECT max(t2.generated_at) - interval '5' minute
    FROM themes t2
    WHERE t2.client_id = t.client_id
);

-- View: theme_articles
-- Joins theme_article_associations with articles to get article details for each theme
CREATE OR REPLACE VIEW theme_articles AS
SELECT
    ta.theme_id,
    ta.client_id,
    a.content_hash,
    a.title,
    a.url,
    a.source,
    a.published_date,
    a.summary
FROM theme_article_associations ta
JOIN articles a ON ta.article_hash = a.content_hash;

-- View: advisor_monthly_aum
-- Aggregates AUM by month across all advisors
CREATE OR REPLACE VIEW advisor_monthly_aum AS
SELECT
    c.advisor_id,
    date_trunc('month', p.period_end_date) AS report_month,
    sum(p.ending_value) AS total_aum
FROM performance p
JOIN portfolios pf ON CAST(p.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
JOIN clients c ON CAST(acc.client_id AS varchar) = CAST(c.client_id AS varchar)
GROUP BY c.advisor_id, date_trunc('month', p.period_end_date);

-- View: investor_monthly_aum
-- Aggregates AUM by month per client
CREATE OR REPLACE VIEW investor_monthly_aum AS
SELECT
    c.client_id,
    date_trunc('month', p.period_end_date) AS report_month,
    sum(p.ending_value) AS total_aum
FROM performance p
JOIN portfolios pf ON CAST(p.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
JOIN clients c ON CAST(acc.client_id AS varchar) = CAST(c.client_id AS varchar)
GROUP BY c.client_id, date_trunc('month', p.period_end_date);

-- View: client_search
-- Comprehensive client view used by the search API
CREATE OR REPLACE VIEW client_search AS
SELECT
    c.client_id,
    c.first_name AS client_first_name,
    c.last_name AS client_last_name,
    c.email AS client_email,
    c.phone AS client_phone,
    c.city AS client_city,
    c.state AS client_state,
    c.risk_tolerance,
    c.segment,
    c.status AS client_status,
    c.created_date AS client_since,
    c.advisor_id,
    COALESCE(aum.total_aum, 0) AS aum,
    COALESCE(aum.total_aum, 0) AS net_worth,
    COALESCE(perf.ytd_return, 0) AS ytd_performance,
    i.sentiment AS interaction_sentiment,
    cr.next_best_action,
    CAST(NULL AS integer) AS goals_on_track
FROM clients c
LEFT JOIN (
    SELECT acc.client_id, sum(p.ending_value) AS total_aum
    FROM performance p
    JOIN portfolios pf ON CAST(p.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
    JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
    WHERE p.period_end_date = (SELECT max(period_end_date) FROM performance)
    GROUP BY acc.client_id
) aum ON CAST(c.client_id AS varchar) = CAST(aum.client_id AS varchar)
LEFT JOIN (
    SELECT acc.client_id, avg(p.time_weighted_return) AS ytd_return
    FROM performance p
    JOIN portfolios pf ON CAST(p.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
    JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
    WHERE p.period_end_date >= date_trunc('year', current_date)
    GROUP BY acc.client_id
) perf ON CAST(c.client_id AS varchar) = CAST(perf.client_id AS varchar)
LEFT JOIN (
    SELECT client_id, sentiment,
           row_number() OVER (PARTITION BY client_id ORDER BY interaction_date DESC) AS rn
    FROM interactions
) i ON CAST(c.client_id AS varchar) = CAST(i.client_id AS varchar) AND i.rn = 1
LEFT JOIN (
    SELECT client_id, next_best_action,
           row_number() OVER (PARTITION BY client_id ORDER BY generated_date DESC) AS rn
    FROM client_reports
) cr ON CAST(c.client_id AS varchar) = CAST(cr.client_id AS varchar) AND cr.rn = 1
WHERE c.status = 'Active';

-- View: client_portfolio_holdings
-- Holdings with security details per client
CREATE OR REPLACE VIEW client_portfolio_holdings AS
SELECT
    c.client_id,
    h.portfolio_id,
    s.ticker,
    s.security_name,
    h.quantity,
    h.cost_basis,
    h.current_price,
    h.market_value,
    h.unrealized_gain_loss,
    h.as_of_date
FROM holdings h
JOIN portfolios pf ON CAST(h.portfolio_id AS varchar) = CAST(pf.portfolio_id AS varchar)
JOIN accounts acc ON CAST(pf.account_id AS varchar) = CAST(acc.account_id AS varchar)
JOIN clients c ON CAST(acc.client_id AS varchar) = CAST(c.client_id AS varchar)
LEFT JOIN securities s ON CAST(h.security_id AS varchar) = CAST(s.security_id AS varchar);
