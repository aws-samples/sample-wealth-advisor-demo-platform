# Last interaction prompt - synthesizes recent client communication
LAST_INTERACTION_PROMPT = """
Summarize the most recent client interaction and actions completed since then.

## Client Profile
{profile_json}

## Communications History
{communications_json}

## Your Task
Generate a brief summary (3-5 sentences) covering:

1. **What Was Discussed**
   - Key topics from the most recent meeting or communication
   - Concerns or questions the client raised

2. **Actions Completed Since Then**
   - Explicitly list each task marked "Completed" that was done after or as a result of the last interaction
   - Be specific: "We completed X", "We set up Y", "We processed Z"
   - If no actions were completed, state that clearly

3. **Outstanding Items**
   - Any pending or overdue tasks
   - Next steps that were agreed upon

## Guidelines
- Lead with the discussion summary, then enumerate completed actions
- Use concrete language: "completed", "processed", "configured", "set up"
- Reference specific amounts, dates, or details from the task data
- Professional, concise tone
- Output plain text (no markdown formatting)
- If no recent interactions exist, state: "No recent interactions recorded."
"""
