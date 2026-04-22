# ruff: noqa: E501
# Client summary template
CLIENT_SUMMARY_TEMPLATE = """
## Client Summary

| | |
|---|---|
| **Client** | {{ names | join(', ') }} (Ages: {{ ages | join(', ') }}) |
| **Client Since** | {{ client_since }} ({{ tenure_years }} years) |
| **AUM** | {{ aum_formatted }} |
| **Risk Profile** | {{ risk_profile }} |
| **Service Model** | {{ service_model }} |
| **Activity Level** | {{ activity_level }} |
| **Sophistication** | {{ sophistication }} |
| **Domicile** | {{ domicile }} |
| **Tax Jurisdiction** | {{ tax_jurisdiction }} |
| **Recent Highlights** | {{ recent_highlights }} |
{%- if qualified_investor %}
| **Qualified Investor** | Yes |
{%- endif %}
{%- if restrictions %}
| **Restrictions** | {% for r in restrictions %}- {{ r }}<br>{% endfor %} |
{%- endif %}
{%- if document_links %}
| **Documents** | {% for doc in document_links %}[{{ doc.label }}]({{ doc.url }}){% if not loop.last %}<br>{% endif %}{% endfor %} |
{%- endif %}

### Associated Accounts
| Account Type | Value | Currency | Risk Profile | Inception Date |
|---------|-------|----------|--------------|----------------|
{%- for account in associated_accounts %}
| {{ account.account_type }} | {{ account.value_formatted }} | {{ account.currency }} | {{ account.risk_profile or 'N/A' }} | {{ account.inception_date_formatted or 'N/A' }} |
{%- endfor %}

### Last Interaction
{{ last_interaction_summary }}
"""
