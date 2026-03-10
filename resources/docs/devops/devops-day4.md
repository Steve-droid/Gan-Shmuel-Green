# DevOps Day 4

## Context

`devops-test` and `devops-e2e` are already merged into `devops`. The CI service is running on EC2 with emails silenced. Waiting for `billing` and `weight` to merge into `main`.

---

## Plan: from the moment `billing` and `weight` merge into `main`

---

### Steve

#### Step 1 — Create back-merge branch

```bash
git checkout devops
git pull origin devops
git checkout -b devops-backmerge
git merge origin/main
```

#### Step 2 — Resolve conflicts

Likely conflict files: `billing/app.py`, `weight/app.py` (stubs vs real implementations).

**Always accept the billing/weight team's version** — their real implementation replaces our stubs.

```bash
git checkout --theirs billing/app.py
git checkout --theirs weight/app.py
git add billing/app.py weight/app.py
git commit
```

Also check `docker-compose.yml` and `docker-compose.test.yml` for conflicts — resolve manually if needed.

#### Step 3 — Check `.env`

Consolidate all environment variables from billing and weight into one `.env` at repo root. Check what variables they use in their compose files and add any missing ones:

```
MYSQL_ROOT_PASSWORD=root
WEIGHT_SERVICE_URL=http://weight:5000
# add any billing/weight specific vars here
```

This file is gitignored — set it manually, don't commit it.

#### Step 3b — Fix known issues before testing

---

**Fix 1: EC2 spurious local branches**

**Reason:** Git has local branches literally named `origin/billing`, `origin/devops`, etc. at `refs/heads/origin/*`. These conflict with the remote-tracking refs at `refs/remotes/origin/*`. When the pipeline runs `git reset --hard origin/devops`, Git sees two matching refs and picks the wrong one (the old local branch), causing the reset to land on a stale commit instead of the latest remote.

**Fix:**
```bash
sudo git branch -d origin/bill-feature origin/devops-branch-filter origin/devops-hotfix-mailing origin/devops-monitor
```

**How to diagnose in future:** `sudo git show-ref | grep <branch-name>` — if you see both `refs/heads/origin/X` and `refs/remotes/origin/X`, the local one is the spurious one. Delete it.

---

**Fix 2: Weight tests — `from app import app` import error**

**Reason:** All weight tests do `from app import app`. This is a Python import — Python searches `sys.path` for a file called `app.py`. When pytest runs from `/repo`, `sys.path` contains `/repo` but not `/repo/weight/`, so Python looks for `/repo/app.py` which doesn't exist. Every test fails with `ImportError` before even running.

**What is `sys.path`:** A Python list of directory paths that Python searches when resolving imports. It's populated at startup from the current directory, environment variables, and installed packages.

**What is `conftest.py`:** A special file recognized exclusively by pytest. pytest automatically discovers and loads every `conftest.py` it finds while walking the directory tree toward the test files — you never import it manually. Common uses: define shared fixtures, manipulate the environment before tests run.

**What is a fixture:** A function decorated with `@pytest.fixture` that pytest runs automatically before a test to set up what the test needs. Instead of repeating setup code in every test, you define it once as a fixture and pytest injects it into any test function that declares it as a parameter. The `yield` keyword splits setup (before) from teardown (after the test).

**Fix:** Create a new file `weight/conftest.py` (at `weight/` root, NOT inside `weight/tests/`) — do not move or modify `weight/tests/conftest.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
```

**Breaking down `sys.path.insert(0, os.path.dirname(__file__))`:**
- `__file__` — built-in Python variable holding the current file's path, e.g. `/repo/weight/conftest.py`
- `os.path.dirname(__file__)` — strips the filename, returns just the directory: `/repo/weight`
- `sys.path.insert(0, ...)` — inserts that directory at position `0` (the front of the list), so Python checks `weight/` first before anything else

pytest loads `weight/conftest.py` before `weight/tests/conftest.py`, so the path is fixed before any test tries to import `app`.

---

**Fix 3: Weight tests — `test_e2e.py` and `test_db_functions_day2.py` use `localhost`**

**Reason:** `test_e2e.py` hits `http://localhost:5000` and `test_db_functions_day2.py` connects directly to a `localhost` DB. Neither address is reachable from inside the CI container — the weight service runs in a separate container, not on localhost from the CI's perspective.

**Fix:** Exclude them from the CI test run with `--ignore` flags in `ci/app.py` Step 4a:

```bash
python -m pytest billing/tests/ weight/tests/ -v \
  --ignore=weight/tests/test_e2e.py \
  --ignore=weight/tests/test_db_functions_day2.py
```

---

**Fix 4: Billing tests — same `from app import app` issue (flag to Einav)**

**Reason:** Same as Fix 2. When billing merges, `billing/tests/` will likely have tests that do `from app import app`. The CI runs `pytest billing/tests/` from `/repo`, so the same `ImportError` applies.

**Fix:** Einav needs to add `billing/conftest.py` at `billing/` root with the same two lines as Fix 2.

---

#### Step 4 — Test locally

```bash
docker compose -f docker-compose.test.yml -p gan-shmuel-test up -d --build
sleep 10
python -m pytest billing/tests/ weight/tests/ -v   # unit + integration tests
python -m pytest tests/ -v                          # health + e2e tests
docker compose -f docker-compose.test.yml -p gan-shmuel-test down
```

Fix any failures before proceeding.

#### Step 5 — PR `devops-backmerge` → `devops`

Open PR, get reviewed, merge.

#### Step 6 — Re-enable emails

Create branch `devops-reenable-emails` off `devops`. Uncomment the two `send_email` calls in `ci/app.py` that were silenced in the hotfix. Commit, PR, merge to `devops`.

#### Step 7 — PR `devops` → `main`

Open PR, get reviewed, merge.

#### Step 8 — Deploy to EC2

```bash
# SSH to EC2
cd ~/Gan-Shmuel-Green
sudo git fetch origin
sudo git reset --hard refs/remotes/origin/main
~/restart-ci.sh
sudo chown -R ubuntu:ubuntu ~/Gan-Shmuel-Green
```

#### Step 9 — Verify end-to-end on EC2

Push a test commit to `weight` or `billing` and confirm:
- Pipeline runs successfully
- Prod deploy happens (if pushing to `main`)
- Email sent on success

---

### Sami

#### While Steve does Steps 1-4

Start the **rollback bonus feature** on a new branch:

```bash
git checkout devops
git pull origin devops
git checkout -b devops-rollback
```

Design: implement a `/rollback` endpoint in `ci/app.py` that redeploys the last known good production state.

#### After Steve opens PR in Step 5

**Review** Steve's `devops-backmerge` → `devops` PR.

#### After Step 7

**Review** Steve's `devops` → `main` PR.

---

## Bonus: Rollback

- Branch: `devops-rollback`
- Owner: Sami (with Steve reviewing)
- Approach: git-based (checkout last good SHA, rebuild, redeploy)

### Trigger: automatic on prod deploy failure

After every prod deploy, run a health check on billing and weight prod ports. If health check fails → automatically roll back. A manual `POST /rollback` endpoint also exists as a fallback for cases where health checks pass but a human decides to roll back.

### Flow

```
prod deploy runs
    ↓
health check: GET /health on billing (8081) and weight (8080)
    ↓ pass                          ↓ fail
save current SHA               checkout .last_good_sha
to .last_good_sha              rebuild + redeploy
    ↓                               ↓
email: deploy success          email: deploy failed, rolled back to <sha>
```

### Implementation notes

- On every **successful** prod deploy: write current SHA to `/repo/.last_good_sha`
- On health check failure: read `/repo/.last_good_sha`, checkout that SHA, rebuild, redeploy
- `POST /rollback` endpoint: same logic as automatic rollback, triggered manually
- `.last_good_sha` is a plain text file in the repo dir on EC2, not committed to git
