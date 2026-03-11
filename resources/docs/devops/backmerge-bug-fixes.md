# Back-Merge Bug Fixes

This document lists all bugs discovered and fixed by the DevOps team during the back-merge of `main` into `devops`. Shared with all teams for transparency.

---

## Fix 1: `docker-compose.yml` — billing port typo

**File:** `docker-compose.yml`

**Problem:** Billing port mapping was `8081:5051` — a typo. The right side of a Docker port mapping (`host:container`) is the port the app listens on inside the container. Billing listens on `5001`, so `5051` meant every request to billing on port 8081 reached nothing inside the container.

**Fix:**
```yaml
ports:
  - "8081:5001"
```

---

## Fix 2: `docker-compose.yml` — missing `WEIGHT_SERVICE_URL` for billing in production

**File:** `docker-compose.yml`, billing service environment block

**Problem:** Billing's `GET /bill/<id>` endpoint calls the weight service internally to fetch truck session data. Without `WEIGHT_SERVICE_URL` set as an environment variable, billing falls back to hardcoded defaults (`http://weight-service:5000`, `http://weight-app:5000`) which don't match the actual service name. Docker's internal DNS resolves containers by their service name as defined in the compose file — the correct name is `weight`.

**Fix:** Added to billing's environment block in `docker-compose.yml`:
```yaml
- WEIGHT_SERVICE_URL=http://weight:5000
```

Note: `docker-compose.test.yml` already had this set correctly.

---

## Fix 3: `billing/conftest.py` — missing `sys.path` fix

**File:** `billing/conftest.py`

**Problem:** The CI pipeline runs `pytest billing/tests/` from the repo root (`/repo`). The billing conftest immediately does `from app import create_app`, but Python's module search path (`sys.path`) only contains `/repo` at that point — not `/repo/billing/`. Python can't find `billing`'s `app` package and every billing test fails with `ImportError` before running.

**Background — what is `sys.path`:** Python maintains a list of directories to search when resolving imports. When pytest runs from `/repo`, only `/repo` is in that list. `billing/app/` is at `/repo/billing/app/`, which Python won't find unless `/repo/billing/` is explicitly added.

**Fix:** Added these two lines at the very top of `billing/conftest.py`, before any existing imports:
```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
```

`os.path.dirname(__file__)` resolves to `/repo/billing/` — inserting it at position 0 ensures Python finds billing's `app` package first.

---

## Fix 4: `weight/conftest.py` — created new file for `sys.path` fix

**File:** `weight/conftest.py` (new file at `weight/` root)

**Problem:** Same issue as Fix 3 but for weight. All weight tests do `from app import app`. When pytest runs `pytest weight/tests/` from `/repo`, Python can't find `weight/app.py` because `/repo/weight/` is not in `sys.path`.

**Fix:** Created `weight/conftest.py` with:
```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
```

**Important:** This is a separate file from `weight/tests/conftest.py` which handles DB setup. The two files have different responsibilities and must not be merged.

---

## Fix 5: `ci/app.py` — split pytest into two separate calls to avoid name collision

**File:** `ci/app.py`, Step 4a

**Problem:** Running `pytest billing/tests/ weight/tests/` in a single command caused a name collision. Billing uses an `app/` directory (a Python package with `__init__.py`). Weight has a single `app.py` file. Both are named `app`. When both `billing/` and `weight/` are in `sys.path` simultaneously, weight tests doing `from app import app` found `billing/app/` instead of `weight/app.py` and failed with `ImportError: cannot import name 'app' from 'app'`.

**Background — Python packages vs modules:**
- A **module** is a single `.py` file: `weight/app.py` → `import app`
- A **package** is a directory containing `__init__.py`: `billing/app/` → also `import app`

When both directories are in `sys.path`, Python picks whichever comes first. Running both test suites in one process means both directories are in `sys.path` at the same time, causing the collision.

**Fix:** Split into two separate subprocess calls — each runs in its own Python process with its own isolated `sys.path`:

```python
# billing tests
subprocess.run(['python', '-m', 'pytest', 'billing/tests/', '-v'], ...)

# weight tests
subprocess.run(['python', '-m', 'pytest', 'weight/tests/', '-v',
                '--ignore=weight/tests/test_e2e.py',
                '--ignore=weight/tests/test_db_functions_day2.py'], ...)
```

---

## Fix 6: `ci/app.py` — exclude weight's localhost-only tests from CI

**File:** `ci/app.py`, weight pytest call

**Problem:** `weight/tests/test_e2e.py` hits `http://localhost:5000` and `weight/tests/test_db_functions_day2.py` connects directly to `localhost:3307`. From inside the CI container, `localhost` refers to the CI container itself — not the weight service container, which runs on a separate Docker network. These tests are designed for the weight team's local development environment only.

**Fix:** Added `--ignore` flags to exclude them from the CI run:
```
--ignore=weight/tests/test_e2e.py
--ignore=weight/tests/test_db_functions_day2.py
```

The full end-to-end flow is covered by `tests/test_e2e.py` which correctly uses `host.docker.internal` to reach the test containers.

---

## Fix 7: `tests/test_billing.py` — duplicate import block and wrong service URLs

**File:** `tests/test_billing.py`

**Problem:** The file contained two separate test blocks concatenated together — a second `import pytest` statement appeared partway through the file. Both blocks also used wrong service URL defaults (`http://billing-app:5000`, `http://billing-service:5000`) — neither matches the service name in `docker-compose.test.yml` (`billing`) or the correct port (`5001`).

**Fix:** Removed the duplicate block, set a single correct URL:
```python
BILLING_URL = os.getenv("BILLING_URL", "http://billing:5001")
```

---

## Fix 8: `tests/test_weight.py` — wrong service URL default

**File:** `tests/test_weight.py`

**Problem:** Default URL was `http://weight-app:5000` — service name `weight-app` doesn't exist in `docker-compose.test.yml`. The correct service name is `weight`.

**Fix:**
```python
WEIGHT_URL = os.getenv("WEIGHT_SERVICE_URL", "http://weight:5000")
```

---

## Fix 9: `weight/conftest.py` — `DB_HOST` not set before module import

**File:** `weight/conftest.py`

**Problem:** `weight/db.py` reads `DB_HOST` at module level using `os.environ['DB_HOST']` — dictionary-style access that raises `KeyError` if the variable is not set, crashing immediately during import. This happens before any test runs.

**Background — `os.environ` vs `.env` files:** `os.environ` is Python's interface to the process's environment variables (set in the shell or via Docker's `environment:` block). It does NOT automatically read `.env` files — those require an explicit `load_dotenv()` call. `os.environ['KEY']` crashes with `KeyError` if the key is missing; `os.environ.get('KEY', 'default')` is the safe alternative. Since `weight/db.py` uses the unsafe form at module level, the variable must be set before the import happens.

**Why `weight/tests/conftest.py` doesn't fix it:** `weight/tests/conftest.py` sets `DB_PORT` and `DB_NAME` but not `DB_HOST`. Even if it did, the ordering matters — pytest loads conftest files before test files, but `weight/conftest.py` (at `weight/` root) loads before `weight/tests/conftest.py`. Setting `DB_HOST` in the root conftest ensures it is available before any import.

**Fix:** Add `DB_HOST` default to `weight/conftest.py` before the sys.path line:
```python
import sys, os
os.environ.setdefault("DB_HOST", "localhost")
sys.path.insert(0, os.path.dirname(__file__))
```

`os.environ.setdefault` only sets the variable if it isn't already set — so if Docker passes a real `DB_HOST`, it won't be overwritten.

---

## Fix 10: `ci/app.py` — exclude `billing/tests/test_integration.py` from CI

**File:** `ci/app.py`, billing pytest call

**Problem:** `billing/tests/test_integration.py` requires a real MySQL connection to `127.0.0.1:3308`. This works in billing's local dev environment where they run their own DB container. In CI, the `billing-db` container is on the test Docker network (`docker-compose.test.yml`) — a network the CI container is not part of. From inside the CI container, `127.0.0.1:3308` is unreachable (connection refused).

**Background — why the CI container can't reach the test DB:** The CI container runs on the default Docker network (from `docker-compose.yml`). The test containers (including `billing-db`) run on a separate network created by `docker-compose.test.yml`. Docker networks are isolated — containers on one network cannot reach containers on another unless explicitly connected. The CI container reaches test services only via `host.docker.internal` (going through the host machine), not via service names or localhost.

**Fix:** Add `--ignore` flag to the billing pytest call in `ci/app.py`:
```python
['python', '-m', 'pytest', 'billing/tests/', '-v',
 '--ignore=billing/tests/test_integration.py'],
```
