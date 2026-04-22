# Relationship context prompt - synthesizes communication history
RELATIONSHIP_CONTEXT_PROMPT = """
Synthesize the relationship history into a concise narrative.

## Client Profile
{profile_json}

## Communications History
{communications_json}

## Your Task
Generate a "Relationship Context" section that includes:

1. **Key Milestones**
   - Major events in the client relationship
   - Significant financial decisions made together
   - Life events that impacted planning

2. **Recent Interactions**
   - Summary of last 2-3 meetings/communications
   - Key topics discussed
   - Any concerns or questions raised

3. **Personal Context**
   - Family situation relevant to planning
   - Lifestyle and interests (brief)
   - Health or life circumstances to be aware of

## Guidelines
- Write as a narrative, not bullet points
- Focus on what helps the advisor prepare for the meeting
- Keep personal details relevant to financial planning
- Chronological flow from past to present
- Professional but personable tone
- 2-3 paragraphs maximum
"""
