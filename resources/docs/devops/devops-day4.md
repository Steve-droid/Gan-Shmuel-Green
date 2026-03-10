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
