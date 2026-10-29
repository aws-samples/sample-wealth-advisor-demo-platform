# Research References & Source Material

## AWS References Identified During Research (July 2026)

### Tier 1: Directly Applicable (TFC-Endorsed)

| Resource | Relevance | Link |
|----------|-----------|------|
| The Art of the Possible: Building an Intelligent Wealth Management Platform (Part 1) | Automated report pipeline, advisor capacity problem, same tech stack | [Blog](https://aws.amazon.com/blogs/industries/the-art-of-the-possible-building-an-intelligent-wealth-management-platform-part-1) |
| Automate Investment Research Using Strands Agents on Bedrock AgentCore | 6-agent collaboration pattern, investment research, multi-researcher bottleneck | [Blog](https://aws.amazon.com/blogs/industries/automate-investment-research-using-strands-agents-on-bedrock-agentcore) / [GitHub](https://github.com/aws-samples/sample-genai-market-data-analysis) |
| From PDFs to Insights: Architecting an IDP Pipeline | 4-layer architecture for heterogeneous documents, BDA, agentic coordination | [Blog](https://aws.amazon.com/blogs/machine-learning/from-pdfs-to-insights-architecting-an-intelligent-document-processing-pipeline-with-aws-generative-ai-services/) |

### Tier 2: Highly Relevant Supporting Material

| Resource | Relevance | Link |
|----------|-----------|------|
| Agentic GraphRAG for Capital Markets | Multi-hop due diligence, entity relationships, "days to seconds" | [Blog](https://aws.amazon.com/blogs/industries/agentic-graphrag-for-capital-markets) |
| From RAG to Fabric (Parts 1 & 2) | GenAIIC lessons on heterogeneous financial documents | [Part 2](https://aws.amazon.com/blogs/machine-learning/from-rag-to-fabric-lessons-learned-from-building-real-world-rags-at-genaiic-part-2) |
| Accelerate Financial Statement Analysis with Bedrock | Financial reporting generation from 10-Ks, balance sheets | [Blog](https://aws.amazon.com/blogs/machine-learning/accelerate-your-financial-statement-analysis-with-amazon-bedrock-and-generative-ai) |
| Multi-Agent Regulatory Compliance (Bedrock + CrewAI) | Specialized compliance agents, document-vs-framework assessment | [Blog](https://aws.amazon.com/blogs/machine-learning/automating-regulatory-compliance-a-multi-agent-solution-using-amazon-bedrock-and-crewai) |

### Customer Case Studies (Structurally Identical)

| Customer | Use Case | Relevance | Link |
|----------|----------|-----------|------|
| Parameta (TP ICAP) | Regulation PDF review → compliance assessment | 1 month → minutes, 3-week build | [Case Study](https://aws.amazon.com/solutions/case-studies/parameta-tp-icap-bedrock/) |
| PitCrew (Wealth Mgmt) | Form ADV review, compliance cross-referencing | Automated Reasoning checks in Guardrails | [Case Study](https://aws.amazon.com/solutions/case-studies/pitcrew-case-study/) |
| Bridgewater Associates | LLM-powered Investment Analyst Assistant | Approved public reference | N/A |

### AWS Solutions Library

| Solution | Relevance | Link |
|----------|-----------|------|
| Guidance for Investment Analysis Using Amazon Bedrock | Deployable reference architecture | [Solution](https://aws.amazon.com/solutions/guidance/investment-analysis-using-amazon-bedrock) |
| Guidance for IDP Agents on AWS | FSI multi-agent doc processing, HITL flow | [Solution](https://aws.amazon.com/solutions/guidance/intelligent-document-processing-agents-on-aws/) |
| Agentic AI Regulatory Compliance Starter Kit (Grid Dynamics) | Partner solution, 50% compliance response time reduction | [Marketplace](https://aws.amazon.com/marketplace/pp/prodview-dyr5wkvcn753g) |

### Workshops & Labs

| Workshop | What It Builds | Link |
|----------|---------------|------|
| GenAI-Powered Investment Research Portal | Bedrock KB + MCP + Strands agent | [Workshop](https://catalog.us-east-1.prod.workshops.aws/workshops/11f9bcd2-c7a3-4be0-ad2b-158a23aaf095/en-US) |
| Extract Data from Documents Using Multimodal GenAI | Claude 3.5 for charts/tables in financial PDFs | [Workshop](https://catalog.us-east-1.prod.workshops.aws/workshops/d6cbdf25-9a85-4cff-8db7-32f915df96ad/en-US/data-extraction-techniques/work-with-charts-and-tables) |
| AgentCore Getting Started | Runtime, Memory, Observability, Gateway, Policy | [Workshop](https://catalog.workshops.aws/agentcore-getting-started/en-US) |
| Evaluation in GenAI with Bedrock | Evaluation frameworks for production GenAI | [Workshop](https://catalog.us-east-1.prod.workshops.aws/workshops/a2a9ba66-60b1-4dca-b38f-b2112d82d1b8/en-US) |

### Internal Videos (Broadcast)

| Video | Relevance | Link |
|-------|-----------|------|
| Intelligent Wealth Management with AI Agents | FSI TFC demo, shown to IGM, Vanguard, Ameriprise, MyVest | [Broadcast](https://broadcast.amazon.com/videos/1924964) |
| Wealth & Asset Management Use Cases Powered by GenAI | Comprehensive WAM value chain | [Broadcast](https://broadcast.amazon.com/videos/1084259) |
| The Nickel: GenAI Wealth Management Chatbot | BBVA in production, reusable assets | [Broadcast](https://broadcast.amazon.com/videos/1679175) |

### Governance & Compliance

| Resource | Relevance | Link |
|----------|-----------|------|
| Well-Architected FSI Lens (GenAI & Agentic AI update) | Governance framework for regulated FSI deployment | [Blog](https://aws.amazon.com/blogs/industries/announcing-the-well-architected-fsi-lens-updated-for-generative-ai-and-agentic-ai) |

### Internal Wiki Pages

| Page | Relevance | Link |
|------|-----------|------|
| FSI Agentic AI Accelerator (AAA) | Program for FSI customers, tag #FSIAgents | [Wiki](https://w.amazon.com/bin/view/AGS-FinServe-SolArch-NAMER/GenAI/Agentic-AI-Accelerator/) |
| Capital Markets Demos for GenAI | Document summarization, compliance reporting, investor reports | [Wiki](https://w.amazon.com/bin/view/AGS-FinServe-SolArch-NAMER/GenAI/Demos/CapitalMarkets/) |
| GenAIIC Reusable Assets | Rule Validator, Research Copilot, Correlate, FSI Chatbot | [Wiki](https://w.amazon.com/bin/view/AWS/Teams/Proserve/GenAIID/GenAIIC/GenAIIC-Reusable-Assets/) |

### GenAIIC Reusable Assets (Directly Applicable)

| Asset ID | Name | Relevance |
|----------|------|-----------|
| uksb-z6i91u0o6h | Rule Validator | Evaluates documents against user-defined rules, compliance reports with scoring |
| uksb-jgyiww0u3s | Research Copilot | AI-powered content creation and validation for researchers |
| uksb-q2d4demnd9 | Correlate | Checks hypotheses against multiple data sources, generates reports |
| uksb-to0orkxuz5 | FSI Advisory Chatbot | FSI-specific chatbot on Bedrock + Fargate |

### Partner Solutions

| Partner | Solution | Relevance |
|---------|----------|-----------|
| SoftwareOne | Due Diligence Agent | Ingests DDQ + source docs, auto-populates across categories, generates IC memos |
| Grid Dynamics | Agentic AI Regulatory Compliance Starter Kit | Pre-built FSI compliance accelerator |

---

## Internal-Only Resources (Do Not Share with Customer)

### Highspot Content

| Resource | Link |
|----------|------|
| Agentic Investment Assistant (interactive demo) | https://d2wlt44sons8f.cloudfront.net/I3/index.html |
| Investment AI Assistant (multi-agent demo) | https://demos.genai.aws.dev/demos/0b6e8ae2-f8a8-4be7-af86-d447346c47b6 |
| FSI Technical Content Hub (AI/ML) | https://aws.highspot.com/items/68d1a4e7b06ff6efb3206cdb |
| Modernizing Trade Lifecycle — Pre-Trade: Investment Research | https://aws.highspot.com/items/65e777111330b4f5e5b6f63c |
| FSI Generative AI Messaging Guide 2025 | https://aws.highspot.com/items/681e4e2281f484ba6b9d5be3 |

### Curated TFC Collections

| Collection | ID |
|------------|-----|
| Generative AI for Financial Services | f7905d4a-2ce9-4794-814b-27defda7ec73 |
| Capital Markets | 9de65816-6a7a-44bd-a3a8-187ab8346c69 |
| Agentic AI: Enterprise Platform Engineering | ad8a5283-cda2-42c7-955f-98fba867ff31 |
