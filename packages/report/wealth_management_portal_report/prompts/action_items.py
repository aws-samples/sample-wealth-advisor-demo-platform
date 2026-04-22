# Action items prompt - prioritizes tasks and generates insights
ACTION_ITEMS_PROMPT = """
Generate prioritized action items and key insights for the advisor.

## Client Profile
{profile_json}

## Portfolio Data
{portfolio_json}

## Communications History
{communications_json}

## Your Task
Generate an "Action Items" section with:

1. **Overdue & Pending Tasks**
   - List tasks from communications with status
   - Flag overdue items prominently

2. **Recommended Discussion Points**
   - Topics to raise based on portfolio and communications
   - Questions to ask the client
   - Decisions that need to be made

3. **"Tell Me Something I Don't Know"**
   - Non-obvious insights from connecting the data
   - Patterns or concerns the advisor might miss
   - Proactive suggestions based on client situation

## Guidelines
- Prioritize by urgency and impact
- Be specific - reference actual data points
- The "Tell Me Something" section should provide genuine insight
- Format with clear priority indicators
- Keep actionable and concise
"""
