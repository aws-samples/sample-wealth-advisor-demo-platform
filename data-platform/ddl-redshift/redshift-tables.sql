CREATE TABLE IF NOT EXISTS public.articles (
    content_hash character varying(64) NOT NULL ENCODE lzo COLLATE case_sensitive distkey,
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
)
DISTSTYLE KEY
SORTKEY ( published_date, source );

CREATE TABLE IF NOT EXISTS public.client_reports (
    report_id character varying(14) NOT NULL ENCODE lzo COLLATE case_sensitive,
    client_id character varying(10) NOT NULL ENCODE lzo COLLATE case_sensitive,
    generated_date timestamp without time zone NOT NULL DEFAULT ('now'::text)::timestamp with time zone ENCODE az64,
    download_date timestamp without time zone ENCODE az64,
    status character varying(20) NOT NULL DEFAULT 'init'::character varying ENCODE lzo COLLATE case_sensitive,
    s3_path character varying(500) ENCODE lzo COLLATE case_sensitive,
    next_best_action character varying(1000) ENCODE lzo COLLATE case_sensitive,
    PRIMARY KEY (report_id)
)
DISTSTYLE AUTO;

CREATE TABLE IF NOT EXISTS public.theme_article_associations (
    theme_id character varying(100) NOT NULL ENCODE raw COLLATE case_sensitive,
    article_hash character varying(64) NOT NULL ENCODE raw COLLATE case_sensitive,
    client_id character varying(100) NOT NULL DEFAULT '__GENERAL__'::character varying ENCODE raw COLLATE case_sensitive distkey,
    created_at timestamp without time zone DEFAULT getdate() ENCODE az64,
    PRIMARY KEY (theme_id, article_hash, client_id)
)
DISTSTYLE KEY
SORTKEY ( client_id, theme_id, article_hash );

CREATE TABLE IF NOT EXISTS public.themes (
    theme_id character varying(100) NOT NULL ENCODE lzo COLLATE case_sensitive,
    client_id character varying(100) NOT NULL DEFAULT '__GENERAL__'::character varying ENCODE raw COLLATE case_sensitive distkey,
    title character varying(500) NOT NULL ENCODE lzo COLLATE case_sensitive,
    sentiment character varying(20) ENCODE lzo COLLATE case_sensitive,
    article_count integer ENCODE az64,
    sources character varying(5000) ENCODE lzo COLLATE case_sensitive,
    created_at timestamp without time zone ENCODE raw,
    summary character varying(10000) ENCODE lzo COLLATE case_sensitive,
    updated_at timestamp without time zone ENCODE az64,
    score numeric(10,2) ENCODE az64,
    rank integer ENCODE raw,
    score_breakdown character varying(1000) ENCODE lzo COLLATE case_sensitive,
    generated_at timestamp without time zone ENCODE az64,
    relevance_score numeric(10,2) ENCODE az64,
    combined_score numeric(10,2) ENCODE az64,
    matched_tickers character varying(500) ENCODE lzo COLLATE case_sensitive,
    relevance_reasoning character varying(2000) ENCODE lzo COLLATE case_sensitive,
    ticker character varying(10) ENCODE lzo COLLATE case_sensitive,
    PRIMARY KEY (theme_id, client_id)
)
DISTSTYLE KEY
SORTKEY ( client_id, created_at, rank );
