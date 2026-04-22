-- View: advisor_dashboard_summary
SELECT a.advisor_id, (((a.first_name)::text || (' '::character varying)::text) || (a.last_name)::text) AS advisor_name, a.title AS advisor_title, db.latest_month_start AS latest_month, db.prev_month_start AS previous_month, COALESCE(al.total_aum_latest, ((0)::numeric)::numeric(18,0)) AS total_aum_latest_month, COALESCE(ap.total_aum_prev, ((0)::numeric)::numeric(18,0)) AS total_aum_previous_month, (COALESCE(al.total_aum_latest, ((0)::numeric)::numeric(18,0)) - COALESCE(ap.total_aum_prev, ((0)::numeric)::numeric(18,0))) AS aum_change, CASE WHEN (COALESCE(ap.total_aum_prev, ((0)::numeric)::numeric(18,0)) > ((0)::numeric)::numeric(18,0)) THEN round((((COALESCE(al.total_aum_latest, ((0)::numeric)::numeric(18,0)) - ap.total_aum_prev) / ap.total_aum_prev) * ((100)::numeric)::numeric(18,0)), 2) ELSE (NULL::numeric)::numeric(18,0) END AS aum_change_pct, round(COALESCE(ar.avg_return_pct, ((0)::numeric)::numeric(18,0)), 4) AS avg_portfolio_return_pct, round(COALESCE(ar.avg_return_value, ((0)::numeric)::numeric(18,0)), 2) AS avg_portfolio_return_value, COALESCE(acl.active_clients_latest, (0)::bigint) AS active_clients_latest_month, COALESCE(acp.active_clients_prev, (0)::bigint) AS active_clients_previous_month, (COALESCE(acl.active_clients_latest, (0)::bigint) - COALESCE(acp.active_clients_prev, (0)::bigint)) AS active_clients_change, round(COALESCE(fl.total_fees_latest, ((0)::numeric)::numeric(18,0)), 2) AS total_fees_latest_month, round(COALESCE(fp.total_fees_prev, ((0)::numeric)::numeric(18,0)), 2) AS total_fees_previous_month, round((COALESCE(fl.total_fees_latest, ((0)::numeric)::numeric(18,0)) - COALESCE(fp.total_fees_prev, ((0)::numeric)::numeric(18,0))), 2) AS fees_change FROM ((((((((advisors a CROSS JOIN (SELECT date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS latest_month_start, date_add(('month'::character varying)::text, (1)::bigint, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS latest_month_end, date_add(('month'::character varying)::text, (- (1)::bigint), date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS prev_month_start, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS prev_month_end FROM performance) db) LEFT JOIN (SELECT c.advisor_id, sum(perf.ending_value) AS total_aum_latest FROM ((((performance perf JOIN portfolios p ON (((perf.portfolio_id)::text = (p.portfolio_id)::text))) JOIN accounts acc ON (((p.account_id)::text = (acc.account_id)::text))) JOIN clients c ON (((acc.client_id)::text = (c.client_id)::text))) CROSS JOIN (SELECT date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS latest_month_start, date_add(('month'::character varying)::text, (1)::bigint, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS latest_month_end, date_add(('month'::character varying)::text, (- (1)::bigint), date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS prev_month_start, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS prev_month_end FROM performance) db) WHERE ((perf.period_end_date >= db.latest_month_start) AND (perf.period_end_date < db.latest_month_end)) GROUP BY c.advisor_id) al ON (((a.advisor_id)::text = (al.advisor_id)::text))) LEFT JOIN (SELECT c.advisor_id, sum(perf.ending_value) AS total_aum_prev FROM ((((performance perf JOIN portfolios p ON (((perf.portfolio_id)::text = (p.portfolio_id)::text))) JOIN accounts acc ON (((p.account_id)::text = (acc.account_id)::text))) JOIN clients c ON (((acc.client_id)::text = (c.client_id)::text))) CROSS JOIN (SELECT date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS latest_month_start, date_add(('month'::character varying)::text, (1)::bigint, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS latest_month_end, date_add(('month'::character varying)::text, (- (1)::bigint), date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS prev_month_start, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS prev_month_end FROM performance) db) WHERE ((perf.period_end_date >= db.prev_month_start) AND (perf.period_end_date < db.prev_month_end)) GROUP BY c.advisor_id) ap ON (((a.advisor_id)::text = (ap.advisor_id)::text))) LEFT JOIN (SELECT c.advisor_id, avg(lp.time_weighted_return) AS avg_return_pct, avg((lp.ending_value - lp.beginning_value)) AS avg_return_value FROM ((((SELECT perf.portfolio_id, perf.time_weighted_return, perf.beginning_value, perf.ending_value, pg_catalog.row_number() OVER(  PARTITION BY perf.portfolio_id ORDER BY perf.period_end_date DESC) AS rn FROM performance perf) lp JOIN portfolios p ON (((lp.portfolio_id)::text = (p.portfolio_id)::text))) JOIN accounts acc ON (((p.account_id)::text = (acc.account_id)::text))) JOIN clients c ON (((acc.client_id)::text = (c.client_id)::text))) WHERE (lp.rn = 1) GROUP BY c.advisor_id) ar ON (((a.advisor_id)::text = (ar.advisor_id)::text))) LEFT JOIN (SELECT c.advisor_id, count(DISTINCT c.client_id) AS active_clients_latest FROM (((transactions t JOIN accounts acc ON (((t.account_id)::text = (acc.account_id)::text))) JOIN clients c ON (((acc.client_id)::text = (c.client_id)::text))) CROSS JOIN (SELECT date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS latest_month_start, date_add(('month'::character varying)::text, (1)::bigint, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS latest_month_end, date_add(('month'::character varying)::text, (- (1)::bigint), date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS prev_month_start, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS prev_month_end FROM performance) db) WHERE (((t.transaction_date >= db.latest_month_start) AND (t.transaction_date < db.latest_month_end)) AND ((c.status)::text = ('Active'::character varying)::text)) GROUP BY c.advisor_id) acl ON (((a.advisor_id)::text = (acl.advisor_id)::text))) LEFT JOIN (SELECT c.advisor_id, count(DISTINCT c.client_id) AS active_clients_prev FROM (((transactions t JOIN accounts acc ON (((t.account_id)::text = (acc.account_id)::text))) JOIN clients c ON (((acc.client_id)::text = (c.client_id)::text))) CROSS JOIN (SELECT date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS latest_month_start, date_add(('month'::character varying)::text, (1)::bigint, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS latest_month_end, date_add(('month'::character varying)::text, (- (1)::bigint), date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS prev_month_start, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS prev_month_end FROM performance) db) WHERE (((t.transaction_date >= db.prev_month_start) AND (t.transaction_date < db.prev_month_end)) AND ((c.status)::text = ('Active'::character varying)::text)) GROUP BY c.advisor_id) acp ON (((a.advisor_id)::text = (acp.advisor_id)::text))) LEFT JOIN (SELECT c.advisor_id, sum(f.fee_amount) AS total_fees_latest FROM (((fees f JOIN accounts acc ON (((f.account_id)::text = (acc.account_id)::text))) JOIN clients c ON (((acc.client_id)::text = (c.client_id)::text))) CROSS JOIN (SELECT date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS latest_month_start, date_add(('month'::character varying)::text, (1)::bigint, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS latest_month_end, date_add(('month'::character varying)::text, (- (1)::bigint), date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS prev_month_start, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS prev_month_end FROM performance) db) WHERE ((f.billing_date >= db.latest_month_start) AND (f.billing_date < db.latest_month_end)) GROUP BY c.advisor_id) fl ON (((a.advisor_id)::text = (fl.advisor_id)::text))) LEFT JOIN (SELECT c.advisor_id, sum(f.fee_amount) AS total_fees_prev FROM (((fees f JOIN accounts acc ON (((f.account_id)::text = (acc.account_id)::text))) JOIN clients c ON (((acc.client_id)::text = (c.client_id)::text))) CROSS JOIN (SELECT date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS latest_month_start, date_add(('month'::character varying)::text, (1)::bigint, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS latest_month_end, date_add(('month'::character varying)::text, (- (1)::bigint), date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone)) AS prev_month_start, date_trunc(('month'::character varying)::text, ("max"(performance.period_end_date))::timestamp without time zone) AS prev_month_end FROM performance) db) WHERE ((f.billing_date >= db.prev_month_start) AND (f.billing_date < db.prev_month_end)) GROUP BY c.advisor_id) fp ON (((a.advisor_id)::text = (fp.advisor_id)::text)));

-- View: advisor_master
CREATE MATERIALIZED VIEW public.advisor_master AS
SELECT
    a.advisor_id,
    a.first_name        AS advisor_first_name,
    a.last_name         AS advisor_last_name,
    a.email             AS advisor_email,
    a.phone             AS advisor_phone,
    a.title             AS advisor_title,
    a."credentials"     AS advisor_credentials,
    a.specialization    AS advisor_specialization,
    a.years_experience  AS advisor_years_experience,
    a.hire_date         AS advisor_hire_date,
    c.client_id,
    c.first_name        AS client_first_name,
    c.last_name         AS client_last_name,
    c.email             AS client_email,
    c.phone             AS client_phone,
    c.address           AS client_address,
    c.city              AS client_city,
    c.state             AS client_state,
    c.zip               AS client_zip,
    c.date_of_birth     AS client_dob,
    c.risk_tolerance,
    c.investment_objectives,
    c.segment           AS client_segment,
    c.status            AS client_status,
    c.created_date      AS client_created_date,
    c.service_model,
    c.sophistication,
    c.qualified_investor,
    acc.account_id,
    acc.account_type,
    acc.account_name,
    acc.opening_date    AS account_opening_date,
    acc.investment_strategy,
    acc.status          AS account_status,
    acc.current_balance AS account_current_balance,
    p.portfolio_id,
    p.portfolio_name,
    p.investment_model,
    p.target_allocation,
    p.benchmark,
    p.inception_date    AS portfolio_inception_date,
    perf.performance_id,
    perf.period         AS performance_period,
    perf.period_start_date AS performance_start_date,
    perf.period_end_date   AS performance_end_date,
    perf.time_weighted_return,
    perf.benchmark_return,
    perf.beginning_value AS performance_beginning_value,
    perf.ending_value    AS performance_ending_value,
    f.fee_id,
    f.fee_type,
    f.fee_rate,
    f.billing_date      AS fee_billing_date,
    f.fee_amount,
    f.payment_status    AS fee_payment_status,
    f.payment_date      AS fee_payment_date,
    i.interaction_id,
    i.interaction_type,
    i.interaction_date,
    i.subject           AS interaction_subject,
    i.summary           AS interaction_summary,
    i.sentiment         AS interaction_sentiment,
    i.duration_minutes  AS interaction_duration,
    comp.compliance_id,
    comp.kyc_status,
    comp.kyc_date,
    comp.aml_status,
    comp.aml_date,
    comp.suitability_status,
    comp.suitability_date,
    comp.next_review_date AS compliance_next_review_date,
    doc_count.total_documents,
    doc_count.latest_document_date,
    goal_summary.total_goals,
    goal_summary.total_target_amount,
    goal_summary.total_current_value,
    goal_summary.goals_on_track,
    goal_summary.goals_behind,
    COALESCE(rst.restriction_count, 0) AS restriction_count
FROM advisors a
LEFT JOIN clients c
    ON a.advisor_id = c.advisor_id
LEFT JOIN accounts acc
    ON c.client_id = acc.client_id
LEFT JOIN portfolios p
    ON acc.account_id = p.account_id
LEFT JOIN (
    SELECT portfolio_id, performance_id, period, period_start_date, period_end_date,
           time_weighted_return, benchmark_return, beginning_value, ending_value,
           ROW_NUMBER() OVER (PARTITION BY portfolio_id ORDER BY period_end_date DESC) AS rn
    FROM performance
) perf ON p.portfolio_id = perf.portfolio_id AND perf.rn = 1
LEFT JOIN (
    SELECT account_id, fee_id, fee_type, fee_rate, billing_date, fee_amount,
           payment_status, payment_date,
           ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY billing_date DESC) AS rn
    FROM fees
) f ON acc.account_id = f.account_id AND f.rn = 1
LEFT JOIN (
    SELECT client_id, interaction_id, interaction_type, interaction_date, subject,
           summary, sentiment, duration_minutes,
           ROW_NUMBER() OVER (PARTITION BY client_id ORDER BY interaction_date DESC) AS rn
    FROM interactions
) i ON c.client_id = i.client_id AND i.rn = 1
LEFT JOIN compliance comp
    ON c.client_id = comp.client_id
LEFT JOIN (
    SELECT client_id, COUNT(*) AS total_documents, MAX(upload_date) AS latest_document_date
    FROM documents
    GROUP BY client_id
) doc_count ON c.client_id = doc_count.client_id
LEFT JOIN (
    SELECT client_id, COUNT(*) AS total_goals,
           SUM(target_amount) AS total_target_amount,
           SUM(current_value) AS total_current_value,
           SUM(CASE WHEN funding_status = 'On Track' THEN 1 ELSE 0 END) AS goals_on_track,
           SUM(CASE WHEN funding_status = 'Behind' THEN 1 ELSE 0 END) AS goals_behind
    FROM goals
    GROUP BY client_id
) goal_summary ON c.client_id = goal_summary.client_id
LEFT JOIN (
    SELECT client_id, COUNT(*) AS restriction_count
    FROM client_investment_restrictions
    GROUP BY client_id
) rst ON c.client_id = rst.client_id
WHERE c.status = 'Active';

-- View: advisor_monthly_aum
SELECT a.advisor_id, (((a.first_name)::text || ' '::text) || (a.last_name)::text) AS advisor_name, mp.report_month, count(DISTINCT c.client_id) AS client_count, count(DISTINCT acc.account_id) AS account_count, count(DISTINCT mp.portfolio_id) AS portfolio_count, sum(mp.ending_value) AS total_aum, sum(mp.beginning_value) AS total_beginning_value, (sum(mp.ending_value) - sum(mp.beginning_value)) AS total_value_change, avg(mp.time_weighted_return) AS avg_portfolio_return_pct FROM (((((SELECT perf.portfolio_id, date_trunc('month'::text, (perf.period_end_date)::timestamp without time zone) AS report_month, perf.ending_value, perf.beginning_value, perf.time_weighted_return, pg_catalog.row_number() OVER(  PARTITION BY perf.portfolio_id, date_trunc('month'::text, (perf.period_end_date)::timestamp without time zone) ORDER BY perf.period_end_date DESC) AS rn FROM performance perf) mp JOIN portfolios p ON (((mp.portfolio_id)::text = (p.portfolio_id)::text))) JOIN accounts acc ON (((p.account_id)::text = (acc.account_id)::text))) JOIN clients c ON (((acc.client_id)::text = (c.client_id)::text))) JOIN advisors a ON (((c.advisor_id)::text = (a.advisor_id)::text))) WHERE (mp.rn = 1) GROUP BY a.advisor_id, a.first_name, a.last_name, mp.report_month;

-- View: client_account_transactions
SELECT a.client_id, t.transaction_id, t.account_id, t.security_id, t.transaction_type, t.transaction_date, t.settlement_date, t.quantity, t.price, t.amount, t.status FROM (transactions t JOIN accounts a ON (((t.account_id)::text = (a.account_id)::text)));

-- View: client_accounts
SELECT accounts.account_id, accounts.client_id, accounts.account_type, accounts.account_name, accounts.opening_date, accounts.investment_strategy, accounts.status, accounts.current_balance FROM accounts;

-- View: client_income_expenses
SELECT client_income_expense.client_id, client_income_expense.as_of_date, client_income_expense.monthly_income, client_income_expense.monthly_expenses, client_income_expense.sustainability_years FROM client_income_expense;

-- View: client_interactions
SELECT interactions.interaction_id, interactions.client_id, interactions.advisor_id, interactions.interaction_type, interactions.interaction_date, interactions.subject, interactions.summary, interactions.sentiment, interactions.duration_minutes FROM interactions;

-- View: client_list
SELECT c.client_id, c.advisor_id, (((adv.first_name)::text || (' '::character varying)::text) || (adv.last_name)::text) AS advisor_name, c.last_name AS client_last_name, c.first_name AS client_first_name, COALESCE(ca.total_aum, ((0)::numeric)::numeric(18,0)) AS aum, COALESCE(cnw.net_worth, ((0)::numeric)::numeric(18,0)) AS net_worth, cy.ytd_return_pct AS ytd_performance, c.risk_tolerance, c.created_date AS client_since, li.sentiment AS interaction_sentiment, lr.report_id, lr.s3_path, lr.generated_date, lr.next_best_action FROM ((((((clients c JOIN advisors adv ON (((c.advisor_id)::text = (adv.advisor_id)::text))) LEFT JOIN (SELECT latest_performance.client_id, sum(latest_performance.ending_value) AS total_aum FROM (SELECT p.portfolio_id, p.ending_value, p.beginning_value, p.time_weighted_return, p.period_start_date, a.client_id, pg_catalog.row_number() OVER(  PARTITION BY p.portfolio_id ORDER BY p.period_end_date DESC) AS rn FROM ((performance p JOIN portfolios pf ON (((p.portfolio_id)::text = (pf.portfolio_id)::text))) JOIN accounts a ON (((pf.account_id)::text = (a.account_id)::text)))) latest_performance WHERE (latest_performance.rn = 1) GROUP BY latest_performance.client_id) ca ON (((c.client_id)::text = (ca.client_id)::text))) LEFT JOIN (SELECT accounts.client_id, sum(accounts.current_balance) AS net_worth FROM accounts WHERE ((accounts.status)::text = ('Active'::character varying)::text) GROUP BY accounts.client_id) cnw ON (((c.client_id)::text = (cnw.client_id)::text))) LEFT JOIN (SELECT ytd_performance.client_id, (sum((ytd_performance.time_weighted_return * ytd_performance.ending_value)) / CASE WHEN (sum(ytd_performance.ending_value) = ((0)::numeric)::numeric(18,0)) THEN (NULL::numeric)::numeric(18,0) ELSE sum(ytd_performance.ending_value) END) AS ytd_return_pct FROM (SELECT p.portfolio_id, p.time_weighted_return, p.ending_value, a.client_id, pg_catalog.row_number() OVER(  PARTITION BY p.portfolio_id ORDER BY p.period_end_date DESC) AS rn FROM ((performance p JOIN portfolios pf ON (((p.portfolio_id)::text = (pf.portfolio_id)::text))) JOIN accounts a ON (((pf.account_id)::text = (a.account_id)::text))) WHERE (p.period_start_date >= date_trunc(('year'::character varying)::text, (('now'::character varying)::date)::timestamp without time zone))) ytd_performance WHERE (ytd_performance.rn = 1) GROUP BY ytd_performance.client_id) cy ON (((c.client_id)::text = (cy.client_id)::text))) LEFT JOIN (SELECT interactions.client_id, interactions.sentiment, pg_catalog.row_number() OVER(  PARTITION BY interactions.client_id ORDER BY interactions.interaction_date DESC) AS rn FROM interactions) li ON ((((c.client_id)::text = (li.client_id)::text) AND (li.rn = 1)))) LEFT JOIN (SELECT client_reports.client_id, client_reports.report_id, client_reports.s3_path, client_reports.generated_date, client_reports.next_best_action, pg_catalog.row_number() OVER(  PARTITION BY client_reports.client_id ORDER BY client_reports.generated_date DESC) AS rn FROM client_reports) lr ON ((((c.client_id)::text = (lr.client_id)::text) AND (lr.rn = 1)))) WHERE ((c.status)::text = ('Active'::character varying)::text);

-- View: client_portfolio_holdings
SELECT a.client_id, p.portfolio_id, p.account_id, p.portfolio_name, p.investment_model, p.target_allocation, p.benchmark, p.inception_date, h.position_id, h.security_id, h.quantity, h.cost_basis, h.current_price, h.market_value, h.unrealized_gain_loss, h.as_of_date, s.ticker, s.security_name, s.asset_class, s.sector FROM (((holdings h JOIN securities s ON (((h.security_id)::text = (s.security_id)::text))) JOIN portfolios p ON (((h.portfolio_id)::text = (p.portfolio_id)::text))) JOIN accounts a ON (((p.account_id)::text = (a.account_id)::text)));

-- View: client_portfolio_performance
SELECT a.client_id, pf.performance_id, pf.portfolio_id, pf.period, pf.period_start_date, pf.period_end_date, pf.time_weighted_return, pf.benchmark_return, pf.beginning_value, pf.ending_value FROM ((performance pf JOIN portfolios p ON (((pf.portfolio_id)::text = (p.portfolio_id)::text))) JOIN accounts a ON (((p.account_id)::text = (a.account_id)::text)));

-- View: client_restrictions
SELECT client_investment_restrictions.restriction_id, client_investment_restrictions.client_id, client_investment_restrictions.restriction, client_investment_restrictions.created_date FROM client_investment_restrictions;

-- View: client_search
SELECT c.client_id, c.first_name AS client_first_name, c.last_name AS client_last_name, (((c.first_name)::text || (' '::character varying)::text) || (c.last_name)::text) AS client_name, c.email, c.phone, c.address, c.city, c.state, c.zip, c.date_of_birth, c.risk_tolerance, c.investment_objectives, c.segment, c.status, c.created_date AS client_since, c.sophistication, c.qualified_investor, c.service_model, c.advisor_id, (((adv.first_name)::text || (' '::character varying)::text) || (adv.last_name)::text) AS advisor_name, COALESCE(ca.total_aum, ((0)::numeric)::numeric(18,0)) AS aum, COALESCE(cnw.net_worth, ((0)::numeric)::numeric(18,0)) AS net_worth, cy.ytd_return_pct AS ytd_performance, li.sentiment AS interaction_sentiment, lr.report_id, lr.s3_path, lr.generated_date, lr.next_best_action, lie.income_expense_as_of_date, lie.monthly_income, lie.monthly_expenses, (lie.monthly_income - lie.monthly_expenses) AS monthly_net, lie.sustainability_years, comp.compliance_id, comp.kyc_status, comp.kyc_date, comp.aml_status, comp.aml_date, comp.suitability_status, comp.suitability_date, comp.next_review_date, COALESCE(cr.restriction_count, (0)::bigint) AS restriction_count, cr.restrictions_list, COALESCE(gs.total_goals, (0)::bigint) AS total_goals, COALESCE(gs.total_target_amount, ((0)::numeric)::numeric(18,0)) AS goals_total_target_amount, COALESCE(gs.total_current_value, ((0)::numeric)::numeric(18,0)) AS goals_total_current_value, COALESCE(gs.goals_on_track, (0)::bigint) AS goals_on_track, COALESCE(gs.goals_behind, (0)::bigint) AS goals_behind, COALESCE(th.theme_count, (0)::bigint) AS theme_count, pc.tickers AS recommended_tickers, pc.generated_at AS portfolio_config_generated_at FROM ((((((((((((clients c JOIN advisors adv ON (((c.advisor_id)::text = (adv.advisor_id)::text))) LEFT JOIN (SELECT lp.client_id, sum(lp.ending_value) AS total_aum FROM (SELECT p.portfolio_id, p.ending_value, p.beginning_value, p.time_weighted_return, p.period_start_date, a.client_id, pg_catalog.row_number() OVER(  PARTITION BY p.portfolio_id ORDER BY p.period_end_date DESC) AS rn FROM ((performance p JOIN portfolios pf ON (((p.portfolio_id)::text = (pf.portfolio_id)::text))) JOIN accounts a ON (((pf.account_id)::text = (a.account_id)::text)))) lp WHERE (lp.rn = 1) GROUP BY lp.client_id) ca ON (((c.client_id)::text = (ca.client_id)::text))) LEFT JOIN (SELECT accounts.client_id, sum(accounts.current_balance) AS net_worth FROM accounts WHERE ((accounts.status)::text = ('Active'::character varying)::text) GROUP BY accounts.client_id) cnw ON (((c.client_id)::text = (cnw.client_id)::text))) LEFT JOIN (SELECT yp.client_id, (sum((yp.time_weighted_return * yp.ending_value)) / CASE WHEN (sum(yp.ending_value) = ((0)::numeric)::numeric(18,0)) THEN (NULL::numeric)::numeric(18,0) ELSE sum(yp.ending_value) END) AS ytd_return_pct FROM (SELECT p.portfolio_id, p.time_weighted_return, p.ending_value, a.client_id, pg_catalog.row_number() OVER(  PARTITION BY p.portfolio_id ORDER BY p.period_end_date DESC) AS rn FROM ((performance p JOIN portfolios pf ON (((p.portfolio_id)::text = (pf.portfolio_id)::text))) JOIN accounts a ON (((pf.account_id)::text = (a.account_id)::text))) WHERE (p.period_start_date >= date_trunc(('year'::character varying)::text, (('now'::character varying)::date)::timestamp without time zone))) yp WHERE (yp.rn = 1) GROUP BY yp.client_id) cy ON (((c.client_id)::text = (cy.client_id)::text))) LEFT JOIN (SELECT interactions.client_id, interactions.sentiment, pg_catalog.row_number() OVER(  PARTITION BY interactions.client_id ORDER BY interactions.interaction_date DESC) AS rn FROM interactions) li ON ((((c.client_id)::text = (li.client_id)::text) AND (li.rn = 1)))) LEFT JOIN (SELECT client_reports.client_id, client_reports.report_id, client_reports.s3_path, client_reports.generated_date, client_reports.next_best_action, pg_catalog.row_number() OVER(  PARTITION BY client_reports.client_id ORDER BY client_reports.generated_date DESC) AS rn FROM client_reports) lr ON ((((c.client_id)::text = (lr.client_id)::text) AND (lr.rn = 1)))) LEFT JOIN (SELECT cie.client_id, cie.as_of_date AS income_expense_as_of_date, cie.monthly_income, cie.monthly_expenses, cie.sustainability_years, pg_catalog.row_number() OVER(  PARTITION BY cie.client_id ORDER BY cie.as_of_date DESC) AS rn FROM client_income_expense cie) lie ON ((((c.client_id)::text = (lie.client_id)::text) AND (lie.rn = 1)))) LEFT JOIN compliance comp ON (((c.client_id)::text = (comp.client_id)::text))) LEFT JOIN (SELECT cir.client_id, count(*) AS restriction_count, pg_catalog.listagg((cir.restriction)::text, ('; '::character varying)::text) WITHIN GROUP( ORDER BY cir.created_date) AS restrictions_list FROM client_investment_restrictions cir GROUP BY cir.client_id) cr ON (((c.client_id)::text = (cr.client_id)::text))) LEFT JOIN (SELECT g.client_id, count(*) AS total_goals, sum(g.target_amount) AS total_target_amount, sum(g.current_value) AS total_current_value, sum(CASE WHEN ((g.funding_status)::text = ('On Track'::character varying)::text) THEN 1 ELSE 0 END) AS goals_on_track, sum(CASE WHEN ((g.funding_status)::text = ('Behind'::character varying)::text) THEN 1 ELSE 0 END) AS goals_behind FROM goals g GROUP BY g.client_id) gs ON (((c.client_id)::text = (gs.client_id)::text))) LEFT JOIN (SELECT t.client_id, count(*) AS theme_count FROM themes t GROUP BY t.client_id) th ON (((c.client_id)::text = (th.client_id)::text))) LEFT JOIN portfolio_config pc ON (((c.client_id)::text = (pc.client_id)::text))) WHERE ((c.status)::text = ('Active'::character varying)::text);

-- View: investor_monthly_aum
SELECT c.client_id, (((c.first_name)::text || ' '::text) || (c.last_name)::text) AS client_name, c.segment AS client_segment, c.risk_tolerance, c.advisor_id, (((a.first_name)::text || ' '::text) || (a.last_name)::text) AS advisor_name, mp.report_month, count(DISTINCT acc.account_id) AS account_count, count(DISTINCT mp.portfolio_id) AS portfolio_count, sum(mp.ending_value) AS total_aum, sum(mp.beginning_value) AS total_beginning_value, (sum(mp.ending_value) - sum(mp.beginning_value)) AS total_value_change, avg(mp.time_weighted_return) AS avg_portfolio_return_pct FROM (((((SELECT perf.portfolio_id, date_trunc('month'::text, (perf.period_end_date)::timestamp without time zone) AS report_month, perf.ending_value, perf.beginning_value, perf.time_weighted_return, pg_catalog.row_number() OVER(  PARTITION BY perf.portfolio_id, date_trunc('month'::text, (perf.period_end_date)::timestamp without time zone) ORDER BY perf.period_end_date DESC) AS rn FROM performance perf) mp JOIN portfolios p ON (((mp.portfolio_id)::text = (p.portfolio_id)::text))) JOIN accounts acc ON (((p.account_id)::text = (acc.account_id)::text))) JOIN clients c ON (((acc.client_id)::text = (c.client_id)::text))) JOIN advisors a ON (((c.advisor_id)::text = (a.advisor_id)::text))) WHERE (mp.rn = 1) GROUP BY c.client_id, c.first_name, c.last_name, c.segment, c.risk_tolerance, c.advisor_id, a.first_name, a.last_name, mp.report_month;

-- View: latest_themes
SELECT t.theme_id, t.client_id, t.title, t.sentiment, t.article_count, t.sources, t.created_at, t.summary, t.updated_at, t.score, t.rank, t.score_breakdown, t.generated_at, t.relevance_score, t.combined_score, t.matched_tickers, t.relevance_reasoning, t.ticker FROM themes t WHERE (t.generated_at >= (SELECT ("max"(t2.generated_at) - '00:05:00'::interval) FROM themes t2 WHERE ((t2.client_id)::text = (t.client_id)::text)));

-- View: product_catalog
SELECT recommended_products.product_id, recommended_products.product_name, recommended_products.product_type, recommended_products.description, recommended_products.status, recommended_products.created_date FROM recommended_products;

-- View: theme_articles
SELECT taa.theme_id, taa.client_id, a.content_hash, a.title, a.url, a.source, a.published_date FROM (theme_article_associations taa JOIN articles a ON (((taa.article_hash)::text = (a.content_hash)::text)));

-- Grant SELECT on all public views/tables to PUBLIC so any IAM-authenticated
-- Data API user can query them (workgroup is already secured by IAM policy).
GRANT USAGE ON SCHEMA public TO PUBLIC;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO PUBLIC;