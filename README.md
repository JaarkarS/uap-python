# UAP Python v0.1 — working prototype

A **proposed** fault-tolerant agent-task protocol, not an MCP or A2A implementation. Includes FastAPI server, SQLite durable task ledger, HTTP client SDK, resumable Python worker, and tests.

## Quickstart (Python 3.10+)

```bash
cd uap-python
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export UAP_API_KEY=replace-with-a-secret  # Windows PowerShell: $env:UAP_API_KEY='replace-with-a-secret'
uvicorn uap.api:app --host 127.0.0.1 --port 8000
```

Open a **second terminal** (same environment and directory):

```bash
export UAP_API_KEY=replace-with-a-secret
python -m uap.worker --worker-id worker-a --delay 0.1
```

Submit a task from a **third terminal**:

```bash
export UAP_API_KEY=replace-with-a-secret
python -c "import os; from uap.client import UAPClient; c=UAPClient(api_key=os.environ['UAP_API_KEY']); print(c.submit('range.sum', {'start':0,'end':10000}))"
```

Observe the worker printing `checkpoint` progress. Kill worker A with Ctrl+C halfway through. Wait for the 10-second lease to expire. Start another worker (`--worker-id worker-b`) and see it resume from the checkpoint. Query task status using:

```bash
python -c "import os; from uap.client import UAPClient; c=UAPClient(api_key=os.environ['UAP_API_KEY']); print(c.get('PASTE_TASK_ID'))"
```

Run tests (stdlib unittest):

```bash
python -m unittest discover -s tests -v
```

## v0.1 protocol operations

- `POST /uap/v1/tasks` — submit `{capability, payload, max_attempts}`
- `GET /uap/v1/tasks/{id}` — inspect state, checkpoint and result
- `POST /uap/v1/claim` — atomically lease queued or expired task
- `POST /uap/v1/tasks/{id}/heartbeat` — extend owned lease
- `POST /uap/v1/tasks/{id}/checkpoint` — persist checkpoint and extend lease
- `POST /uap/v1/tasks/{id}/complete` — complete owned leased task
- `POST /uap/v1/tasks/{id}/fail` — requeue or fail owned leased task
- `GET /health` — health indicator

All `/uap/v1` operations require `Authorization: Bearer <UAP_API_KEY>`. The lease token returned by `claim` must be provided on subsequent mutations. Old/expired tokens receive 409 Conflict.

## Correctness and limitations

- Atomic claims use SQLite `BEGIN IMMEDIATE` to prevent simultaneous claims on the same SQLite database file.
- Leases and checkpoint writes are guarded by the current lease token (fencing of ledger writes). A checkpoint only saves **application-defined** state. Work is **at least once**, not exactly once.
- **Do not use non-idempotent side effects in tasks** without stronger fencing, idempotency, or transactional outbox semantics. A crashed agent may have applied external effects before its checkpoint was saved.
- API key is a **demo shared secret**, not per-agent identity/authorization. Default key is insecure. Never expose this server publicly or put secrets in Git.
- For production: PostgreSQL, durable queue, structured task schema registry, TLS + OAuth/mTLS, true per-agent ACLs, rate limits, metrics, retry backoff, cancellations, idempotency keys, observability, protocol conformance tests and trace propagation.
- One SQLite database stored on one host; not intended for shared network filesystem or multi-region coordination.
- While the worker is running a long blocking step that exceeds its lease, another agent may claim the same job. Keep steps shorter than the lease or add a heartbeat thread.

## Suggested next version

UAP v0.2 should introduce capability discovery, versioned JSON schemas, task idempotency keys, optional SSE events, OpenTelemetry trace context and reusable handler registration (`@uap.tool(...)`).
