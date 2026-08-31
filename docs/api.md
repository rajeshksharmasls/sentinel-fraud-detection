# Sentinel API Documentation

## Base URL

```
http://127.0.0.1:8000/api/v1
```

## Endpoints

### Health

**GET /health**

Health check endpoint.

Example:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Response:

```json
{
  "status": "ok"
}
```

---

### Submit Investigation

**POST /investigations**

Submit a fraud investigation.

Request:

```json
{
  "account_id": "A00985"
}
```

Response (202 Accepted):

```json
{
  "job_id": "abc123",
  "account_id": "A00985",
  "status": "queued",
  "graph_thread_id": "investigation-abc123"
}
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{"account_id":"A00985"}'
```

---

### Investigation Status

**GET /investigations/{job_id}**

Get investigation status.

Response:

```json
{
  "job_id": "abc123",
  "account_id": "A00985",
  "status": "completed",
  "graph_thread_id": "investigation-abc123",
  "result": {...},
  "error": null
}
```

Possible statuses:

- `queued`: Investigation accepted, waiting to be processed
- `running`: Investigation in progress
- `waiting_approval`: Requires human approval
- `completed`: Investigation finished
- `failed`: Investigation encountered an error

Example:

```bash
curl http://127.0.0.1:8000/api/v1/investigations/abc123
```

---

### Approval

**POST /investigations/{job_id}/approval**

Approve or reject an investigation action.

Request (approve):

```json
{
  "approved": true,
  "reason": "Reviewed evidence."
}
```

Request (reject):

```json
{
  "approved": false,
  "reason": "Need additional evidence."
}
```

Response:

```json
{
  "job_id": "abc123",
  "approved": true,
  "reason": "Reviewed evidence.",
  "status": "completed",
  "result": {...}
}
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/investigations/abc123/approval \
  -H "Content-Type: application/json" \
  -d '{"approved":true,"reason":"Reviewed evidence"}'
```

---

### Policies

**GET /policies**

List configured policy rules.

Response:

```json
{
  "rules": [
    "rule_investigation_always_allowed",
    "rule_customer_locked",
    "rule_insufficient_evidence",
    "rule_fraud_requires_confidence",
    "rule_irreversible_actions_require_approval"
  ]
}
```

Example:

```bash
curl http://127.0.0.1:8000/api/v1/policies
```

---

## HTTP Status Codes

| Situation                 | Status                    | Response                               |
| ------------------------- | ------------------------- | -------------------------------------- |
| Valid submission          | 202 Accepted              | Investigation submitted                |
| Invalid request           | 400 Bad Request           | Error details                          |
| Job not found             | 404 Not Found             | Investigation not found                |
| Job not awaiting approval | 409 Conflict              | Investigation not waiting for approval |
| Unexpected error          | 500 Internal Server Error | Error details                          |

---

## Examples

### Complete Flow

1. Submit investigation:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{"account_id":"A00985"}'
```

Response:

```json
{
  "job_id": "b6f3c8f2",
  "account_id": "A00985",
  "status": "queued",
  "graph_thread_id": "investigation-b6f3c8f2"
}
```

2. Poll status:

```bash
curl http://127.0.0.1:8000/api/v1/investigations/b6f3c8f2
```

Response (when waiting_approval):

```json
{
  "job_id": "b6f3c8f2",
  "account_id": "A00985",
  "status": "waiting_approval",
  "graph_thread_id": "investigation-b6f3c8f2"
}
```

3. Approve:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/investigations/b6f3c8f2/approval \
  -H "Content-Type: application/json" \
  -d '{"approved":true,"reason":"Reviewed fraud evidence"}'
```

Response:

```json
{
  "job_id": "b6f3c8f2",
  "approved": true,
  "reason": "Reviewed fraud evidence",
  "status": "completed",
  "result": {...}
}
```

---

## Swagger UI

Interactive API explorer available at:

```
http://127.0.0.1:8000/docs
```

---

## Important Notes

1. **Asynchronous Processing**: The API returns 202 Accepted immediately. The investigation continues in the background.

2. **Job IDs**: Keep the job ID returned by the submit endpoint. Use it to poll status and request approval/rejection.

3. **Policy Enforcement**: All actions are subject to deterministic policy evaluation before execution. The LLM cannot bypass policy.

4. **Human Approval Required**: Consequential actions (account blocking, case closure) require explicit human approval via the approval endpoint.

5. **Idempotency**: The approval/rejection endpoints are not idempotent. Sending the same request twice will process twice.
