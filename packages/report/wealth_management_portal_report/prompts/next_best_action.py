# Next Best Action prompt — generates a single advisor recommendation sentence
NEXT_BEST_ACTION_PROMPT = """
You are a wealth management advisor assistant.
Based on the client data below, identify the single most impactful action
the advisor should take right now.

## Client Profile
{profile_json}

## Portfolio Data
{portfolio_json}

## Communications History
{communications_json}

## Instructions
Respond with ONE sentence only (maximum 150 characters).
No preamble, no explanation, no punctuation at the end beyond a period.

Examples of good responses:
- Schedule a rebalancing call to address the 8% drift from target allocation in tech holdings.
- Follow up on the estate planning referral discussed in the March meeting.
- Review suitability before the upcoming CD maturity on April 15th.
- Send Q1 performance summary highlighting the 12% YTD gain versus benchmark.
"""
