# Day 3 — DevOps

## Daily Goals

**Overall goal:** Full E2E + Basic Sanity

### DevOps Team tasks
- Manage testing for dev teams
- End-to-end test automation
- BONUS: Rollback functionality

---

## Task split: Steve and Sami

| Task | Owner |
|---|---|
| Update test runner in pipeline to run all test files | Steve |
| Create `tests/test_weight.py` — weight API integration tests | Sami |
| Create `tests/test_billing.py` — billing API integration tests | Sami |
| Create `tests/test_e2e.py` — full integration flow | Steve |
| Deploy updated pipeline to EC2 | Steve |
| BONUS: Rollback functionality | Steve |

**Why this split:**
- Sami writes the integration tests for weight and billing separately — each file focuses on one service and its HTTP endpoints, which is a manageable scope
- Steve handles the pipeline changes and E2E test (requires understanding of how billing + weight interact as a full system)
- Both should coordinate with the other teams early on Day 3 to get the API contracts before writing tests

---

## Background: Types of tests in this project

There are two kinds of tests in this pipeline:

### Unit tests (written by billing and weight teams)
- Location: `billing/tests/`, `weight/tests/`
- Written by: each team, for their own service
- What they test: internal logic — functions, DB queries, calculations
- Do they need a running server? No — they test code directly
- Do they need the DB? Possibly — depends on whether the team mocked the DB or not

### Integration tests (written by DevOps team)
- Location: `tests/` (repo root)
- Written by: DevOps
- What they test: the running services via HTTP — send real requests and assert responses
- Do they need a running server? Yes — the test containers must be up

### Why run both in the pipeline?
Unit tests catch logic errors fast. Integration tests catch deployment and wiring errors. Running both gives full coverage.

---

## Updated pipeline flow (Day 3)

```
Step 1: git update (fetch + checkout + reset)
Step 2: Build images (docker compose build)
Step 3: Deploy test environment (docker-compose.test.yml up)
Step 4a: Sleep(5) — wait for services to boot
Step 4b: Run unit tests (billing/tests/, weight/tests/) — DB is available
Step 4c: Run integration tests (tests/) — services are running
Step 5: Cleanup test environment
Step 6: (main only) Deploy to production
```

Unit tests run after the test environment is up (not before) because the billing/weight teams may make real DB calls in their tests. Since the DB containers are part of the test environment, running everything after Step 3 is the safest approach.

---

## Task 1: Manage testing for dev teams

### Subtask 1a: Restructure the test runner in the pipeline (Steve)

Currently `run_pipeline()` runs a single file:
```python
result = subprocess.run(['python', f'{REPO_DIR}/tests/test_health.py'], ...)
```

This needs to be replaced with two sequential pytest calls — one for unit tests, one for integration tests.

**Changes needed in `ci/app.py`:**

```python
# Step 4b: Run unit tests (billing + weight)
result = subprocess.run(
    ['python', '-m', 'pytest', 'billing/tests/', 'weight/tests/', '-v'],
    cwd=REPO_DIR, capture_output=True, text=True
)
logging.info(f"Unit tests: {result.stdout.strip()}")
if result.returncode != 0:
    logging.error(f"Unit tests failed: {result.stderr.strip()}")
    send_email(f"[FAIL] Pipeline failed on {branch}", f"Unit tests failed:\n{result.stdout.strip()}", recipients)
    cleanup_test_env()
    return

# Step 4c: Run integration tests (DevOps)
result = subprocess.run(
    ['python', '-m', 'pytest', 'tests/', '-v'],
    cwd=REPO_DIR, capture_output=True, text=True
)
logging.info(f"Integration tests: {result.stdout.strip()}")
if result.returncode != 0:
    logging.error(f"Integration tests failed: {result.stderr.strip()}")
    send_email(f"[FAIL] Pipeline failed on {branch}", f"Integration tests failed:\n{result.stdout.strip()}", recipients)
    cleanup_test_env()
    return
```

**Changes needed in `ci/requirements.txt`:**
- Add `pytest`

### Subtask 1b: Create `tests/test_weight.py` (Sami)

Integration tests for the weight service. These run against the test container at `host.docker.internal:8082`.

Endpoints to test (from `api-spec-for-all-teams.md`):
- `GET /health` — returns 200 OK
- `POST /weight` — records a truck weighing, returns session id + bruto
- `GET /weight` — returns list of weighings
- `GET /item/<id>` — returns item details (tara, sessions)
- `GET /session/<id>` — returns session details
- `GET /unknown` — returns list of containers with unknown tara
- `POST /batch-weight` — uploads container tara weights from file

### Subtask 1c: Create `tests/test_billing.py` (Sami)

Integration tests for the billing service. These run against the test container at `host.docker.internal:8083`.

Endpoints to test (from `api-spec-for-all-teams.md`):
- `GET /health` — returns 200 OK
- `POST /provider` — creates a provider, returns `{"id": <str>}`
- `PUT /provider/<id>` — updates provider name
- `POST /truck` — registers a truck under a provider
- `PUT /truck/<id>` — updates truck's provider
- `GET /truck/<id>` — returns truck details (tara, sessions)
- `POST /rates` — uploads rates from excel file
- `GET /rates` — downloads current rates file
- `GET /bill/<id>` — returns invoice for a provider (requires provider + truck + rates + weight sessions to exist first)

---

## Task 2: End-to-end test automation

### What this means

E2E tests verify the full system works together as a whole — not just individual services. The critical flow for this project is:

```
1. Register a provider (billing)
2. Register a truck under that provider (billing)
3. Upload rates (billing)
4. Truck arrives at factory → POST /weight direction=in (weight)
5. Truck leaves → POST /weight direction=out (weight)
6. Request invoice → GET /bill/<provider_id> (billing)
7. Assert invoice reflects the correct weight and pay
```

This test crosses the boundary between weight and billing — it only passes if both services are running correctly AND the data flows correctly between them.

### Subtask 2a: Create `tests/test_e2e.py` (Steve)

General structure:
```python
WEIGHT_URL = "http://host.docker.internal:8082"
BILLING_URL = "http://host.docker.internal:8083"

def test_full_weighing_and_billing_flow():
    # Setup: create provider, truck, upload rates
    provider_id = ...  # POST /provider
    # POST /truck with provider_id
    # POST /rates with rates file

    # Weight flow
    r = requests.post(f"{WEIGHT_URL}/weight", data={
        "direction": "in", "truck": "<license>", "weight": 10000,
        "unit": "kg", "force": "false", "produce": "orange", "containers": ""
    })
    assert r.status_code == 200
    session_id = r.json()["id"]

    r = requests.post(f"{WEIGHT_URL}/weight", data={
        "direction": "out", "truck": "<license>", "weight": 3000,
        "unit": "kg", "force": "false", "produce": "na", "containers": ""
    })
    assert r.status_code == 200
    assert r.json()["neto"] == 7000

    # Billing flow
    r = requests.get(f"{BILLING_URL}/bill/{provider_id}")
    assert r.status_code == 200
    bill = r.json()
    assert bill["sessionCount"] >= 1
    assert bill["total"] > 0
```

**Note:** The exact request format depends on the final implementation from each team. Verify with billing and weight before writing this.

### Subtask 2b: Update `docker-compose.test.yml` if needed (Steve)

Both services are already on the same Docker network (same compose file = same default network), so they can reach each other by service name internally. No changes likely needed, but verify once the real services replace the stubs.

**Owner: Steve**

---

## Task 3 (BONUS): Rollback functionality (Steve)

### What this means

If a production deploy breaks the live system, the pipeline should be able to automatically revert to the last known good version.

### Approach: image tagging

Before each production deploy, tag the current production images with the git commit SHA. If the deploy fails, redeploy the previous tagged images.

```python
# Before prod deploy — save current image as backup
# docker tag gan-shmuel-billing:latest gan-shmuel-billing:<previous-sha>

# If prod deploy fails — roll back
# docker compose -p gan-shmuel up -d --no-deps billing weight
# using the previous tagged images
```

This is a bonus task — implement only if time allows after the required tasks are done.

---

## Coordination checklist for Day 3

Before writing tests, DevOps needs from each team:

**From weight team:**
- Confirmation that `billing/tests/` and `weight/tests/` directories exist with pytest-compatible test files
- Any test data setup required before weighing can be recorded (e.g. do containers need to be pre-registered?)

**From billing team:**
- Confirmation that `billing/tests/` exists with pytest-compatible test files
- What data must exist before `GET /bill/<id>` returns a valid result (provider, truck, rates, weight sessions)

The API contracts are already documented in `resources/docs/api-spec-for-all-teams.md`.
The earlier this is confirmed, the earlier tests can be written.
