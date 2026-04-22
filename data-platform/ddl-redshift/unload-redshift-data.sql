-- UNLOAD all tables from Redshift to S3
-- Bucket: s3://unload-rs-s3-anup/
-- IAM Role: arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721
-- Format: CSV with header

-- 1. accounts
UNLOAD ('SELECT * FROM public.accounts')
TO 's3://unload-rs-s3-anup/accounts.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 2. advisors
UNLOAD ('SELECT * FROM public.advisors')
TO 's3://unload-rs-s3-anup/advisors.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 3. articles
UNLOAD ('SELECT * FROM public.articles')
TO 's3://unload-rs-s3-anup/articles.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 4. client_income_expense
UNLOAD ('SELECT * FROM public.client_income_expense')
TO 's3://unload-rs-s3-anup/client_income_expense.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 5. client_investment_restrictions
UNLOAD ('SELECT * FROM public.client_investment_restrictions')
TO 's3://unload-rs-s3-anup/client_investment_restrictions.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 6. client_reports
UNLOAD ('SELECT * FROM public.client_reports')
TO 's3://unload-rs-s3-anup/client_reports.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 7. clients
UNLOAD ('SELECT * FROM public.clients')
TO 's3://unload-rs-s3-anup/clients.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 8. compliance
UNLOAD ('SELECT * FROM public.compliance')
TO 's3://unload-rs-s3-anup/compliance.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 9. crawl_log
UNLOAD ('SELECT * FROM public.crawl_log')
TO 's3://unload-rs-s3-anup/crawl_log.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 10. documents
UNLOAD ('SELECT * FROM public.documents')
TO 's3://unload-rs-s3-anup/documents.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 11. fees
UNLOAD ('SELECT * FROM public.fees')
TO 's3://unload-rs-s3-anup/fees.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 12. goals
UNLOAD ('SELECT * FROM public.goals')
TO 's3://unload-rs-s3-anup/goals.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 13. holdings
UNLOAD ('SELECT * FROM public.holdings')
TO 's3://unload-rs-s3-anup/holdings.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 14. interactions
UNLOAD ('SELECT * FROM public.interactions')
TO 's3://unload-rs-s3-anup/interactions.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 15. market_data
UNLOAD ('SELECT * FROM public.market_data')
TO 's3://unload-rs-s3-anup/market_data.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 16. performance
UNLOAD ('SELECT * FROM public.performance')
TO 's3://unload-rs-s3-anup/performance.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 17. portfolio_config
UNLOAD ('SELECT * FROM public.portfolio_config')
TO 's3://unload-rs-s3-anup/portfolio_config.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 18. portfolios
UNLOAD ('SELECT * FROM public.portfolios')
TO 's3://unload-rs-s3-anup/portfolios.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 19. recommended_products
UNLOAD ('SELECT * FROM public.recommended_products')
TO 's3://unload-rs-s3-anup/recommended_products.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 20. research
UNLOAD ('SELECT * FROM public.research')
TO 's3://unload-rs-s3-anup/research.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 21. securities
UNLOAD ('SELECT * FROM public.securities')
TO 's3://unload-rs-s3-anup/securities.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 22. theme_article_associations
UNLOAD ('SELECT * FROM public.theme_article_associations')
TO 's3://unload-rs-s3-anup/theme_article_associations.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 23. themes
UNLOAD ('SELECT * FROM public.themes')
TO 's3://unload-rs-s3-anup/themes.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;

-- 24. transactions
UNLOAD ('SELECT * FROM public.transactions')
TO 's3://unload-rs-s3-anup/transactions.csv'
IAM_ROLE 'arn:aws:iam::507139572291:role/service-role/AmazonRedshift-CommandsAccessRole-20260209T124721'
CSV HEADER
ALLOWOVERWRITE
PARALLEL OFF;
