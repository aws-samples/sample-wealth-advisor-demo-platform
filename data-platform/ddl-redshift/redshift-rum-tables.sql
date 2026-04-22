CREATE TABLE IF NOT EXISTS public.rum_page_views (
    view_id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    page_url VARCHAR(500) NOT NULL,
    page_title VARCHAR(200),
    load_time_ms INTEGER,
    device_type VARCHAR(20),
    browser VARCHAR(50),
    country VARCHAR(50),
    city VARCHAR(100),
    user_agent VARCHAR(500),
    view_timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (view_id)
) DISTSTYLE AUTO SORTKEY (view_timestamp);

CREATE TABLE IF NOT EXISTS public.rum_errors (
    error_id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    error_type VARCHAR(50) NOT NULL,
    error_message VARCHAR(2000),
    page_url VARCHAR(500),
    http_status INTEGER,
    error_timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (error_id)
) DISTSTYLE AUTO SORTKEY (error_timestamp);

CREATE TABLE IF NOT EXISTS public.rum_performance (
    perf_id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    page_url VARCHAR(500) NOT NULL,
    ttfb_ms INTEGER,
    fcp_ms INTEGER,
    lcp_ms INTEGER,
    cls_score DECIMAL(5,3),
    fid_ms INTEGER,
    dom_load_ms INTEGER,
    perf_timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (perf_id)
) DISTSTYLE AUTO SORTKEY (perf_timestamp);
