CREATE TABLE public.accounts (
    account_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    client_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        account_type character varying(30) NOT NULL ENCODE lzo COLLATE case_sensitive,
        account_name character varying(255) NOT NULL ENCODE lzo COLLATE case_sensitive,
        opening_date date NOT NULL ENCODE raw,
        investment_strategy character varying(50) ENCODE lzo COLLATE case_sensitive,
        status character varying(20) NOT NULL DEFAULT 'Active':: character varying ENCODE lzo COLLATE case_sensitive,
        current_balance numeric(18, 2) DEFAULT 0 ENCODE az64,
        PRIMARY KEY (account_id)
) DISTSTYLE KEY
SORTKEY
    (opening_date);

CREATE TABLE public.advisors (
    advisor_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    first_name character varying(100) NOT NULL ENCODE lzo COLLATE case_sensitive,
    last_name character varying(100) NOT NULL ENCODE raw COLLATE case_sensitive,
    email character varying(255) NOT NULL ENCODE lzo COLLATE case_sensitive,
    phone character varying(20) ENCODE lzo COLLATE case_sensitive,
    title character varying(100) ENCODE lzo COLLATE case_sensitive,
    credentials
        character varying(100) ENCODE lzo COLLATE case_sensitive,
        specialization character varying(100) ENCODE lzo COLLATE case_sensitive,
        years_experience integer ENCODE az64,
        hire_date date NOT NULL ENCODE az64,
        PRIMARY KEY (advisor_id)
) DISTSTYLE ALL
SORTKEY
    (last_name);

CREATE TABLE public.articles (
    content_hash character varying(64) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        url character varying(2000) NOT NULL ENCODE lzo COLLATE case_sensitive,
        title character varying(1000) ENCODE lzo COLLATE case_sensitive,
        content character varying(65535) ENCODE lzo COLLATE case_sensitive,
        summary character varying(10000) ENCODE lzo COLLATE case_sensitive,
        published_date timestamp without time zone ENCODE raw,
        source character varying(200) ENCODE raw COLLATE case_sensitive,
        author character varying(500) ENCODE lzo COLLATE case_sensitive,
        file_path character varying(500) ENCODE lzo COLLATE case_sensitive,
        created_at timestamp without time zone DEFAULT getdate() ENCODE az64,
        PRIMARY KEY (content_hash)
) DISTSTYLE KEY
SORTKEY
    (published_date, source);

CREATE TABLE public.client_income_expense (
    client_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    as_of_date date NOT NULL ENCODE az64,
    monthly_income numeric(18, 2) NOT NULL ENCODE az64,
    monthly_expenses numeric(18, 2) NOT NULL ENCODE az64,
    sustainability_years numeric(10, 2) NOT NULL ENCODE az64,
    PRIMARY KEY (client_id, as_of_date)
) DISTSTYLE AUTO;

CREATE TABLE public.client_investment_restrictions (
    restriction_id character varying(14) NOT NULL ENCODE lzo COLLATE case_sensitive,
    client_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    restriction character varying(255) NOT NULL ENCODE lzo COLLATE case_sensitive,
    created_date date DEFAULT ('now':: text):: date ENCODE az64,
    PRIMARY KEY (restriction_id)
) DISTSTYLE AUTO;

CREATE TABLE public.client_reports (
    report_id character varying(14) NOT NULL ENCODE lzo COLLATE case_sensitive,
    client_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    generated_date timestamp without time zone NOT NULL DEFAULT ('now':: text):: timestamp with time zone ENCODE az64,
    download_date timestamp without time zone ENCODE az64,
    status character varying(20) NOT NULL DEFAULT 'init':: character varying ENCODE lzo COLLATE case_sensitive,
    s3_path character varying(500) ENCODE lzo COLLATE case_sensitive,
    PRIMARY KEY (report_id)
) DISTSTYLE AUTO;

CREATE TABLE public.clients (
    client_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    first_name character varying(100) NOT NULL ENCODE lzo COLLATE case_sensitive,
    last_name character varying(100) NOT NULL ENCODE raw COLLATE case_sensitive,
    email character varying(255) NOT NULL ENCODE lzo COLLATE case_sensitive,
    phone character varying(20) ENCODE lzo COLLATE case_sensitive,
    address character varying(255) ENCODE lzo COLLATE case_sensitive,
    city character varying(100) ENCODE lzo COLLATE case_sensitive,
    state character varying(2) ENCODE lzo COLLATE case_sensitive,
    zip character varying(20) ENCODE lzo COLLATE case_sensitive,
    date_of_birth date ENCODE az64,
    risk_tolerance character varying(30) ENCODE lzo COLLATE case_sensitive,
    investment_objectives character varying(100) ENCODE lzo COLLATE case_sensitive,
    segment character varying(30) ENCODE lzo COLLATE case_sensitive,
    status character varying(20) NOT NULL DEFAULT 'Active':: character varying ENCODE lzo COLLATE case_sensitive,
    advisor_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        created_date date ENCODE az64,
        sophistication character varying(30) ENCODE lzo COLLATE case_sensitive,
        qualified_investor boolean DEFAULT false ENCODE raw,
        service_model character varying(30) ENCODE lzo COLLATE case_sensitive,
        PRIMARY KEY (client_id)
) DISTSTYLE KEY
SORTKEY
    (last_name);

CREATE TABLE public.compliance (
    compliance_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    client_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        kyc_status character varying(20) NOT NULL ENCODE lzo COLLATE case_sensitive,
        kyc_date date ENCODE az64,
        aml_status character varying(20) NOT NULL ENCODE lzo COLLATE case_sensitive,
        aml_date date ENCODE az64,
        suitability_status character varying(20) NOT NULL ENCODE lzo COLLATE case_sensitive,
        suitability_date date ENCODE az64,
        next_review_date date ENCODE raw,
        PRIMARY KEY (compliance_id)
) DISTSTYLE KEY
SORTKEY
    (next_review_date);

CREATE TABLE public.crawl_log (
    log_id bigint NOT NULL identity(1, 1) ENCODE az64,
    timestamp timestamp without time zone NOT NULL ENCODE raw,
    total_crawled integer ENCODE az64,
    new_articles integer ENCODE az64,
    duplicates integer ENCODE az64,
    errors integer ENCODE az64,
    sources_stats character varying(10000) ENCODE lzo COLLATE case_sensitive,
    created_at timestamp without time zone DEFAULT getdate() ENCODE az64,
    PRIMARY KEY (log_id)
) DISTSTYLE ALL
SORTKEY
    (timestamp);

CREATE TABLE public.documents (
    document_id character varying(14) NOT NULL ENCODE lzo COLLATE case_sensitive,
    client_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        account_id character varying(10) ENCODE lzo COLLATE case_sensitive,
        document_type character varying(30) NOT NULL ENCODE lzo COLLATE case_sensitive,
        document_name character varying(255) NOT NULL ENCODE lzo COLLATE case_sensitive,
        upload_date date NOT NULL ENCODE raw,
        file_size_kb integer ENCODE az64,
        storage_location character varying(500) ENCODE lzo COLLATE case_sensitive,
        PRIMARY KEY (document_id)
) DISTSTYLE KEY
SORTKEY
    (upload_date);

CREATE TABLE public.fees (
    fee_id character varying(14) NOT NULL ENCODE lzo COLLATE case_sensitive,
    account_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        fee_type character varying(30) NOT NULL ENCODE lzo COLLATE case_sensitive,
        fee_rate numeric(10, 4) ENCODE az64,
        billing_date date NOT NULL ENCODE raw,
        fee_amount numeric(18, 2) ENCODE az64,
        payment_status character varying(20) NOT NULL DEFAULT 'Pending':: character varying ENCODE lzo COLLATE case_sensitive,
        payment_date date ENCODE az64,
        PRIMARY KEY (fee_id)
) DISTSTYLE KEY
SORTKEY
    (billing_date);

CREATE TABLE public.goals (
    goal_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    client_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        goal_type character varying(30) NOT NULL ENCODE lzo COLLATE case_sensitive,
        goal_name character varying(255) NOT NULL ENCODE lzo COLLATE case_sensitive,
        target_amount numeric(18, 2) ENCODE az64,
        current_value numeric(18, 2) ENCODE az64,
        target_date date ENCODE raw,
        funding_status character varying(20) ENCODE lzo COLLATE case_sensitive,
        probability_of_success integer ENCODE az64,
        created_date date ENCODE az64,
        PRIMARY KEY (goal_id)
) DISTSTYLE KEY
SORTKEY
    (target_date);

CREATE TABLE public.holdings (
    position_id character varying(12) NOT NULL ENCODE lzo COLLATE case_sensitive,
    portfolio_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        security_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
        quantity numeric(14, 2) ENCODE az64,
        cost_basis numeric(12, 2) ENCODE az64,
        current_price numeric(12, 2) ENCODE az64,
        market_value numeric(18, 2) ENCODE az64,
        unrealized_gain_loss numeric(18, 2) ENCODE az64,
        as_of_date date NOT NULL ENCODE raw,
        PRIMARY KEY (position_id)
) DISTSTYLE KEY
SORTKEY
    (as_of_date);

CREATE TABLE public.interactions (
    interaction_id character varying(14) NOT NULL ENCODE lzo COLLATE case_sensitive,
    client_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        advisor_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
        interaction_type character varying(20) NOT NULL ENCODE lzo COLLATE case_sensitive,
        interaction_date date NOT NULL ENCODE raw,
        subject character varying(255) ENCODE lzo COLLATE case_sensitive,
        summary character varying(1000) ENCODE lzo COLLATE case_sensitive,
        sentiment character varying(20) ENCODE lzo COLLATE case_sensitive,
        duration_minutes integer ENCODE az64,
        PRIMARY KEY (interaction_id)
) DISTSTYLE KEY
SORTKEY
    (interaction_date);

CREATE TABLE public.market_data (
    market_data_id character varying(14) NOT NULL ENCODE lzo COLLATE case_sensitive,
    security_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        price_date date NOT NULL ENCODE raw,
        open_price numeric(12, 2) ENCODE az64,
        high_price numeric(12, 2) ENCODE az64,
        low_price numeric(12, 2) ENCODE az64,
        close_price numeric(12, 2) ENCODE az64,
        volume bigint ENCODE az64,
        PRIMARY KEY (market_data_id)
) DISTSTYLE KEY
SORTKEY
    (price_date);

CREATE TABLE public.performance (
    performance_id character varying(14) NOT NULL ENCODE lzo COLLATE case_sensitive,
    portfolio_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        period character varying(20) NOT NULL ENCODE lzo COLLATE case_sensitive,
        period_start_date date NOT NULL ENCODE raw,
        period_end_date date NOT NULL ENCODE az64,
        time_weighted_return numeric(10, 4) ENCODE az64,
        benchmark_return numeric(10, 4) ENCODE az64,
        beginning_value numeric(18, 2) ENCODE az64,
        ending_value numeric(18, 2) ENCODE az64,
        PRIMARY KEY (performance_id)
) DISTSTYLE KEY
SORTKEY
    (period_start_date);

CREATE TABLE public.portfolio_config (
    client_id character varying(100) NOT NULL ENCODE raw COLLATE case_sensitive,
    tickers character varying(1000) ENCODE lzo COLLATE case_sensitive,
    generated_at timestamp without time zone ENCODE az64,
    created_at timestamp without time zone DEFAULT getdate() ENCODE az64,
    updated_at timestamp without time zone DEFAULT getdate() ENCODE az64,
    PRIMARY KEY (client_id)
) DISTSTYLE ALL
SORTKEY
    (client_id);

CREATE TABLE public.portfolios (
    portfolio_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    account_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        portfolio_name character varying(255) NOT NULL ENCODE lzo COLLATE case_sensitive,
        investment_model character varying(30) ENCODE lzo COLLATE case_sensitive,
        target_allocation character varying(255) ENCODE lzo COLLATE case_sensitive,
        benchmark character varying(100) ENCODE lzo COLLATE case_sensitive,
        inception_date date NOT NULL ENCODE raw,
        PRIMARY KEY (portfolio_id)
) DISTSTYLE KEY
SORTKEY
    (inception_date);

CREATE TABLE public.recommended_products (
    product_id character varying(14) NOT NULL ENCODE lzo COLLATE case_sensitive,
    product_name character varying(255) NOT NULL ENCODE lzo COLLATE case_sensitive,
    product_type character varying(50) NOT NULL ENCODE lzo COLLATE case_sensitive,
    description character varying(1000) ENCODE lzo COLLATE case_sensitive,
    status character varying(20) NOT NULL DEFAULT 'Active':: character varying ENCODE lzo COLLATE case_sensitive,
    created_date date DEFAULT ('now':: text):: date ENCODE az64,
    PRIMARY KEY (product_id)
) DISTSTYLE AUTO;

CREATE TABLE public.research (
    research_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    security_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        research_type character varying(50) NOT NULL ENCODE lzo COLLATE case_sensitive,
        publication_date date NOT NULL ENCODE raw,
        rating character varying(20) ENCODE lzo COLLATE case_sensitive,
        target_price numeric(12, 2) ENCODE az64,
        analyst_name character varying(100) ENCODE lzo COLLATE case_sensitive,
        analyst_firm character varying(100) ENCODE lzo COLLATE case_sensitive,
        summary character varying(1000) ENCODE lzo COLLATE case_sensitive,
        PRIMARY KEY (research_id)
) DISTSTYLE KEY
SORTKEY
    (publication_date);

CREATE TABLE public.securities (
    security_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    ticker character varying(10) NOT NULL ENCODE raw COLLATE case_sensitive,
    security_name character varying(255) NOT NULL ENCODE lzo COLLATE case_sensitive,
    security_type character varying(30) NOT NULL ENCODE lzo COLLATE case_sensitive,
    asset_class character varying(30) ENCODE lzo COLLATE case_sensitive,
    sector character varying(50) ENCODE lzo COLLATE case_sensitive,
    current_price numeric(12, 2) ENCODE az64,
    price_date date ENCODE az64,
    PRIMARY KEY (security_id)
) DISTSTYLE ALL
SORTKEY
    (ticker);

CREATE TABLE public.theme_article_associations (
    theme_id character varying(100) NOT NULL ENCODE raw COLLATE case_sensitive,
    article_hash character varying(64) NOT NULL ENCODE raw COLLATE case_sensitive,
    client_id character varying(100) NOT NULL DEFAULT '__GENERAL__':: character varying ENCODE raw COLLATE case_sensitive
    distkey
,
        created_at timestamp without time zone DEFAULT getdate() ENCODE az64,
        PRIMARY KEY (theme_id, article_hash, client_id)
) DISTSTYLE KEY
SORTKEY
    (client_id, theme_id, article_hash);

CREATE TABLE public.themes (
    theme_id character varying(100) NOT NULL ENCODE lzo COLLATE case_sensitive,
    client_id character varying(100) NOT NULL DEFAULT '__GENERAL__':: character varying ENCODE raw COLLATE case_sensitive
    distkey
,
        title character varying(500) NOT NULL ENCODE lzo COLLATE case_sensitive,
        sentiment character varying(20) ENCODE lzo COLLATE case_sensitive,
        article_count integer ENCODE az64,
        sources character varying(5000) ENCODE lzo COLLATE case_sensitive,
        created_at timestamp without time zone ENCODE raw,
        summary character varying(10000) ENCODE lzo COLLATE case_sensitive,
        updated_at timestamp without time zone ENCODE az64,
        score numeric(10, 2) ENCODE az64,
        rank integer ENCODE raw,
        score_breakdown character varying(1000) ENCODE lzo COLLATE case_sensitive,
        generated_at timestamp without time zone ENCODE az64,
        relevance_score numeric(10, 2) ENCODE az64,
        combined_score numeric(10, 2) ENCODE az64,
        matched_tickers character varying(500) ENCODE lzo COLLATE case_sensitive,
        relevance_reasoning character varying(2000) ENCODE lzo COLLATE case_sensitive,
        ticker character varying(10) ENCODE lzo COLLATE case_sensitive,
        PRIMARY KEY (theme_id, client_id)
) DISTSTYLE KEY
SORTKEY
    (client_id, created_at, rank);

CREATE TABLE public.transactions (
    transaction_id character varying(14) NOT NULL ENCODE lzo COLLATE case_sensitive,
    account_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive
    distkey
,
        security_id character varying(10) ENCODE lzo COLLATE case_sensitive,
        transaction_type character varying(20) NOT NULL ENCODE lzo COLLATE case_sensitive,
        transaction_date date NOT NULL ENCODE raw,
        settlement_date date ENCODE az64,
        quantity numeric(14, 2) ENCODE az64,
        price numeric(12, 2) ENCODE az64,
        amount numeric(18, 2) ENCODE az64,
        status character varying(20) NOT NULL DEFAULT 'Pending':: character varying ENCODE lzo COLLATE case_sensitive,
        PRIMARY KEY (transaction_id)
) DISTSTYLE KEY
SORTKEY
    (transaction_date);

