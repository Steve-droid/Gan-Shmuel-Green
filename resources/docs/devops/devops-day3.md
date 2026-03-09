# Day 3 — DevOps

## Daily Goals

**Overall goal:** Full E2E + Basic Sanity

### DevOps Team tasks
- Manage testing for dev teams
- End-to-end test automation
- BONUS: Rollback functionality

---

## Task split: Steve and Sami

| Task | Owner | Branch |
|---|---|---|
| Update test runner in pipeline to run all test files | Steve | `devops-test-runner` → `devops-test` |
| Create `tests/test_weight.py` — weight API integration tests | Sami | `devops-test-weight` → `devops-test` |
| Create `tests/test_billing.py` — billing API integration tests | Sami | `devops-test-billing` → `devops-test` |
| Create `tests/test_e2e.py` — full integration flow | Steve | `devops-e2e-test` → `devops-e2e` |
| Deploy updated pipeline to EC2 | Steve | — (after merging `devops-test` + `devops-e2e` to `devops`) |
| BONUS: Rollback functionality | Steve | `devops-rollback` → `devops` |

**Branch hierarchy:**
```
devops
├── devops-test              ← parent for all test runner + integration test work
│   ├── devops-test-runner   ← subtask 1a (Steve)
│   ├── devops-test-weight   ← subtask 1b (Sami)
│   └── devops-test-billing  ← subtask 1c (Sami)
├── devops-e2e               ← parent for E2E work
│   └── devops-e2e-test      ← subtask 2a (Steve)
└── devops-rollback          ← bonus (Steve)
```

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
Step 3: Deploy test environment (docker-compose.test.yml up + sleep(5))
Step 4: Run tests
         → 4a: Unit tests (billing/tests/, weight/tests/)
         → 4b: Integration tests (tests/)
Step 5: Cleanup test environment
Step 6: (main only) Deploy to production
```

`sleep(5)` is part of step 3 — it waits for services to finish booting before tests can run. It is not a test step.

Unit tests run after the test environment is up because the billing/weight teams may make real DB calls in their tests. Since the DB containers are part of the test environment, running everything after step 3 is the safest approach.

---

## Task 1: Manage testing for dev teams

### Subtask 1a: Restructure the test runner in the pipeline (Steve) — `devops-test-runner`

Currently `run_pipeline()` runs a single file:
```python
result = subprocess.run(['python', f'{REPO_DIR}/tests/test_health.py'], ...)
```

This needs to be replaced with two sequential pytest calls — one for unit tests, one for integration tests.

**Changes needed in `ci/app.py`:**

```python
# Step 4: Run tests
# Step 4a: Unit tests (billing + weight)
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

# Step 4b: Integration tests (DevOps)
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

### Subtask 1b: Create `tests/test_weight.py` (Sami) — `devops-test-weight`

Integration tests for the weight service. These run against the test container at `host.docker.internal:8082`.

Endpoints to test (from `api-spec-for-all-teams.md`):
- `GET /health` — returns 200 OK
- `POST /weight` — records a truck weighing, returns session id + bruto
- `GET /weight` — returns list of weighings
- `GET /item/<id>` — returns item details (tara, sessions)
- `GET /session/<id>` — returns session details
- `GET /unknown` — returns list of containers with unknown tara
- `POST /batch-weight` — uploads container tara weights from file

### Subtask 1c: Create `tests/test_billing.py` (Sami) — `devops-test-billing`

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

### Subtask 2a: Create `tests/test_e2e.py` (Steve) — `devops-e2e-test`

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

### Subtask 2b: Update `docker-compose.test.yml` (Steve)

Both services are already on the same Docker network — no networking changes needed.

However, the volume mounts for `/in` must be added.

**What is `/in`?**

The billing and weight services expect certain files to be placed on their filesystem before specific endpoints can work:
- `POST /rates` (billing) — reads a rates Excel file from `/in/<filename>` inside the billing container
- `POST /batch-weight` (weight) — reads a container tara CSV/JSON file from `/in/<filename>` inside the weight container

Neither endpoint accepts the file content directly in the HTTP request. You send just the filename (e.g. `{"file": "rates.xlsx"}`), and the service opens that file from its own `/in` folder.

**Why the volume mount?**

By default `/in` doesn't exist inside the containers. The volume mount maps a directory from the host into the container at `/in`, so the files are available without any manual copying:

```yaml
services:
  billing:
    volumes:
      - ./resources/sample_files/sample_uploads:/in

  weight:
    volumes:
      - ./resources/sample_files/sample_uploads:/in
```

`./resources/sample_files/sample_uploads` already contains the files needed:
- `rates.xlsx` — for `POST /rates` on billing
- `containers1.csv` — for `POST /batch-weight` on weight

This is required for the E2E test: `POST /rates` must succeed before `GET /bill/<id>` can return `total > 0`.

---

## Task 3 (BONUS): Rollback functionality (Steve) — `devops-rollback`

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

## DB schemas and sample files

### Weight DB (`resources/db_schemas/multi-db/weightdb.sql`)

Two tables:
- `containers_registered` (`container_id` varchar(15), `weight` int, `unit` varchar(10))
- `transactions` (`id` int auto_increment, `datetime`, `direction`, `truck` varchar(50), `containers`, `bruto` int, `truckTara` int, `neto` int, `produce` varchar(50))

Relevant for tests:
- `truckTara` and `neto` are only populated for direction=out — direction=in response will not contain them
- `neto` is NULL (not the string "na") in the DB when containers have unknown tara — the API translates this to "na" in the JSON response
- Container IDs are varchar(15) — test container IDs must stay within that limit

### Billing DB (`resources/db_schemas/multi-db/billingdb.sql`)

Three tables:
- `Provider` (`id` int auto_increment, `name` varchar(255))
- `Rates` (`product_id` varchar(50), `rate` int, `scope` varchar(50))
- `Trucks` (`id` varchar(10), `provider_id` int)

**Critical:** `Trucks.id` is varchar(10). Any truck license plate used in tests must be ≤ 10 characters. `"TEST-TRUCK-456"` (14 chars) will fail with a DB error. Use `"TST-456"` or similar.

### Sample upload files (`resources/sample_files/sample_uploads/`)

| File | Format | Use |
|---|---|---|
| `containers1.csv` | `"id","kg"` — IDs like `C-35434` | `POST /batch-weight` on weight service |
| `containers2.csv` | `"id","lbs"` — IDs like `K-8263` | `POST /batch-weight` on weight service |
| `trucks.json` | `[{"id":"T-XXXXX","weight":NNN,"unit":"lbs"}]` | `POST /batch-weight` on weight service |
| `rates.xlsx` | Excel — columns: Product, Rate, Scope | `POST /rates` on billing service |

`POST /batch-weight` and `POST /rates` both require the file to be in the `/in` folder inside the respective container. To enable these tests without manual steps, add a volume mount to `docker-compose.test.yml`:

```yaml
services:
  weight:
    volumes:
      - ./resources/sample_files/sample_uploads:/in
  billing:
    volumes:
      - ./resources/sample_files/sample_uploads:/in
```

Then in tests:
- `POST /batch-weight` with body `{"file": "containers1.csv"}`
- `POST /rates` with body `{"file": "rates.xlsx"}`

This also unblocks the E2E test — `POST /rates` must succeed before `GET /bill/<id>` can return `total > 0`.

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
