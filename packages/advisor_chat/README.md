# Advisor Chat — Multi-Agent A2A System

A multi-agent conversational AI system for financial advisors, built on [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) and the [Strands SDK](https://github.com/strands-agents/sdk-python). A routing agent classifies user intent and delegates to specialist agents via the A2A protocol (JSON-RPC 2.0).

[Get full details for scheduler function](../scheduler_executor/README.md)

## Architecture

```
                         ┌─────────────────────┐
                         │    React Chat UI     │
                         │  (Text + Voice)      │
                         └────────┬─────────────┘
                                  │
                    ┌─────────────┼──────────────┐
                    │             │               │
              POST /invocations  GET /chat/stream WS /ws
              (prod SSE or JSON) (local dev SSE)  (voice)
                    │             │               │
                    ▼             ▼               ▼
              ┌───────────────────────┐   ┌──────────────┐
              │    Routing Agent      │   │    Voice      │
              │    :9000              │   │   Gateway     │
              │                       │   │    :9005      │
              │  Intent classifier    │   │ (Nova Sonic)  │
              │  + orchestrator       │   └──┬──┬──┬─────┘
              └───┬────┬────┬────┬───┘      │  │  │
                  │    │    │    │           │  │  │
         ┌────────┘    │    │    └────┐  ┌──┘  │  └──┐
         ▼             ▼    ▼         ▼  ▼     ▼     ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ Database │ │  Stock   │ │   Web    │ │Scheduler │
   │  Agent   │ │  Data    │ │  Search  │ │  + Email │
   │  :9001   │ │  Agent   │ │  Agent   │ │  (MCP)   │
   │          │ │  :9002   │ │  :9004   │ │          │
   │ Redshift │ │  Yahoo   │ │  Tavily  │ │EventBridge│
   │ + PDF    │ │ Finance  │ │  + Score │ │  + SES   │
   └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

## Agents

### Routing Agent (`routing_agent/`)

The supervisor — classifies intent and delegates. Never answers directly.

| Intent | Delegates To | Example |
|--------|-------------|---------|
| `STOCK_DATA` | Stock Data Agent | "What's AAPL price?" |
| `CLIENT_DATA` | Database Agent | "Show Jennifer Bell's portfolio" |
| `MARKET_NEWS` | Web Search Agent | "Why is tech down today?" |
| `COMPOSITE` | Multiple agents | "How are my client's tech holdings doing?" |

Also exposes scheduling tools (create/list/delete/toggle schedules) and email via MCP gateways.

- **Model**: `ROUTING_BEDROCK_MODEL_ID` (default: Claude Haiku 4.5)
- **Endpoints**: `POST /chat` (sync), `GET /chat/stream` (SSE), `POST /invocations` (AgentCore — supports SSE via `Accept: text/event-stream`)

### Database Agent (`database_agent/`)

Answers questions about clients, portfolios, holdings, AUM, and advisor metrics.

- **Model**: `SUBAGENT_BEDROCK_MODEL_ID` (default: Claude Haiku 4.5)
- **Tools**: `run_sql` (Redshift queries), `get_client_report_pdf` (S3 PDF reports)
- **Schema**: Injected into system prompt at startup from Redshift DDL

### Stock Data Agent (`stock_data_agent/`)

Real-time stock quotes, financial metrics, and comparisons via Yahoo Finance.

- **Model**: `STOCK_AGENT_BEDROCK_MODEL_ID` (default: Claude Sonnet 4)
- **Tools**: `get_stock_quotes` (yfinance) — returns markdown tables + embedded `<!--QUOTES:-->` JSON for UI charts
- **Insights**: Auto-generated from data (52-week positioning, P/E analysis, significant moves) — no LLM hallucination risk

### Web Search Agent (`web_search_agent/`)

Financial news and market intelligence via Tavily with credibility scoring.

- **Model**: `SUBAGENT_BEDROCK_MODEL_ID` (default: Claude Haiku 4.5)
- **Tools**: `web_search` (Tavily API)
- **Scoring pipeline**: Each result scored on relevance (45%), freshness (25%), credibility (30%) before LLM sees it
- **Source tiers**: Reuters/Bloomberg = 1.0, Yahoo Finance = 0.90, unknown = 0.70
- **Anti-hallucination**: System prompt enforces "only use provided evidence" rules

### Voice Gateway (`voice_gateway/`)

Speech-to-speech via Amazon Nova Sonic bidirectional audio streaming.

- **Model**: `VOICE_AGENT_BEDROCK_MODEL_ID` (default: Nova Sonic v1)
- **Transport**: WebSocket (`/ws`) with AudioWorklet PCM capture
- **Design**: Nova Sonic replaces the routing agent for voice — directly orchestrates specialists via tool use (no double-LLM hop)
- **Deployment**: ECS/Fargate (not Lambda — WebSocket connections are long-lived)

## Common Modules (`common/`)

| Module | Purpose |
|--------|---------|
| `memory.py` | AgentCore Memory — STM (3-day conversation) + LTM (30-day semantic extraction) |
| `streaming.py` | SSE event helpers (`token_event`, `status_event`, `done_event`, etc.) |
| `market_data.py` | Chart data builder from yfinance for `<!--CHART:-->` tags |
| `agentcore_server.py` | Shared FastAPI server setup for sub-agents with `/invocations` + `/stream` |
| `redshift.py` | Redshift connection management |
| `schema.py` | DDL schema loader for database agent |
| `sql_tool.py` | SQL execution tool |

## Streaming

The system uses SSE (Server-Sent Events) for real-time streaming:

1. **Tool status** — Hooks (`BeforeToolCallEvent`/`AfterToolCallEvent`) push status updates: "Consulting Stock Data Agent..."
2. **Final response** — After all tools complete, the clean response text is streamed in chunks for typewriter effect
3. **Done event** — Final event includes `marketData` and `sources` for chart rendering

Intermediate tokens (tool reasoning, JSON fragments) are **not** streamed to avoid corrupting the UI.

**Production**: Browser sends `POST /invocations` with `Accept: text/event-stream` to AgentCore → SSE stream back.
**Local dev**: Browser sends `GET /chat/stream` → SSE stream back.

## Environment Variables

### Model IDs (required — defaults provided for CI)

| Variable | Default | Used By |
|----------|---------|---------|
| `ROUTING_BEDROCK_MODEL_ID` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Routing Agent |
| `SUBAGENT_BEDROCK_MODEL_ID` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Database Agent, Web Search Agent |
| `STOCK_AGENT_BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-6` | Stock Data Agent |
| `VOICE_AGENT_BEDROCK_MODEL_ID` | `amazon.nova-2-sonic-v1:0` | Voice Gateway |

### Agent Endpoints (production — AgentCore ARNs)

| Variable | Purpose |
|----------|---------|
| `CLIENT_REPORT_AGENT_ARN` | Database Agent AgentCore ARN |
| `STOCK_DATA_AGENT_ARN` | Stock Data Agent AgentCore ARN |
| `WEB_SEARCH_AGENT_ARN` | Web Search Agent AgentCore ARN |
| `SCHEDULER_GATEWAY_URL` | Scheduler MCP gateway URL |
| `EMAIL_SENDER_GATEWAY_URL` | Email sender MCP gateway URL |

### Agent Endpoints (local dev — HTTP URLs)

| Variable | Default |
|----------|---------|
| `CLIENT_REPORT_AGENT_URL` | `http://localhost:9001` |
| `STOCK_DATA_AGENT_URL` | `http://localhost:9002` |
| `WEB_SEARCH_AGENT_URL` | `http://localhost:9004` |

### Other

| Variable | Purpose |
|----------|---------|
| `TAVILY_API_KEY` | Tavily API key for web search |
| `REPORT_S3_BUCKET` | S3 bucket for PDF reports |
| `AWS_REGION` | AWS region (default: `us-west-2`) |

## Running Locally

```bash
# Terminal 1 — Routing agent (the orchestrator)
cd packages/advisor_chat
PORT=9000 uv run python -m wealth_management_portal_advisor_chat.routing_agent.main

# Terminal 2 — Sub-agents
cd packages/advisor_chat
PORT=9001 uv run python -m wealth_management_portal_advisor_chat.database_agent.main &
PORT=9002 uv run python -m wealth_management_portal_advisor_chat.stock_data_agent.main &
PORT=9004 uv run python -m wealth_management_portal_advisor_chat.web_search_agent.main &

# Terminal 3 — Voice gateway (optional)
cd packages/advisor_chat
PORT=9005 uv run python -m wealth_management_portal_advisor_chat.voice_gateway.main
```

The UI at `http://localhost:4200` connects to the routing agent at `http://localhost:9000`.

## Testing

```bash
pnpm nx test wealth_management_portal.advisor_chat
pnpm nx lint wealth_management_portal.advisor_chat
```

## A2A Protocol

All agent-to-agent communication uses JSON-RPC 2.0:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "message/send",
  "params": {
    "message": {
      "kind": "message",
      "role": "user",
      "messageId": "session-123",
      "parts": [{"kind": "text", "text": "What's AAPL price?"}]
    }
  }
}
```

In production, the routing agent calls specialists via `boto3.client("bedrock-agentcore").invoke_agent_runtime()`. In local dev, it falls back to direct HTTP POST.

## Memory

Two-tier AgentCore Memory:

- **STM (Short-Term)**: Raw conversation turns, 3-day retention. Keeps context within a session.
- **LTM (Long-Term)**: Semantic extraction, 30-day retention. Stores schema knowledge and SQL artifacts with two retrieval namespaces:
  - `/knowledge/{actorId}/` — Semantic search (top 10, relevance ≥ 0.3)
  - `/summaries/{actorId}/{sessionId}/` — Session summaries (top 3, relevance ≥ 0.5)
