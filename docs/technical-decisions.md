# Sentinel Technical Decisions

## Why LangGraph?

The investigation contains multiple stages and may pause for human approval.

LangGraph provides:

- Explicit stateful workflow orchestration
- Support for interrupt/resume semantics
- Checkpointing for persistent graph state
- Clean node/edge abstractions

Alternative: Direct Python state machine would require more custom scaffolding.

---

## Why Isolated Specialist Agents?

Fraud investigation contains different analytical domains:

- **Behaviour**: Transaction patterns and account activity
- **Context**: Customer history and account restrictions
- **Network**: Relationships and connected entities

Separating these:

- Reduces the responsibility of each agent
- Makes testing easier
- Improves auditability
- Allows domain experts to review specialist logic independently

Alternative: Single monolithic agent would be harder to reason about.

---

## Why a Routing Supervisor?

The supervisor is responsible for routing. It decides which specialist should be invoked rather than performing all investigation itself.

This means:

- Supervisor logic is minimal
- Specialists have clear responsibilities
- Easy to add new specialists

Alternative: Direct calls to specialists would couple the caller to specialist details.

---

## Why Deterministic Policies?

Fraud controls are consequential.

LLM reasoning is probabilistic:

- The model might hallucinate a high-confidence score
- The model might misinterpret policy requirements
- The model's output can vary between runs

Therefore, policy enforcement must be deterministic:

- Implemented in Python with explicit rules
- Evaluated independently of LLM reasoning
- Auditable and reproducible

Alternative: Embedding policy in LLM prompts would be implicit and hard to audit.

---

## Why a Separate Execution Layer?

The model should not directly execute consequential operations.

Execution occurs only after:

1. Disposit proposed by supervisor
2. Policy engine evaluates
3. Human approves (if required)

This three-layer approach ensures:

- Clear separation of concerns
- Explicit approval gates
- Auditability

Alternative: Allowing the LLM to directly execute would be unsafe.

---

## Why Asynchronous Processing?

Investigations may take longer than a normal HTTP request (30s timeout):

- Multiple model calls
- Database queries
- Human approval wait times

The queue allows:

- API to return immediately with job ID (202 Accepted)
- Caller to poll status independently
- Long-running investigations to complete in background

Alternative: Synchronous REST would block the API and timeout on long operations.

---

## Why SQLite?

SQLite keeps the demonstration self-contained and easy to run locally:

- No external dependencies
- Single file database
- No installation required
- Cross-platform

The architecture can later move to PostgreSQL and a distributed queue (Redis, RabbitMQ, SQS, Kafka) without changing the core investigation workflow.

Alternative: PostgreSQL + message broker would be harder to setup for a demo.

---

## Why Policy is Separate from LLM

The LLM should not make decisions about whether its own proposals are allowed.

Example of what NOT to do:

```python
# BAD: LLM decides whether to execute its own proposal
if confidence > 80:
    execute()
```

Example of what TO do:

```python
# GOOD: LLM proposes, policy decides
disposition = llm.propose()

policy_result = policy_engine.evaluate(disposition)

if policy_result.decision == "ALLOW":
    execute()
elif policy_result.decision == "REQUIRE_APPROVAL":
    request_human_approval()
else:
    skip()
```

---

## Why Fail-Closed Policy

If an action does not have an explicit policy rule, Sentinel blocks it.

This is intentional:

```python
# If we introduce a new action:
freeze_card

# But forget to define a policy for it, we must NOT say:
"Unknown action → probably okay."

# We must say:
"Unknown action → blocked."
```

This is a standard safety property for consequential systems.

---

## Why CLI Talks to API

The CLI could directly instantiate the FraudTriageService:

```python
# WRONG: Direct instantiation
service = FraudTriageService()
service.triage_account("A00985")
```

Instead, the CLI talks to the API:

```python
# RIGHT: Via HTTP
client = SentinelAPIClient()
client.submit_investigation("A00985")
```

Benefits:

- CLI and API use the same code path
- API behavior can be verified via CLI
- Prevents CLI and API from diverging over time
- Makes CLI a real client of the system

---

## Why Policy + Approval Are Different

Don't confuse:

- **Policy**: Is this action permitted?
- **Approval**: Has an authorized human explicitly approved this permitted action?

Policy asks:

```
Is action permitted?
```

Approval asks:

```
Has an authorized human explicitly approved this permitted action?
```

Therefore:

```
LLM proposal
     │
     ▼
Policy
     │
     ├── BLOCK
     │
     └── REQUIRE_APPROVAL
                │
                ▼
             Human
                │
          ┌─────┴─────┐
          ▼           ▼
       APPROVE      REJECT
          │           │
          ▼           ▼
        Execute      Skip
```

---

## Why Async Queue Instead of Direct Execution

Could we just call the LangGraph directly?

```python
# WRONG: Blocking the API
result = graph.invoke(state)
return result  # 30 seconds later
```

Or use async/await?

```python
# BETTER: Non-blocking but still coupled
result = await graph.invoke(state)
return result
```

Or queue?

```python
# BEST: Truly decoupled
job = queue.submit(account_id)
return {"job_id": job.id, "status": "queued"}
# Queue processes in background
# Caller polls status independently
```

The queue approach provides:

- Immediate API response (202 Accepted)
- Independent processing
- Resilience to long-running tasks
- Easy to scale with multiple workers

---

## Future Extensions

Without changing the core architecture, we can:

1. **Replace SQLite with PostgreSQL**: Change database connector
2. **Replace in-process queue with Redis**: Change queue implementation
3. **Add LangSmith tracing**: Add to graph nodes
4. **Add structured logging**: Wrap nodes with telemetry
5. **Add approval audit trail**: Persist approval decisions
6. **Add metrics/monitoring**: Add prometheus endpoints
7. **Add authentication**: Add JWT to API routes
8. **Add rate limiting**: Add to FastAPI middleware

The architecture stays the same.

---

## Summary

The key decisions are:

1. **Specialist isolation**: Clear responsibilities
2. **Routing supervisor**: Minimal orchestration
3. **Deterministic policy**: Auditable controls
4. **Separate execution**: Three-layer safety
5. **Asynchronous queue**: Resilient to long tasks
6. **SQLite for demo**: Easy setup, replaceable later
7. **Policy separate from LLM**: Safety boundary
8. **Fail-closed policy**: Unknown = blocked
9. **CLI talks to API**: Consistent behavior
10. **Policy != Approval**: Different concerns

These decisions work together to create a safe, auditable, and extensible fraud investigation system.
