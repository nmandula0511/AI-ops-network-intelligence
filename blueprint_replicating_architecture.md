# Blueprint: Resilient Device Diagnostics System Architecture

This document serves as a comprehensive system architecture blueprint and prompt. You can copy and paste this file directly to another AI agent to replicate the same multi-repository architecture, decoupling patterns, security frameworks, and resilient agent patterns on a different codebase.

---

## 🏗️ Terminology Mapping
To apply this architecture to any system, replace the placeholders below with your domain-specific terms:

| Original System Term | Placeholder/Generic Term | Description |
| :--- | :--- | :--- |
| **CBU (Cable Modem)** | **Smart Device / Edge Node** | The hardware device being monitored. |
| **LTE Switchover / Failover** | **Backup Connectivity Event** | The anomaly or fallback event being analyzed. |
| **CM/RCA Agent** | **Diagnostics Agent** | The AI detective running the analysis. |
| **Aurora DB / `inwifi`** | **Telemetry Database** | The database housing historical metrics. |
| **SpecNetAI API / `ir-api`** | **NetSense Core API** | The FastAPI backend handling application logic. |
| **MCP Gateway** | **Central MCP Gateway** | The AWS Bedrock AgentCore MCP Gateway. |
| **Chalk RAG** | **Documentation RAG Target** | The documentation index used for semantic searches. |
| **Agent Tools API / Neptune** | **Topology Graph Target** | The network relation/topology database. |

---

## 🗺️ Architectural Topology

The system consists of three decoupled components:

```
                      ┌────────────────────────────────────┐
                      │        Central API Service         │
                      │       (FastAPI / ECS Fargate)      │
                      └──────────────────┬─────────────────┘
                                         │
                         [SigV4 signed HTTP POST / RPC]
                                         │
                                         ▼
                      ┌────────────────────────────────────┐
                      │         Diagnostics Agent          │
                      │    (Strands A2AServer / Bedrock)   │
                      └──────────┬──────────────────┬──────┘
                                 │                  │
                [Degraded Fallback: Local MCP]      │ [Primary Path: MCP Client]
                                 │                  │
                                 ▼                  ▼
                      ┌────────────────────┐ ┌──────────────────────────┐
                      │  Local MCP Server  │ │    Central MCP Gateway   │
                      │ (Queries Database) │ │ (AWS Bedrock AgentCore)  │
                      └────────────────────┘ └──────────┬───────────────┘
                                                        │
                                          ┌─────────────┼─────────────┐
                                          │             │             │
                                          ▼             ▼             ▼
                                     Central API    Doc RAG     Topology Graph
                                    (NetSense Core) (Chalk)     (Agent Tools)
```

---

## 📋 Comprehensive Task Description & Implementation Checklist

### Repository 1: Central API Service (Backend API)
Deploy a high-performance **FastAPI** application containerized via Docker and deployed on serverless hosting (e.g. AWS ECS Fargate).

- [ ] **FastAPI Base Routing**:
  - Implement a central router (`/device-feed`) with endpoints for stats, coordinates, history, and triggering diagnostics.
- [ ] **Unified Agent Trigger Endpoint**:
  - Create an endpoint `POST /device-feed/diagnose` that calls the Diagnostics Agent.
  - Implement a service client to sign requests with secure AWS signatures (SigV4) and forward them to the agent using the JSON-RPC 2.0 (A2A) protocol structure.
- [ ] **Telemetry Data Endpoints**:
  - Create endpoints `/device-feed/records` (paginated history queries) and `/device-feed/metrics` (SNMP / telemetry metrics).
  - Implement database fallback queries if telemetry metrics tables do not exist in the dev environment.
- [ ] **Semantic Retrieval Endpoint**:
  - Create a route `/device-feed/kb-context` to retrieve text chunks from your document Knowledge Base using a semantic vector search service.
- [ ] **Optimizations & Performance**:
  - Integrate structured JSON logging with correlation IDs across all logs.
  - Optimize count endpoints using an in-memory cache warming strategy to avoid expensive database GSI scans.

---

### Repository 2: Diagnostics Agent (AI Diagnostic Engine)
Build a modular agent package using a factory pattern, exposing a Strands-based Agent-to-Agent (A2A) server.

- [ ] **A2A Server Setup**:
  - Use `strands.multiagent.a2a.A2AServer` to expose the agent at `/`.
  - Expose a `/ping` health check endpoint *before* mounting the A2A server to prevent route shadowing.
- [ ] **Input / Output Model Boundaries**:
  - Define strict Pydantic models for incoming requests (validate formats, normalize inputs) and outgoing responses.
  - Enforce range boundaries on scores (e.g., confidence score in `[0.0, 100.0]`) and restrict classifications to specific String Enums.
- [ ] **Agent Factory Pattern**:
  - Implement a `create_diagnostics_agent(mcp_tools=None)` factory.
  - Use a high-performance LLM (such as Amazon Nova Pro) configured for structured outputs (`temperature=0`, `streaming=False`, `topK=1`).
- [ ] **Resilient MCP Client Lifecycle**:
  - Instantiate a deferred MCP client (`MCPClient`). Do not run network handshakes inside the factory.
  - Execute `mcp_client.__enter__()` inside a `try/except` block at server startup.
  - **Graceful Degradation Requirement**: If the MCP gateway is unreachable, do not crash the startup routine. Fall back to RAG-only mode with local tools.
- [ ] **Divergence Engine & Capture Hooks**:
  - Create a local python tool that executes hard, rule-based mathematical scoring equations on the telemetry data.
  - Implement a custom agent hook that saves the output of the mathematical engine.
  - Add a Pydantic model validator that compares the AI's classification confidence with the rule-based engine score. Log a warning if the AI's opinion diverges from the math rules.

---

### Repository 3: Central MCP Gateway (Terraform)
Provision the secure network adapter gateway via Terraform.

- [ ] **AWS Bedrock AgentCore Gateway**:
  - Create an `aws_bedrockagentcore_gateway` resource configured to use the `MCP` protocol and `AWS_IAM` authorizers.
- [ ] **API Key Providers**:
  - Provision credential providers in Secrets Manager to hold token credentials for backend target services.
- [ ] **Gateway Targets Configuration**:
  - Declare `aws_bedrockagentcore_gateway_target` blocks mapping the endpoints.
  - Inject the target base URLs using templated OpenAPI specs (`openapi/*.json.tftpl`).
- [ ] **Three Primary Targets**:
  - **Target 1**: Central API (NetSense Core target) -> routes to telemetry records, SNMP metrics, and KB context.
  - **Target 2**: Documentation RAG (Chalk target) -> routes to document storage.
  - **Target 3**: Topology Graph (Agent Tools target) -> routes to Neptune graph queries.
