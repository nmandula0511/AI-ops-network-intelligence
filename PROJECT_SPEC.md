# AIOps Engineering Project — Charter Communications × Infosys
> **AI IDE Context Document** — Read this before touching any file in this repository.
> This document captures the full technical architecture, business logic, team ownership,
> and implementation roadmap for the AIOps platform at Charter Communications.

---

## 1. WHAT THIS PROJECT IS

Charter Communications (the cable + internet company) operates a national network serving
millions of customers. This project builds an **AIOps (AI for IT Operations) platform**
that uses AWS AI services to automatically detect, diagnose, and resolve network problems
— without human intervention where possible.

The platform has **two products** at different stages of maturity:

| Product | Your workload | Status |
|---|---|---|
| Invincible WiFi | **80% of all your work** | Live in UAT, 140k devices nationally |
| Mobile Offloading | 20% of all your work | Dev only, Charlotte NC, Android only |

---

## 2. PRODUCT 1 — INVINCIBLE WIFI (PRIMARY FOCUS)

### 2.1 What It Is

Charter sells a premium router called **Invincible WiFi**. It has two internet connections:
- **Primary**: Fiber/cable (Charter's own network — cheap for Charter)
- **Backup**: SIM card with 5G LTE (Verizon — Charter pays per usage)

When the cable goes down, the device auto-switches to 5G. When cable comes back, it
should auto-switch back. **The problem: some devices never switch back.**

### 2.2 The Business Problem

```
Device switches to LTE (5G SIM)
         ↓
Charter starts paying Verizon for data
         ↓
Cable comes back online
         ↓
Device does NOT switch back to fiber  ← THIS IS THE BUG
         ↓
Charter keeps paying Verizon indefinitely
```

**Scale**: 140,000 devices deployed nationwide. Even 1% stuck on LTE = 1,400 devices
wasting money continuously.

### 2.3 The Business Rules / Thresholds

```python
# Time a device has been on LTE (5G SIM) instead of fiber
LTE_GREEN_THRESHOLD_MINUTES  = 60   # 0-60 min: normal, no action
LTE_YELLOW_THRESHOLD_MINUTES = 90   # 60-90 min: warning, flag it
LTE_RED_THRESHOLD_MINUTES    = 90   # 90+ min: critical, trigger agent
```

### 2.4 Customer Journey (Aaron's Story — From KT)

```
1. Aaron has Invincible WiFi at home
2. Cable modem goes offline (outage, unplugged, etc.)
3. Device auto-switches to 5G SIM → Charter begins paying Verizon
4. 1 hour passes → Charter's system sends Aaron an email alert
5. Aaron ignores the email (happens 2-7 days)
6. Device is STILL on 5G. Charter is STILL paying.
7. Resolution options (worst to best):
   a. [WORST]  Truck roll  — send a field engineer to Aaron's house ($$$)
   b. [MEDIUM] Charter calls Aaron to troubleshoot
   c. [BEST]   Aaron self-troubleshoots with AI agent guidance
```

**The AIOps goal**: Eliminate truck rolls. Use AI agents to diagnose why the device
is stuck and either auto-fix it or walk Aaron through fixing it himself.

### 2.5 Real-Time Data Source — Kafka

```
Device event (WiFi→LTE or LTE→WiFi) occurs
        ↓
Charter's network immediately captures it
        ↓
Event published to KAFKA topic (real-time stream)
        ↓
Our system consumes the Kafka event
        ↓
Agent triggered if thresholds exceeded
```

This is **LIVE** data — not delayed. Every WiFi↔LTE switch generates an immediate event.

### 2.6 Data Schema — Kafka Event

```json
{
  "device_id": "INV-WIFI-1234567890",
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "customer_account_id": "CHR-98765432",
  "event_type": "WIFI_TO_LTE",        // or "LTE_TO_WIFI"
  "timestamp": "2025-05-14T17:30:00Z",
  "duration_on_lte_minutes": 0,        // starts at 0, increments
  "location": {
    "zip_code": "80111",
    "state": "CO",
    "region": "SW"
  },
  "signal_strength_db": -65,
  "firmware_version": "3.2.1",
  "cable_modem_status": "OFFLINE"      // or "ONLINE"
}
```

---

## 3. PRODUCT 2 — MOBILE OFFLOADING (SECONDARY)

### 3.1 What It Is

When a phone is near a Charter WiFi access point (AP), it should switch from cellular
(LTE/5G) to WiFi automatically. This is called **WiFi offloading** — Charter saves money
by using their own WiFi instead of paying carriers for cellular data.

**The problem**: Phones sometimes stay on cellular even inside WiFi range.

### 3.2 Current Limitations (Do Not Try to Fix These)

- Only works for **Android** phones (18-22% of US market)
- Apple blocks this data entirely (privacy policy)
- Data is **1.5 days delayed** — not real-time
- Only covers **Charlotte, NC** — not scaled nationally
- Product team is NOT actively adding features
- You will only make cosmetic/minor changes here

### 3.3 Three Existing Agents for Mobile Offloading

```
Agent 1 → AP-level analysis (analyzes one access point tower)
Agent 2 → Device-level analysis (analyzes one specific phone's event)
Agent 3 → Full-day phone analysis (analyzes a phone's whole day)
           └─ Status: DEV environment only. NOT in UAT yet.
```

---

## 4. AGENT ARCHITECTURE — THE FULL PICTURE

### 4.1 The Hierarchy

```
                    ┌──────────────────────────┐
                    │     Paul Edworth          │
                    │  (Master Orchestrator)    │
                    │  Built by IR team         │
                    │  Already A2A compatible   │
                    └──────────────┬───────────┘
                    A2A Protocol   │   A2A Protocol
              ┌────────────────────┼───────────────────┐
              ↓                    ↓                    ↓
┌─────────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  Invincible WiFi    │ │  Cable Modem     │ │  Mobile Offload  │
│  Agent              │ │  Agent           │ │  Agents (×3)     │
│  ← YOUR WORK        │ │  ← IR team       │ │  ← Sushma        │
│  80% of all effort  │ │  Not your task   │ │  20% of effort   │
└──────────┬──────────┘ └────────┬─────────┘ └──────────┬───────┘
           │  Tool calls         │ Tool calls            │ Tool calls
           └────────────────────┬┘──────────────────────┘
                                 ↓
                    ┌────────────────────────────┐
                    │     Shared MCP Server      │
                    │  (exposes all @tool fns)   │
                    └────────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ↓                  ↓                  ↓
       ┌──────────┐      ┌──────────────┐   ┌──────────────┐
       │ Aurora   │      │  DynamoDB    │   │   Neptune    │
       │ (SQL)    │      │  (NoSQL)     │   │  (Graph DB)  │
       │ telemetry│      │ state+events │   │ topology     │
       └──────────┘      └──────────────┘   └──────────────┘
```

### 4.2 What Is Paul Edworth?

Paul Edworth is NOT a person. He is the **master orchestrator AI agent** built by the
Internet Reliability (IR) team. His full name in the system is `paul_edworth`.

- Already built and deployed — not your responsibility
- Already supports A2A protocol
- When a Charter Business Unit (CBU) engineer asks a question,
  Paul figures out which sub-agent to call
- Paul reads each sub-agent's `agent_card.json` to know what it can do
- Then calls the right sub-agent via A2A protocol

### 4.3 What Is A2A Protocol?

A2A = **Agent-to-Agent** communication protocol (Google's open standard).

```
Paul wants to check why a device is stuck on LTE:
  1. Paul reads our agent_card.json
  2. Paul sees our agent has tool: "analyze_device_lte_duration"
  3. Paul calls our agent via A2A: POST /a2a/tasks/send
     { "input": { "device_id": "INV-WIFI-123", "date": "2025-05-14" } }
  4. Our agent processes and returns structured response
  5. Paul reads our response and synthesizes answer for CBU engineer
```

### 4.4 What Is agent_card.json?

Every A2A-compatible agent must have an `agent_card.json` at the root URL.
This is a machine-readable description of the agent's capabilities.

```json
{
  "name": "Invincible WiFi Agent",
  "description": "Diagnoses devices stuck on LTE instead of switching back to fiber",
  "version": "2.0.0",
  "url": "https://agent.aiops.charter.internal/invincible-wifi",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "skills": [
    {
      "id": "analyze_lte_duration",
      "name": "Analyze LTE Duration",
      "description": "Determines why a device is stuck on LTE",
      "inputModes": ["application/json"],
      "outputModes": ["application/json"],
      "parameters": {
        "device_id": { "type": "string", "required": true },
        "date": { "type": "string", "format": "date", "required": false }
      }
    }
  ]
}
```

---

## 5. THE SIX REFACTORING STORIES — YOUR EXACT TASKS

This is the core of your work. The existing agents were written as vanilla Python by
**Sushma** (offshore engineer). They need to be refactored into a proper production
architecture. You and Sushma split these 6 stories.

### Story 1 — A2A Compatible Agent

**Problem**: Current agents are isolated. Paul cannot call them.
**Solution**: Convert each agent to expose an A2A-compatible HTTP endpoint + `agent_card.json`.

```python
# BEFORE — vanilla Python, no standard interface
class InvincibleWifiAnalyzer:
    def analyze(self, device_id: str):
        # just a class method, no HTTP, no A2A
        pass

# AFTER — A2A compatible Strands agent
from strands import Agent
from strands.agent.a2a import A2AServer

agent = Agent(
    name="invincible-wifi-agent",
    model="amazon.nova-pro-v1:0",
    tools=[get_device_lte_duration, analyze_cable_modem_status, generate_recommendations],
    system_prompt=SYSTEM_PROMPT
)

# Expose A2A endpoint
a2a_server = A2AServer(agent=agent, port=8080)
# Automatically serves agent_card.json at GET /
# Accepts A2A task calls at POST /a2a/tasks/send
a2a_server.run()
```

### Story 2 — Pydantic Models for All I/O

**Problem**: Agents use raw Python dicts for input/output. No type safety, no validation.
**Solution**: Define Pydantic models for every request and response.

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date

# REQUEST MODELS
class DeviceAnalysisRequest(BaseModel):
    device_id: str = Field(..., description="Invincible WiFi device identifier")
    analysis_date: Optional[date] = Field(None, description="Date to analyze; defaults to today")
    include_history_days: int = Field(7, ge=1, le=30)

class BulkDeviceRequest(BaseModel):
    device_ids: list[str] = Field(..., min_length=1, max_length=100)
    region: Optional[str] = None

# RESPONSE MODELS
class DeviceAnalysisResponse(BaseModel):
    device_id: str
    severity: Literal["GREEN", "YELLOW", "RED"]
    lte_duration_minutes: int
    root_cause: str
    recommended_action: str
    estimated_resolution_time_minutes: int
    requires_truck_roll: bool
    confidence_score: float = Field(..., ge=0.0, le=1.0)

class AgentFinalResponse(BaseModel):
    summary: str
    devices_analyzed: int
    critical_devices: list[DeviceAnalysisResponse]
    total_estimated_cost_per_day_usd: float
    actions_recommended: list[str]
```

### Story 3 — Reusable @tool Decorated Functions

**Problem**: All logic is in monolithic utility functions inside the agent. Nothing is
reusable. Other agents cannot call these functions.

**Solution**: Convert every utility into a Strands `@tool` decorated function. These get
exposed via the MCP server and can be called by any agent.

```python
from strands import tool
from typing import Optional
import boto3
from datetime import datetime, date

# BEFORE — not reusable
def _get_device_data_internal(device_id: str) -> dict:
    """private helper, nobody else can use this"""
    conn = get_aurora_connection()
    return conn.execute(f"SELECT * FROM devices WHERE id = '{device_id}'")

# AFTER — proper @tool, usable by any agent
@tool
def get_device_lte_duration(
    device_id: str,
    reference_date: Optional[str] = None
) -> dict:
    """
    Retrieves how long a specific Invincible WiFi device has been
    continuously on LTE (5G SIM) instead of fiber.
    
    Args:
        device_id: The device identifier (format: INV-WIFI-XXXXXXXXXX)
        reference_date: ISO date string YYYY-MM-DD; defaults to today
    
    Returns:
        dict with keys: device_id, lte_duration_minutes, last_wifi_event,
                        cable_modem_status, threshold_status (GREEN/YELLOW/RED)
    """
    target_date = date.fromisoformat(reference_date) if reference_date else date.today()
    aurora = get_aurora_client()
    result = aurora.execute_statement(
        sql="""
            SELECT device_id, 
                   TIMESTAMPDIFF(MINUTE, wifi_to_lte_ts, NOW()) as lte_minutes,
                   cable_modem_online
            FROM device_events 
            WHERE device_id = :device_id 
              AND DATE(wifi_to_lte_ts) = :target_date
              AND lte_to_wifi_ts IS NULL
            ORDER BY wifi_to_lte_ts DESC LIMIT 1
        """,
        parameters=[
            {"name": "device_id", "value": {"stringValue": device_id}},
            {"name": "target_date", "value": {"stringValue": str(target_date)}}
        ]
    )
    # ... process and return structured dict

@tool
def get_cable_modem_status(device_id: str) -> dict:
    """
    Checks whether the cable modem associated with a device is online.
    Returns modem status, last seen online timestamp, and outage duration.
    """
    pass

@tool
def check_firmware_version(device_id: str) -> dict:
    """
    Returns current firmware version and whether an update is pending.
    Outdated firmware is a common cause of LTE-stuck issues.
    """
    pass

@tool
def generate_customer_recommendation(
    device_id: str,
    root_cause: str,
    lte_duration_minutes: int
) -> dict:
    """
    Generates human-readable troubleshooting steps for the customer.
    Tailored to root cause. Prioritizes self-service over truck roll.
    """
    pass

@tool
def flag_for_truck_roll(device_id: str, reason: str, priority: str) -> dict:
    """
    Creates a truck roll ticket in Charter's field service system.
    Only call this when all other options are exhausted.
    Priority: LOW / MEDIUM / HIGH / CRITICAL
    """
    pass
```

### Story 4 — Factory Pattern (One Agent Instance Per User)

**Problem**: If two Charter engineers use the agent simultaneously, they share one
agent instance. Their conversation context can bleed into each other.

**Solution**: Factory pattern — dynamically create a fresh, isolated agent per user session.

```python
from strands import Agent
from typing import Optional
import uuid

# System prompt template
INVINCIBLE_WIFI_SYSTEM_PROMPT = """
You are an AIOps diagnostic agent specializing in Invincible WiFi devices.
Your job is to diagnose why devices are stuck on LTE instead of fiber,
and recommend the least disruptive resolution.

Business rules:
- GREEN: < 60 minutes on LTE — monitor only
- YELLOW: 60-90 minutes on LTE — proactive outreach
- RED: > 90 minutes on LTE — immediate intervention required
- NEVER recommend a truck roll unless all self-service options fail.

Always respond with:
1. Root cause (specific, not vague)
2. Confidence level (0-100%)
3. Recommended action steps (ordered by least to most disruptive)
4. Estimated resolution time
"""

def create_invincible_wifi_agent(
    session_id: Optional[str] = None,
    user_context: Optional[dict] = None
) -> Agent:
    """
    Factory function. Creates an isolated agent instance per user session.
    Never share instances across users — context bleeds between sessions.
    
    Args:
        session_id: Unique identifier for this session; auto-generated if None
        user_context: Optional dict with engineer's name, team, permissions
    
    Returns:
        Fresh Agent instance with no prior conversation history
    """
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    # Personalize system prompt if user context provided
    system_prompt = INVINCIBLE_WIFI_SYSTEM_PROMPT
    if user_context:
        system_prompt += f"\nCurrent user: {user_context.get('name', 'Unknown')}"
        system_prompt += f"\nTeam: {user_context.get('team', 'Unknown')}"
    
    return Agent(
        model="amazon.nova-pro-v1:0",
        tools=[
            get_device_lte_duration,
            get_cable_modem_status,
            check_firmware_version,
            generate_customer_recommendation,
            flag_for_truck_roll,
        ],
        system_prompt=system_prompt,
        session_id=session_id,   # isolates conversation history
    )

# Usage — each API request gets its own agent
def handle_analysis_request(request: DeviceAnalysisRequest, user_id: str):
    agent = create_invincible_wifi_agent(
        session_id=f"{user_id}-{request.device_id}",
        user_context={"name": user_id}
    )
    response = agent(f"Analyze device {request.device_id}")
    return response
```

### Story 5 — Remove Lambda + API Gateway, Use Direct REST

**Problem**: Current deployment is needlessly complex:

```
UI → API Gateway → Lambda → Agent Core
          (3 hops, slow, hard to debug)
```

Lambda and API Gateway add latency, cost, and complexity with no benefit here.

**Solution**: Expose Agent Core directly via REST.

```
UI → Agent Core (direct)
     (1 hop, simple, fast)
```

```python
# main.py — new direct REST deployment
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="Invincible WiFi AIOps Agent",
    description="Direct REST API for agent — no Lambda, no API Gateway",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://charter-aiops.internal"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"]
)

@app.get("/")
async def agent_card():
    """A2A agent card — Paul reads this to discover our capabilities"""
    return load_agent_card_json()

@app.post("/a2a/tasks/send")
async def handle_task(request: A2ATaskRequest, session_id: str = Depends(get_session)):
    """Main A2A endpoint — Paul calls this"""
    agent = create_invincible_wifi_agent(session_id=session_id)
    result = agent(request.input.get("message", ""))
    return A2ATaskResponse(output=result, session_id=session_id)

@app.post("/analyze")
async def analyze_device(request: DeviceAnalysisRequest):
    """Direct analysis endpoint for Charter UI"""
    agent = create_invincible_wifi_agent()
    result = agent(f"Analyze device {request.device_id}")
    return DeviceAnalysisResponse(**parse_agent_response(result))

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

### Story 6 — Terraform for Deployment (Infrastructure as Code)

**Problem**: Current deployment requires manual AWS console clicks. Not repeatable.
**Solution**: Terraform scripts that deploy the entire stack with one command.

```hcl
# main.tf

terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

variable "environment" {
  description = "DEV, UAT, or PROD"
  type        = string
}

# ECS Task Definition for the agent
resource "aws_ecs_task_definition" "invincible_wifi_agent" {
  family                   = "invincible-wifi-agent-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"

  container_definitions = jsonencode([{
    name  = "agent"
    image = "${aws_ecr_repository.agent.repository_url}:latest"
    portMappings = [{ containerPort = 8080 }]
    environment = [
      { name = "ENV",           value = var.environment },
      { name = "AWS_REGION",    value = "us-east-1" }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group  = "/ecs/invincible-wifi-agent-${var.environment}"
        awslogs-region = "us-east-1"
      }
    }
  }])
}

# ECS Service
resource "aws_ecs_service" "invincible_wifi_agent" {
  name            = "invincible-wifi-agent-${var.environment}"
  cluster         = aws_ecs_cluster.aiops.id
  task_definition = aws_ecs_task_definition.invincible_wifi_agent.arn
  desired_count   = var.environment == "PROD" ? 3 : 1
  launch_type     = "FARGATE"
}

# Aurora DB (existing — just reference)
data "aws_rds_cluster" "aurora" {
  cluster_identifier = "aiops-aurora-${var.environment}"
}
```

---

## 6. IMPORTANT CLARIFICATION — THE SUMMARY AGENT

> ⚠️ This is a common point of confusion. Know this cold.

When someone says **"the summary agent"**, they do NOT mean an actual Strands agent
running in Agent Core. It is a **Glue Job** (AWS Glue = ETL batch processing service)
that has access to Bedrock but is nicknamed "the summary agent."

```
WRONG understanding:
  "Where does the summary agent live in Agent Core?"

CORRECT understanding:
  The summary agent is a post-processing Glue Job.
  It runs AFTER the main agent analysis is done.
  It uses Bedrock to summarize and aggregate results.
  It is NOT a Strands agent.
  It is NOT in Agent Core.
  It is a separate AWS Glue batch job.
```

If someone asks where the summary agent is, the answer is:
> "It's not in Agent Core — it's a post-processing Glue Job with Bedrock access."

---

## 7. TEAM STRUCTURE

| Person | Role | Location | What they own |
|---|---|---|---|
| You | AIOps Engineer (Infosys) | Greenwood Village, CO | Invincible WiFi agent refactoring (stories 1-6) |
| Sushma | AIOps Engineer (offshore) | India | Original code author; split 6 stories with you |
| Gurkeerat (GK) | Senior AIOps Engineer | Onsite | Technical guide; introduced architecture |
| Basu | Manager | Infosys | Your Infosys manager |
| IR Team | Internet Reliability | Charter internal | Paul Edworth; Cable Modem Agent |
| Paul Edworth | AI Agent (not a person) | AWS | Master orchestrator |

### How to Work With Sushma

- She wrote the existing agent code — knows it deeply
- You will split the 6 stories between you
- Typical split: You take stories 1, 4, 5, 6 (architecture/deployment)
- Sushma takes stories 2, 3 (models/tools) since she knows the data schema
- Coordinate via Jira stories + Slack

---

## 8. AWS TECH STACK

### Core AI Services

```
Amazon Bedrock      → Foundation models (Claude, Nova, Titan)
                      Model ID: amazon.nova-pro-v1:0
                      Used for: agent reasoning, generating recommendations

Amazon SageMaker    → Custom ML model training and inference
                      Used for: predictive models (will a device fail?)

Amazon Comprehend   → NLP text analysis
                      Used for: parsing customer support tickets, logs

AWS Strands SDK     → Agent framework (like LangChain but AWS-native)
                      Used for: building all agents
```

### Data Infrastructure

```
Amazon Aurora       → Relational SQL database (MySQL compatible)
                      Stores: device telemetry, event history, thresholds

Amazon DynamoDB     → NoSQL key-value store
                      Stores: session state, real-time device status

Amazon Neptune      → Graph database
                      Stores: network topology, device relationships
                      (e.g., which AP is this device's nearest neighbor?)

Apache Kafka        → Real-time event streaming
                      Produces: WiFi↔LTE switch events
                      Our agents CONSUME from Kafka
```

### Deployment + Infrastructure

```
AWS ECS Fargate     → Container runtime for agents (after Lambda removal)
AWS ECR             → Container registry (Docker images)
AWS CloudWatch      → Logging and monitoring
AWS IAM             → Identity and permissions
Terraform           → Infrastructure as Code (Story 6)
```

### Development Tools

```
Python 3.11+        → All agent code
FastAPI             → REST API framework (replaces API Gateway)
Pydantic v2         → Data validation (Story 2)
Strands SDK         → AWS agent framework
pytest              → Testing
Docker              → Container packaging
```

---

## 9. PROJECT FILE STRUCTURE (TARGET STATE)

```
aiops-invincible-wifi/
│
├── agent_card.json              # A2A discovery file (Story 1)
│
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── factory.py           # create_agent() factory (Story 4)
│   │   ├── prompts.py           # System prompts
│   │   └── a2a_server.py        # A2A protocol wrapper (Story 1)
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── requests.py          # Pydantic request models (Story 2)
│   │   └── responses.py         # Pydantic response models (Story 2)
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── aurora_tools.py      # @tool fns for Aurora DB (Story 3)
│   │   ├── device_tools.py      # @tool fns for device analysis (Story 3)
│   │   ├── bedrock_tools.py     # @tool fns for Bedrock calls (Story 3)
│   │   └── action_tools.py      # @tool fns for remediation (Story 3)
│   │
│   └── api/
│       ├── __init__.py
│       └── main.py              # FastAPI app — direct REST (Story 5)
│
├── infra/
│   ├── main.tf                  # Terraform main (Story 6)
│   ├── variables.tf
│   ├── outputs.tf
│   └── environments/
│       ├── dev.tfvars
│       ├── uat.tfvars
│       └── prod.tfvars
│
├── tests/
│   ├── unit/
│   │   ├── test_models.py
│   │   └── test_tools.py
│   └── integration/
│       └── test_agent.py
│
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 10. KEY CONCEPTS GLOSSARY

| Term | What it actually means |
|---|---|
| AIOps | Using AI/ML to automate IT operations (detecting outages, routing tickets) |
| A2A | Agent-to-Agent protocol. Standard way for AI agents to call each other |
| agent_card.json | A JSON file describing what an agent can do. Paul reads this |
| MCP | Model Context Protocol. Exposes @tools so multiple agents can share them |
| Strands | AWS's Python SDK for building AI agents (like LangChain) |
| @tool | Decorator that makes a Python function callable by an AI agent |
| Factory Pattern | Create a fresh object per user instead of sharing one instance |
| Pydantic | Python library for data type validation. Like TypeScript but for Python |
| Aurora | AWS managed MySQL database. Not the same as regular MySQL |
| Neptune | AWS graph database. Stores RELATIONSHIPS between things |
| Kafka | Real-time message streaming. Like a very fast message queue |
| Glue Job | AWS batch ETL (Extract Transform Load) data processing job |
| Truck roll | Sending a field engineer to a customer's house. Expensive. Avoid it. |
| LTE | 4G/5G cellular network. Charter pays Verizon when devices use this |
| A2A task | A structured request sent from one agent to another via A2A protocol |
| UAT | User Acceptance Testing. The pre-production environment |
| DEV | Development environment. Only for developers, not real users |
| PROD | Production. Live. Real customers. Be very careful here |
| Sushma | The offshore engineer who originally wrote the agents |
| Paul Edworth | The master orchestrator AI agent. NOT a person |
| IR Team | Internet Reliability team. They own Paul and Cable Modem Agent |
| CBU | Charter Business Unit. The team using the agents day-to-day |

---

## 11. ENVIRONMENT SETUP FOR LOCAL DEVELOPMENT

```bash
# Python version
python --version   # must be 3.11+

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or .venv\Scripts\activate  # Windows

# Install dependencies
pip install strands-agents          # AWS agent framework
pip install pydantic>=2.0           # Data validation (Story 2)
pip install fastapi uvicorn         # REST API (Story 5)
pip install boto3                   # AWS SDK
pip install pytest pytest-asyncio   # Testing

# AWS credentials (use SSO or keys from Infosys)
aws configure

# Required AWS permissions:
# - bedrock:InvokeModel
# - rds-data:ExecuteStatement
# - dynamodb:GetItem, PutItem
# - neptune-db:connect
```

---

## 12. WHAT THE AI IDE NEEDS TO KNOW

If you are an AI IDE reading this file, here is the critical context:

1. **This is a Python project** using AWS Strands SDK as the agent framework
2. **The primary task** is refactoring existing agents per the 6 stories above
3. **Never use Lambda** — we are removing Lambda (Story 5). Use FastAPI + ECS instead
4. **Always use Pydantic** for request/response models — no raw dicts
5. **Always use @tool decorator** for any function an agent might call
6. **Always use the factory pattern** — never share one agent instance across users
7. **The model to use** is `amazon.nova-pro-v1:0` unless specified otherwise
8. **agent_card.json must exist** at the root endpoint — Paul needs to read it
9. **Thresholds**: GREEN < 60min, YELLOW 60-90min, RED > 90min on LTE
10. **The summary agent is a Glue Job** — do not look for it in Agent Core
11. **Invincible WiFi = 80% priority**. Mobile offloading = 20%, mostly cosmetic
12. **Target environments**: DEV → UAT → PROD. Never skip UAT.
13. **Sushma knows the data schema** — ask her before writing Aurora queries
14. **Kafka events are real-time** — Invincible WiFi data is live, not delayed
