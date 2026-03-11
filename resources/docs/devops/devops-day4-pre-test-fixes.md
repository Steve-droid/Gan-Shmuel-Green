# Pre-Test Fixes — devops-backmerge

All fixes below should be committed directly to `devops-backmerge`. No separate branches needed — these are integration fixes discovered during the back-merge scan, not new features.

---

## Steve's Fixes

---

### Fix 1: `docker-compose.yml` — billing port typo

**File:** `docker-compose.yml`

**Problem:** Billing port mapping is `8081:5051` — a typo from an earlier fix. Billing app listens on `5001`, so the container port (right side) must be `5001`. With `5051`, every request to billing on port 8081 hits nothing inside the container.

**Fix:**
```yaml
ports:
  - "8081:5001"
```

---

### Fix 2: `docker-compose.yml` — missing `WEIGHT_SERVICE_URL` for billing in prod

**File:** `docker-compose.yml`, billing service `environment` block

**Problem:** Billing's `GET /bill/<id>` calls the weight service internally to get truck session data. Without `WEIGHT_SERVICE_URL` set, the billing code falls back to hardcoded defaults (`http://weight-service:5000`, `http://weight-app:5000`) which don't match the service name in the compose network. Docker's internal DNS resolves service names — the correct one is `weight`.

**Fix:** Add to billing's environment block:
```yaml
- WEIGHT_SERVICE_URL=http://weight:5000
```

---

### Fix 3: `billing/conftest.py` — missing `sys.path` fix

**File:** `billing/conftest.py` (billing team's file, at `billing/` root)

**Problem:** The first line of `billing/conftest.py` is `from app import create_app`. When pytest runs `pytest billing/tests/` from `/repo`, `billing/` is not in `sys.path`, so Python can't find `billing/app.py` and the entire billing test suite fails with `ImportError` before any test runs.

**Why this is different from weight:** Billing uses an application factory pattern — `create_app()` — rather than a module-level `app = Flask(...)`. But the import problem is the same: Python needs `billing/` in `sys.path` to find `app.py`.

**Fix:** Add these two lines at the very top of `billing/conftest.py`, before any existing imports:
```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
```

**Why at the top:** Python executes imports in order. If `from app import create_app` runs before `billing/` is in `sys.path`, it fails. The `sys.path` fix must come first.

---

### Fix 4: `ci/app.py` — exclude localhost-only weight tests from CI run

**File:** `ci/app.py`, Step 4a pytest command

**Problem:** `weight/tests/test_e2e.py` hits `http://localhost:5000` and `weight/tests/test_db_functions_day2.py` connects to a `localhost` DB on port `3307`. Neither address is reachable from inside the CI container — the weight service is in a separate container. These tests are designed for the weight team's local dev environment, not for CI.

**Fix:** Add `--ignore` flags to the Step 4a pytest command in `run_pipeline()`:
```python
result = subprocess.run(
    ['python', '-m', 'pytest', 'billing/tests/', 'weight/tests/', '-v',
     '--ignore=weight/tests/test_e2e.py',
     '--ignore=weight/tests/test_db_functions_day2.py'],
    cwd=REPO_DIR, capture_output=True, text=True
)
```

---

## Sami's Fixes

---

### Fix 5: `tests/test_billing.py` — duplicate import block + wrong service URL

**File:** `tests/test_billing.py`

**Problem:** The file contains two separate test blocks concatenated into one — there is a second `import pytest` statement in the middle of the file. This causes a syntax/structure issue and means the second `BILLING_URL` definition overwrites the first. Additionally, both defaults are wrong:
- First block: `http://billing-app:5000` — wrong service name, wrong port
- Second block: `http://billing-service:5000` — wrong service name, wrong port

The correct service name (from `docker-compose.test.yml`) is `billing` and the correct port is `5001`.

**Fix:** The file needs to be rewritten as a single clean test file. Remove the duplicate `import` block that appears partway through. Set a single `BILLING_URL`:
```python
BILLING_URL = os.getenv("BILLING_URL", "http://billing:5001")
```

Also verify the endpoint names against billing's actual API before running:
- Is it `POST /trucks` or `POST /truck`?
- Is the payload field `provider_id` or `provider`?
Check `billing/app.py` or billing's README to confirm.

---

### Fix 6: `tests/test_weight.py` — wrong service URL default

**File:** `tests/test_weight.py`, line 7

**Problem:** `WEIGHT_URL = os.getenv("WEIGHT_SERVICE_URL", "http://weight-app:5000")` — the default service name `weight-app` doesn't match the service name in `docker-compose.test.yml`, which is `weight`. If `WEIGHT_SERVICE_URL` is not set as an environment variable, the test will try to connect to a non-existent hostname and fail immediately.

**Fix:**
```python
WEIGHT_URL = os.getenv("WEIGHT_SERVICE_URL", "http://weight:5000")
```

---

## Commit after all fixes

Once all fixes above are applied and staged:

```bash
git add docker-compose.yml ci/app.py billing/conftest.py tests/test_billing.py tests/test_weight.py
git commit -m "pre-test fixes: port typo, service URLs, sys.path, pytest ignores"
git push origin devops-backmerge
```

---

## Run tests

After all fixes are committed:

```bash
docker compose -f docker-compose.test.yml -p gan-shmuel-test up -d --build
sleep 15
python -m pytest billing/tests/ weight/tests/ -v \
  --ignore=weight/tests/test_e2e.py \
  --ignore=weight/tests/test_db_functions_day2.py
python -m pytest tests/ -v
docker compose -f docker-compose.test.yml -p gan-shmuel-test down
```

Fix any remaining failures before opening the PR.
