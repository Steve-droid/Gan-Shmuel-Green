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
| Create `tests/test_weight.py` — weight API tests | Sami |
| Create `tests/test_billing.py` — billing API tests | Sami |
| Create `tests/test_e2e.py` — full integration flow | Steve |
| Deploy updated pipeline to EC2 | Steve |
| BONUS: Rollback functionality | Steve |

**Why this split:**
- Sami writes the individual service tests — these are self-contained and a good way to get familiar with the codebase and the APIs
- Steve handles the pipeline changes and E2E test (requires understanding of the full system and how billing + weight interact)
- Both should coordinate with the other teams early on Day 3 to understand the API contracts before writing tests

---

## Task 1: Manage testing for dev teams

### What this means

By Day 3, billing and weight have real API implementations (not stubs). DevOps is responsible for:
1. Writing tests that cover those APIs in the test environment
2. Making sure the pipeline runs those tests automatically on every push
3. Being the point of contact if tests fail and another team doesn't understand why

Currently `tests/test_health.py` only checks `GET /health`. Day 3 requires expanding this to test actual functionality.

### Subtask 1a: Restructure the test runner in the pipeline

Currently `run_pipeline()` runs a single file:
```python
result = subprocess.run(['python', f'{REPO_DIR}/tests/test_health.py'], ...)
```

This needs to change so the pipeline runs all test files in the `tests/` directory. The simplest approach is to use `pytest` — it discovers and runs all `test_*.py` files automatically.

**Changes needed:**
- Add `pytest` to `ci/requirements.txt`
- Update the pipeline command from `python test_health.py` to `pytest tests/`
- Rename `test_health.py` tests to use pytest-style assertions (or keep them as-is — pytest runs plain `sys.exit` scripts too, but proper pytest style is cleaner)

**Owner: Steve**

### Subtask 1b: Create `tests/test_weight.py`

Tests for the weight team's APIs. Coordinate with the weight team to understand what endpoints exist and what valid requests/responses look like.

Endpoints to test (based on Day 2 requirements):
- `GET /weight` — returns list of weighings
- `POST /weight` — records a truck weighing
- `GET /item/<id>` — returns item details
- `GET /session/<id>` — returns session details
- `POST /batch-weight` — uploads container weights from file

The tests hit the test environment ports (`host.docker.internal:8082`).

**Owner: Sami**

### Subtask 1c: Create `tests/test_billing.py`

Tests for the billing team's APIs. Coordinate with the billing team.

Endpoints to test (based on Day 2 requirements):
- `POST /provider` — create a provider
- `PUT /provider/<id>` — update a provider
- `POST /truck` — register a truck
- `PUT /truck/<id>` — update a truck
- `GET /truck/<id>` — get truck details
- `POST /rates` — upload rates
- `GET /rates` — get current rates

The tests hit the test environment ports (`host.docker.internal:8083`).

**Owner: Sami**

---

## Task 2: End-to-end test automation

### What this means

E2E tests verify the full system works together as a whole — not just individual services. The critical flow for this project is:

```
1. A truck arrives at the factory → POST /weight (truck in)
2. The truck leaves → POST /weight (truck out)
3. Billing generates an invoice → GET /bill/<provider>
4. The invoice reflects the correct weight data from step 1-2
```

This test crosses the boundary between weight and billing — it only passes if both services are running correctly AND they can communicate with each other.

### Subtask 2a: Create `tests/test_e2e.py`

The E2E test script. The exact content depends on the final API contracts from billing and weight — coordinate with both teams before writing this.

General structure:
```python
# 1. Record truck weighing (via weight service on port 8082)
# 2. Record truck exit weight
# 3. Request invoice from billing (via billing service on port 8083)
# 4. Assert invoice contains correct data
```

**Note:** E2E tests require both services to be running and connected. In the test environment, billing and weight are on the same Docker network (`gan-shmuel-test_default`) so they can reach each other by service name.

**Owner: Steve**

### Subtask 2b: Update `docker-compose.test.yml` if needed

If the E2E test requires billing to call weight internally, both services need to be on the same network — which they already are (same compose file = same default network). No changes may be needed, but verify once the real services replace the stubs.

**Owner: Steve**

---

## Task 3 (BONUS): Rollback functionality

### What this means

If a production deploy breaks the live system, the pipeline should be able to automatically revert to the last known good version. Without rollback, a bad deploy means manual intervention to fix production.

### Approach: image tagging

Before each production deploy, tag the current production images with the git commit SHA. If the deploy fails, redeploy the previous tagged images.

```python
# Before prod deploy — tag current images as backup
# docker tag gan-shmuel-billing:latest gan-shmuel-billing:<previous-sha>

# If prod deploy fails — roll back
# docker compose -p gan-shmuel up -d --no-deps billing weight
# using the previous tagged images
```

This is a bonus task — implement only if time allows after the required tasks are done.

**Owner: Steve**

---

## Coordination checklist for Day 3

Before writing tests, DevOps needs from each team:

**From weight team:**
- Final list of API endpoints and their expected request/response format
- Any test data setup required (e.g. do containers need to be registered before a weighing can be recorded?)

**From billing team:**
- Final list of API endpoints and their expected request/response format
- What data needs to exist before `GET /bill` can be called (providers, trucks, rates)

The earlier this information is collected, the earlier the tests can be written.
