# Sentinel Architecture

## Overview

Sentinel separates investigation orchestration from deterministic control and execution.

```text
Client
  |
  ├── FastAPI REST API
  |
  └── CLI

    Both connect to:
  |
  v
Async Queue
  |
  v
Worker
  |
  v
LangGraph
  |
  v
Supervisor
  |
  ├---- Behaviour Specialist
  |
  ├---- Context Specialist
  |
  ├---- Network Specialist
  |
  v
Disposition
  |
  v
Policy Engine
  |
  ├---- BLOCK
  |
  ├---- ALLOW
  |
  ├---- REQUIRE_APPROVAL
              |
              v
        Human Approval
              |
          +---+---+
          |       |
       APPROVE  REJECT
          |       |
          v       v
       Execute   Skip
```

## Design Principles

### 1. Specialist Isolation

Each specialist is responsible for one investigative domain:

- **Behaviour**: Transaction and behavioural signals
- **Context**: Account and customer context
- **Network**: Relationships and connected entities

### 2. Routing-only Supervisor

The supervisor determines which specialist should run but does not replace the specialist's domain reasoning.

### 3. Deterministic Policy

Policy decisions are implemented in Python rather than delegated to the LLM.

The LLM proposes. The policy engine decides what is permitted.

### 4. Human Approval

Consequential actions require explicit approval before execution.

### 5. Asynchronous Execution

The API accepts the investigation and returns a job ID while the queue and workers process the investigation.

### 6. Persistent Graph State

The LangGraph checkpointer maintains investigation state across execution and human approval interruptions.

## Component Details

### FastAPI

Provides the external REST API for submitting and monitoring investigations.

### Async Queue

Allows investigation requests to be accepted without waiting for completion.

### LangGraph

Coordinates the investigation workflow and persists graph state.

### Policy Engine

Applies deterministic business rules to the proposed action. The LLM cannot bypass policy.

Rules are evaluated in order; the first match wins. Unknown actions are blocked by default (fail-closed).

### Human Approval

High-impact actions require explicit human approval before execution.

### Execution

Executes only actions that have passed the policy and approval gates.

## Safety Principle

The core design principle is:

**The LLM proposes. Deterministic policy controls. A human approves consequential actions.**

The system therefore does not allow an LLM response such as:

```
"Block this account immediately."
```

to directly execute an account-blocking operation.

Instead:

```
LLM disposition
      ↓
Policy Engine
      ↓
Human Approval
      ↓
Execution
```

## Project Structure

```
sentinel-fraud-agent/
│
├── policy/               # Deterministic policy rules
│   ├── __init__.py
│   ├── models.py         # Policy data structures
│   ├── rules.py          # Individual policy rules
│   └── engine.py         # Policy evaluation engine
│
├── api/                  # REST API layer
│   ├── __init__.py
│   ├── models.py         # API request/response models
│   ├── routes.py         # API endpoints
│   └── queue_api.py      # FastAPI application
│
├── cli/                  # Command-line interface
│   ├── __init__.py
│   ├── client.py         # HTTP client
│   ├── commands.py       # CLI commands
│   └── __main__.py       # Entry point
│
├── sentinel_app.py       # Core fraud triage service
├── main.py              # CLI entry point
│
├── tests/
│   ├── test_policy.py    # Policy engine tests
│   ├── test_api.py       # API endpoint tests
│   ├── test_cli.py       # CLI client tests
│   └── test_triage.py    # Integration tests
│
├── docs/
│   ├── architecture.md   # This file
│   ├── api.md            # API documentation
│   └── technical-decisions.md
│
└── data/                 # Data files
    ├── sentinel.db       # Main database
    └── sentinel_queue.db # Queue state database
```

## Execution Flow

### Investigation Submission

1. Client submits account via API or CLI
2. API validates request
3. Investigation is queued
4. API returns 202 Accepted with job ID

### Investigation Processing

1. Worker picks up job from queue
2. LangGraph case graph begins execution
3. Supervisor routes to appropriate specialists
4. Specialists gather and analyze data
5. Disposition combines findings
6. Policy engine evaluates proposed action

### Policy Decision Points

**BLOCK**: Action not permitted, skip execution

**ALLOW**: Action permitted, proceed to execution

**REQUIRE_APPROVAL**: Action permitted but requires human approval

### Human Approval Boundary

If policy requires approval:

1. Investigation pauses (stored in checkpointer)
2. Human reviews evidence
3. Human approves or rejects
4. LangGraph thread resumes from same point
5. Action executes (if approved) or skips (if rejected)

## Why Policies Need to Be Outside the LLM

Don't do this:

```python
LLM:
"If confidence > 80%, execute."
```

Instead:

```
LLM
 │ proposed disposition
 ▼
Policy Engine
 │
 ├── Is action permitted?
 ├── Is human approval required?
 ├── Is confidence sufficient?
 ├── Is action allowed for this verdict?
 └── Are there account restrictions?
```

The LLM can propose:

```json
{
  "verdict": "fraud",
  "confidence": "high",
  "proposed_action": "block_account"
}
```

But the policy engine determines whether `block_account` is actually allowed.

## Fail-Closed Policy

If an action does not have an explicit policy rule, Sentinel blocks it.

This is intentional. Unknown actions should never automatically become permitted actions.

## Limitations

The asynchronous queue in this project is an in-process queue backed by SQLite metadata. It is suitable for demonstration and development.

A production deployment would replace the in-process queue with a distributed message broker (Redis, RabbitMQ, SQS, Kafka) depending on operational requirements.

The policy architecture would remain the same.
