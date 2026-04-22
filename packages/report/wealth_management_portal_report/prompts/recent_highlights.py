# Recent highlights prompt - short summary for client summary table
RECENT_HIGHLIGHTS_PROMPT = """
Generate a 1-2 sentence summary of recent account highlights for the client summary.

## Client Profile
{profile_json}

## Portfolio Data
{portfolio_json}

## Communications History
{communications_json}

## Your Task
Write 1-2 concise sentences covering the most important recent developments:
- Key portfolio changes or milestones
- Significant life events affecting planning
- Upcoming deadlines or decisions

## Guidelines
- Maximum 2 sentences
- Focus on what matters most for the upcoming meeting
- Factual and specific — reference actual data
- Output plain text (no markdown formatting)
"""
