# Day 2 — DevOps

## Daily Goals

**Overall goal:** Weight APIs complete, Billing domain management

### DevOps Team tasks
- Test environment setup
- Mailing system
- BONUS: Monitor

---

# Test Environment Setup

## What is a stub?

A stub is a fake, minimal implementation of a service that has the same *interface* (same API endpoints, same response format) as the real thing, but none of the real business logic. It just returns hardcoded responses.

For example, a stub for the weight service:
```python
@app.route('/health')
def health():
    return 'OK', 200
```

No database, no real weighing logic. The point is that anything depending on the weight service (the pipeline, test scripts, billing) can be built and tested against the stub — and when the real weight service is ready, you just swap it in. Nothing else changes.

---

## Port architecture on EC2

The EC2 server runs multiple Docker containers simultaneously, each bound to a different port on the host:

```
EC2 Host (3.108.241.170)
├── ci container        → host port 8085
├── weight container    → host port 8080  (production)
├── billing container   → host port 8081  (production)
├── weight-test         → host port 8082  (test)
└── billing-test        → host port 8083  (test)
```

Who is the client depends on context:
- **Developer testing manually:** their laptop is the client, EC2 is the server → `http://3.108.241.170:8080/weight`
- **Test script in the pipeline:** runs on EC2 itself → `http://localhost:8082/health`
- **Billing calling Weight internally:** uses Docker's internal network via service name → `http://weight:8080/weight` — never touches host ports at all

---

## The `-f` flag in `docker compose`

`-f` stands for `--file`. It tells Docker Compose to use a specific compose file instead of the default `docker-compose.yml`:

```bash
docker compose up -d --build                             # reads docker-compose.yml
docker compose -f docker-compose.test.yml up -d --build  # reads docker-compose.test.yml
```

Without `-f`, Compose always looks for `docker-compose.yml` in the current directory.

---

## Subtasks

1. ✅ **Create billing stub** — `billing/app.py`, `billing/Dockerfile`, `billing/requirements.txt` with just `GET /health`
2. ✅ **Create weight stub** — `weight/app.py`, `weight/Dockerfile`, `weight/requirements.txt` with just `GET /health`
3. ✅ **Update `docker-compose.yml`** — add billing (8081), weight (8080), billing-db, weight-db production services
4. ✅ **Create `docker-compose.test.yml`** — test environment with billing (8083), weight (8082), billing-db, weight-db on separate containers
5. ✅ **Create `.env` file** — DB credentials, never committed to the repo
6. ✅ **Create test script** — `tests/test_health.py` using `requests` to hit `/health` on each test service and assert `200 OK`
7. ✅ **Update `run_pipeline()` in `app.py`** — add test deploy → run tests → prod deploy flow (with sleep, branch check, project name fix)
8. ✅ **Test locally** — full pipeline verified end-to-end on local machine
9. ✅ **Add test container cleanup** — tear down test containers after tests complete
10. ✅ **Mailing system** — send email on pipeline success/failure

---

## Subtask 3: Updating `docker-compose.yml`

### Why

`docker-compose.yml` is the single source of truth for how all services are built and run. Currently it only defines the `ci` service. Without entries for `billing` and `weight`:
- `docker compose build` won't know those services exist
- `docker compose up -d --no-deps billing weight` in the pipeline will fail with "no such service"
- Docker won't know which `Dockerfile` to use, which ports to expose, or how to start them

### The updated `docker-compose.yml`

```yaml
services:
  ci:
    build: ./ci
    ports:
      - "8085:8085"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - .:/repo
    environment:
      - REPO_DIR=/repo
    restart: unless-stopped

  billing:
    build: ./billing
    ports:
      - "8081:8081"
    restart: unless-stopped

  weight:
    build: ./weight
    ports:
      - "8080:8080"
    restart: unless-stopped
```

### Line by line

**`build: ./billing`** — tells Docker Compose where to find the `Dockerfile` for this service. `./billing` is a path relative to `docker-compose.yml`, pointing to the `billing/` directory.

**`ports: "8081:8081"`** — maps port 8081 on the EC2 host to port 8081 inside the billing container (`HOST:CONTAINER`). This is how external traffic (curl, browsers, the test script) reaches the service.

**`restart: unless-stopped`** — automatically restarts the container if it crashes, unless manually stopped.

**No volumes, no environment variables** — unlike `ci`, billing and weight don't need access to the Docker socket or the repo. They are self-contained Flask apps.

---

## Subtask 3b: Adding databases to `docker-compose.yml` and `docker-compose.test.yml`

### Why we need the schema files

The official MySQL Docker image has a built-in feature: any `.sql` file mounted into `/docker-entrypoint-initdb.d/` inside the container is automatically executed on first startup. This is how the database gets its tables created without any manual SQL commands.

Without mounting the schemas, the MySQL container starts with an empty server — no databases, no tables. The weight and billing services would connect and immediately fail.

The schema files are already in the repo:
- `resources/db_schemas/multi-db/weightdb.sql` — creates the `weight` database with `containers_registered` and `transactions` tables
- `resources/db_schemas/multi-db/billingdb.sql` — creates the `billdb` database with `Provider`, `Rates`, and `Trucks` tables

### Why now (before real services exist)

DevOps's job is to have infrastructure ready so other teams are not blocked. The weight and billing teams will need databases the moment they start replacing the stubs with real code. Setting up the DB containers now means they never have to wait.

### What changes

**`.env` file (new, at repo root):**
```
MYSQL_ROOT_PASSWORD=your_password_here
```
MySQL requires a root password. It cannot be hardcoded in the compose file. `.env` is already gitignored so it is safe.

**Updated `docker-compose.yml`:**
```yaml
services:
  ci:
    build: ./ci
    ports:
      - "8085:8085"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - .:/repo
    environment:
      - REPO_DIR=/repo
    restart: unless-stopped

  billing:
    build: ./billing
    ports:
      - "8081:8081"
    environment:
      - DB_HOST=billing-db
      - DB_PASSWORD=${MYSQL_ROOT_PASSWORD}
    depends_on:
      - billing-db
    restart: unless-stopped

  billing-db:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
    volumes:
      - ./resources/db_schemas/multi-db/billingdb.sql:/docker-entrypoint-initdb.d/billingdb.sql
    restart: unless-stopped

  weight:
    build: ./weight
    ports:
      - "8080:8080"
    environment:
      - DB_HOST=weight-db
      - DB_PASSWORD=${MYSQL_ROOT_PASSWORD}
    depends_on:
      - weight-db
    restart: unless-stopped

  weight-db:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
    volumes:
      - ./resources/db_schemas/multi-db/weightdb.sql:/docker-entrypoint-initdb.d/weightdb.sql
    restart: unless-stopped
```

**Updated `docker-compose.test.yml`:**
```yaml
services:
  billing:
    build: ./billing
    ports:
      - "8083:8081"
    environment:
      - DB_HOST=billing-db
      - DB_PASSWORD=${MYSQL_ROOT_PASSWORD}
    depends_on:
      - billing-db
    restart: unless-stopped

  billing-db:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
    volumes:
      - ./resources/db_schemas/multi-db/billingdb.sql:/docker-entrypoint-initdb.d/billingdb.sql
    restart: unless-stopped

  weight:
    build: ./weight
    ports:
      - "8082:8080"
    environment:
      - DB_HOST=weight-db
      - DB_PASSWORD=${MYSQL_ROOT_PASSWORD}
    depends_on:
      - weight-db
    restart: unless-stopped

  weight-db:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
    volumes:
      - ./resources/db_schemas/multi-db/weightdb.sql:/docker-entrypoint-initdb.d/weightdb.sql
    restart: unless-stopped
```

### Key concepts

**`image: mysql:8.0`** — instead of `build:`, this pulls a pre-built official MySQL image from Docker Hub. No Dockerfile needed.

**`${MYSQL_ROOT_PASSWORD}`** — Docker Compose automatically reads `.env` from the repo root and substitutes `${VAR}` placeholders. The password is never written in the file itself.

**`depends_on`** — tells Compose to start the DB container before the app container. Without this, the app might try to connect to the DB before MySQL is ready.

**`DB_HOST` and `DB_PASSWORD`** — environment variables passed to the app containers so their code knows where to find the database. `DB_HOST=billing-db` works because Docker's internal network resolves service names as hostnames.

**No host port for DB containers** — DB containers have no `ports:` mapping. They are only reachable internally via Docker's network. There is no reason to expose MySQL to the outside world.

### Q&A: Environment variables

**Which environment variables does each container need?**

There are two completely separate sets of environment variables going to two different containers:

- **MySQL containers** need `MYSQL_ROOT_PASSWORD` — the official MySQL Docker image reads this on first startup and uses it to set the root password. Without it, MySQL refuses to start.
- **App containers** (billing, weight) need `DB_HOST` and `DB_PASSWORD` — so their Python code knows where to find the database and how to authenticate with it.

These are separate concerns. MySQL doesn't know or care about `DB_HOST`. The app doesn't know or care about `MYSQL_ROOT_PASSWORD`.

**How are environment variables "sent" to a container?**

When Docker starts a container, it injects the `environment:` values from the compose file directly into that container's process environment — the same mechanism as shell environment variables. Inside the Python app, you read them with:

```python
import os
db_host = os.environ.get('DB_HOST')
db_password = os.environ.get('DB_PASSWORD')
```

Writing `environment: - DB_HOST=billing-db` in `docker-compose.yml` doesn't execute any code — it just makes that value available inside the container at runtime. The app code has to actively read and use it.

**Why do we need port mappings?**

Without a `ports:` mapping, a container is only reachable from within Docker's internal network — other containers in the same project can talk to it by service name, but nothing outside Docker can reach it. A port mapping punches a hole from the EC2 host into the container:

```
External world → EC2 host port → container port
```

The billing and weight services need to be reachable from outside Docker — by developers testing manually with `curl`, by the test script, and eventually by the billing team calling the weight API. The DB containers have no port mapping because they only need to be reachable by the app containers on Docker's internal network, never from outside.

**Why are the port mappings different between `docker-compose.yml` and `docker-compose.test.yml`?**

Both prod and test containers run simultaneously on the same EC2 host. A host port can only be bound by one process at a time — two containers cannot both claim port 8081 on the host. So we give them different host ports:

```
Prod:  billing → 8081:8081  (host 8081 → container 8081)
Test:  billing → 8083:8081  (host 8083 → container 8081)
```

The container port (`8081`) never changes — that is what Flask listens on inside the container, configured in `app.py`. Only the host port differs, because that is what must be unique on the EC2 machine.

**Why do we need `depends_on`?**

Without it, Docker Compose may start the billing app container at the same time as `billing-db`. The app boots in seconds, MySQL takes longer to initialize — if the app tries to connect before MySQL is ready, the connection fails.

`depends_on: - billing-db` tells Compose: "don't start `billing` until `billing-db` container has started."

One important nuance: `depends_on` only waits for the container to **start**, not for MySQL to be fully **ready** to accept connections. MySQL can take a few seconds after the container starts to finish initializing. For a production system you would add a healthcheck to wait for MySQL to be truly ready. For this project, `depends_on` is sufficient.

---

## Subtask 4: Creating `docker-compose.test.yml`

### Why

`docker-compose.yml` defines the production environment. We can't deploy untested code directly to production — we need a separate, isolated environment to run tests against first. If tests fail, production is never touched.

`docker-compose.test.yml` defines that test environment: the same services, same Dockerfiles, but on different host ports so test and production containers can run simultaneously on EC2 without conflicting.

### The `docker-compose.test.yml`

```yaml
services:
  billing:
    build: ./billing
    ports:
      - "8083:8081"
    restart: unless-stopped

  weight:
    build: ./weight
    ports:
      - "8082:8080"
    restart: unless-stopped
```

### Line by line

**Same `build:` paths** — the test environment builds from the exact same Dockerfiles as production. There is no separate "test code" — the difference is purely in how they are deployed.

**`ports: "8083:8081"`** — `HOST:CONTAINER`. The container port (`8081`) stays the same — that is what Flask listens on inside the container and it does not change. Only the host port changes (`8083` instead of `8081`) so the test container does not collide with the production container on the EC2 host. Same logic for weight: `"8082:8080"`.

**No CI service** — the CI service manages itself separately and is never part of the test environment.

**No databases** — added later when real services replace the stubs.

### The `-p` flag

When running with `-f docker-compose.test.yml`, Docker Compose still derives the project name from the directory name — same as production. That means container names would collide (`gan-shmuel-green-billing-1` for both). The fix is to pass a different project name with `-p`:

```bash
docker compose -p gan-shmuel-test -f docker-compose.test.yml up -d --build
```

This creates containers named `gan-shmuel-test-billing-1` and `gan-shmuel-test-weight-1` — completely separate from the production ones.

---

## The CI/CD loop

```
Push to GitHub
      ↓
Webhook fires → POST /trigger
      ↓
git fetch + checkout + reset --hard
      ↓
docker compose build (builds new images)
      ↓
Deploy to TEST environment
      ↓
Run tests against test environment
      ↓
    Pass? ──── No ───→ Stop (+ notify via email later)
      │
     Yes
      ↓
Deploy to PRODUCTION
      ↓
Pipeline finished successfully
```

The test environment acts as a safety gate. Production only ever receives code that has already passed tests. This is the core idea behind CI/CD — automate the quality check so humans don't have to remember to do it manually before every deploy.

---

## Subtask 6: Creating the test script

### Why

The test script is the gate in the CI/CD loop. Without it, the pipeline has no way to know whether the deployed code actually works — it would build and deploy blindly with no safety check before production. The script hits `/health` on each test service, checks for `200 OK`, and exits with a non-zero code if anything fails. `subprocess.run` captures that exit code — the pipeline sees `result.returncode != 0` and stops before touching production.

### `tests/test_health.py`

```python
import requests
import sys

SERVICES = {
    'billing': 'http://host.docker.internal:8083/health',
    'weight': 'http://host.docker.internal:8082/health',
}

def run_tests():
    failed = False
    for name, url in SERVICES.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"[PASS] {name} /health returned 200")
            else:
                print(f"[FAIL] {name} /health returned {response.status_code}")
                failed = True
        except Exception as e:
            print(f"[FAIL] {name} /health raised exception: {e}")
            failed = True

    if failed:
        sys.exit(1)
    print("All tests passed")
    sys.exit(0)

if __name__ == '__main__':
    run_tests()
```

### Why `host.docker.internal` and not `localhost`

The test script runs as a subprocess of the pipeline, which runs inside the CI container. Inside a container, `localhost` refers to the container itself — not the EC2 host. The test containers (billing port 8083, weight port 8082) are bound to the host's ports, not the CI container's.

`host.docker.internal` is a special DNS name that resolves to the EC2 host from inside a container. So `http://host.docker.internal:8083/health` correctly reaches the test billing container via the host port mapping.

On Linux this requires adding one line to the CI service in `docker-compose.yml`:

```yaml
ci:
  build: ./ci
  ports:
    - "8085:8085"
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - .:/repo
  environment:
    - REPO_DIR=/repo
  extra_hosts:
    - "host.docker.internal:host-gateway"
  restart: unless-stopped
```

`host-gateway` is a special Docker keyword that resolves to the host's gateway IP automatically — no hardcoding needed.

### Why `sys.exit(1)` on failure

This is how the pipeline knows tests failed. `subprocess.run` captures the exit code in `result.returncode`. A non-zero code triggers the pipeline's error handling and stops before production is deployed.

### Adding `requests` to `ci/requirements.txt`

The test script runs inside the CI container, which currently only has Flask. `requests` must be added:

```
Flask==3.0.3
requests==2.32.3
```

### What is the `requests` package?

`requests` is a Python library for making HTTP requests. Python has a built-in module for this (`urllib`) but it is verbose and low-level. `requests` makes the same thing simple:

```python
# urllib (built-in, verbose)
import urllib.request
response = urllib.request.urlopen('http://host.docker.internal:8083/health')
status = response.status

# requests (clean)
import requests
response = requests.get('http://host.docker.internal:8083/health', timeout=5)
status = response.status_code
```

We need it in the test script to call `/health` on each test service. Since the script runs inside the CI container, `requests` must be installed there — hence adding it to `ci/requirements.txt`.

### What is `extra_hosts` and why is the value `host.docker.internal:host-gateway`?

Every Linux machine has a file called `/etc/hosts` — a simple text file that maps hostnames to IP addresses. It is checked before DNS, so entries there take priority. `extra_hosts` in Docker Compose injects entries into that file inside the container.

`"host.docker.internal:host-gateway"` means: add this line to the container's `/etc/hosts`:
```
<host gateway IP>    host.docker.internal
```

`host-gateway` is a special Docker keyword that automatically resolves to the EC2 host's IP as seen from inside the container (usually something like `172.18.0.1`). Docker fills it in at runtime — no hardcoding needed.

The result: when the test script inside the CI container connects to `host.docker.internal:8083`, the container looks up `host.docker.internal` in `/etc/hosts`, finds the host's IP, and reaches the test billing container through the host port mapping.

**Why is this needed only on Linux?** On Docker Desktop (Mac/Windows), `host.docker.internal` is built in and works automatically. On Linux (our EC2 server), it does not exist by default — `extra_hosts` manually adds it.

### Summary of changes for this subtask

- Create `tests/test_health.py`
- Add `requests==2.32.3` to `ci/requirements.txt`
- Add `extra_hosts` to the CI service in `docker-compose.yml`

---

## Subtask 7: Updating `run_pipeline()` in `app.py`

### The updated function

```python
def run_pipeline(branch):
    # Step 1: Update repo
    git_commands = [
        ['git', 'fetch', 'origin', branch],
        ['git', 'checkout', branch],
        ['git', 'reset', '--hard', f'origin/{branch}'],
    ]
    for cmd in git_commands:
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        logging.info(f"{' '.join(cmd)}: {result.stdout.strip()}")
        if result.returncode != 0:
            logging.error(f"Failed: {result.stderr.strip()}")
            return

    # Step 2: Build images
    result = subprocess.run(
        ['docker', 'compose', 'build'],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    logging.info(f"docker compose build: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Build failed: {result.stderr.strip()}")
        return

    # Step 3: Deploy to test environment
    result = subprocess.run(
        ['docker', 'compose', '-p', 'gan-shmuel-test', '-f', 'docker-compose.test.yml', 'up', '-d', '--build'],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    logging.info(f"Test deploy: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Test deploy failed: {result.stderr.strip()}")
        return

    time.sleep(5)  # Wait for containers to finish booting

    # Step 4: Run tests
    result = subprocess.run(
        ['python', f'{REPO_DIR}/tests/test_health.py'],
        capture_output=True, text=True
    )
    logging.info(f"Tests: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Tests failed: {result.stderr.strip()}")
        return

    # Step 5: Deploy to production (only from main)
    if branch != 'main':
        logging.info(f"Branch '{branch}' is not 'main' - skipping production deploy")
        logging.info("Pipeline finished successfully")
        return

    result = subprocess.run(
        ['docker', 'compose', '-p', 'gan-shmuel', 'up', '-d', '--no-deps', 'billing', 'weight'],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    logging.info(f"Production deploy: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Production deploy failed: {result.stderr.strip()}")
        return

    logging.info("Pipeline finished successfully")
```

### What changed and why

**Structure changed from a loop to explicit steps.** The original flat list worked when every command had the same logic (run it, fail if non-zero). Now we have conditional logic — run tests, and only if they pass deploy to production. A loop cannot express that cleanly.

**Step 3 — test deploy:** `docker compose -p gan-shmuel-test -f docker-compose.test.yml up -d --build` starts the test containers without touching production. `--build` is included because the test project has its own image tags (`gan-shmuel-test-billing` vs `gan-shmuel-green-billing`) and needs to build them separately. The production build in step 2 means the layers are already cached, so this is fast.

**Step 4 — run tests:** `python /repo/tests/test_health.py` runs the test script inside the CI container. Python is available (it is the base image), `requests` is now installed, and the script is at `/repo/tests/test_health.py` via the bind mount. If the script calls `sys.exit(1)`, `result.returncode` is non-zero and the pipeline stops before production.

**Step 5 — production deploy:** Only reached if tests passed, and only if the branch is `main`. Non-main branches (feature branches, team branches) run CI (build + test) but skip CD (production deploy). Uses `-p gan-shmuel` to ensure the pipeline targets the correct project — without it, Docker Compose inside the container would derive the project name from `/repo` (the bind-mount path) and create duplicate containers instead of updating the existing production ones.

---

## Architecture decisions

**Decision 1: Where do the stubs live?**

Stubs go directly in `billing/` and `weight/` — the same place the real code will eventually live. When the teams are ready, they replace the stub with their real implementation. The pipeline doesn't change at all.

**Decision 2: How to separate test from production?**

Two separate compose files:
- `docker-compose.yml` — production services (weight on 8080, billing on 8081, real databases)
- `docker-compose.test.yml` — test environment (weight on 8082, billing on 8083, separate test databases)

**Decision 3: What do the tests look like?**

A Python script in a `tests/` directory at the repo root. It uses the `requests` library to hit `/health` on each test service and asserts `200 OK`. Simple enough to run against stubs now, extensible for real tests later.

**Pipeline flow (updated):**
1. Deploy to test: `docker compose -p gan-shmuel-test -f docker-compose.test.yml up -d --build`
2. `time.sleep(5)` — wait for containers to boot
3. Run tests against test ports
4. If tests pass and branch is `main` → deploy to prod: `docker compose -p gan-shmuel up -d --no-deps billing weight`
5. If tests fail or branch is not `main` → stop

---

## Bugs found during local testing

### Bug 1: `time.sleep(5)` placed after the tests instead of before

**Symptom:** Tests failed with `ConnectionResetError(104, 'Connection reset by peer')`. The connection was established (Flask was listening) but immediately dropped because the server hadn't finished booting.

**Root cause:** `time.sleep(5)` was placed after step 4 (tests) instead of between step 3 (test deploy) and step 4. The tests ran milliseconds after `docker compose up -d` returned — before Flask had time to start.

**Fix:** Move `time.sleep(5)` to between step 3 and step 4.

**Note on `time.sleep` vs healthchecks:** A fixed sleep is a simple solution but not ideal for production — 5 seconds may be too short if the system is slow, or wasteful if containers boot in 1 second. A proper solution would poll the `/health` endpoint until it responds, then run tests. For this project, `time.sleep(5)` is sufficient.

---

### Bug 2: Branch check missing — pipeline deployed to production from non-main branches

**Symptom:** Pushing to `devops-test-env` triggered a production deploy.

**Root cause:** The branch check (`if branch != 'main': return`) was never added to `app.py`. The commit message claimed the fix was included but the code was not there.

**Fix:** Add the branch check before step 5 in `run_pipeline()`.

**Why this matters:** CI (build + test) should run on every branch — catching regressions early. CD (production deploy) should only happen from `main` — only reviewed, approved code reaches production.

---

### Bug 3: Wrong project name in production deploy

**Symptom:** `docker compose up -d --no-deps billing weight` failed with "port is already allocated" — it tried to create new containers instead of updating the existing production ones.

**Root cause:** The pipeline runs inside the CI container where the repo is mounted at `/repo`. Docker Compose derives the project name from the working directory name, so it used `repo` as the project name. The existing production containers were created with project name `gan-shmuel` (from the host directory name). So the pipeline created a new `repo-billing-1` container while `gan-shmuel-billing-1` was already running on the same host port.

**Fix:** Explicitly pass `-p gan-shmuel` to the prod deploy command:
```python
['docker', 'compose', '-p', 'gan-shmuel', 'up', '-d', '--no-deps', 'billing', 'weight']
```

This forces Docker Compose to target the correct project regardless of where the command runs.

---

### Bug 4: File ownership changed by `git reset --hard` inside Docker container

**Symptom:** VSCode showed "Insufficient permissions" when trying to save `app.py`.

**Root cause:** The CI container runs as root. The repo is bind-mounted (`.:/repo`). When `git reset --hard` ran inside the container, git wrote files as root on the host filesystem. The user's account no longer owned those files.

**Fix:** After any pipeline run that touches the repo from inside a container, restore ownership:
```bash
sudo chown -R $USER:$USER .
```

This only affects local development — on EC2 everything runs as root anyway.

---

## Subtask 8: Testing the pipeline locally (and how it maps to EC2)

### What we did

**Step 1 — Start the CI service locally:**
```bash
docker compose up -d --build ci
```
This starts the CI container on your laptop. Port 8085 is now open on localhost.

**Step 2 — Trigger the pipeline manually:**
```bash
curl -X POST http://localhost:8085/trigger \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -d '{"ref": "refs/heads/devops-test-env"}'
```
On EC2, GitHub sends this request automatically when you push. Locally, your machine has no public IP so GitHub cannot reach `localhost:8085` — you simulate the webhook yourself with `curl`.

**Step 3 — Watch the logs:**
```bash
docker compose logs -f ci
```

**What the pipeline did:**
- `git fetch origin devops-test-env` + `git reset --hard` — fetched the latest code from GitHub. The remote is always GitHub regardless of whether CI runs locally or on EC2.
- `docker compose build` — built images from the code on your machine
- `docker compose -p gan-shmuel-test -f docker-compose.test.yml up -d` — started test containers on your machine (billing on port 8083, weight on port 8082)
- `time.sleep(5)` — waited for Flask to boot
- `python tests/test_health.py` — ran from inside the CI container, hit `host.docker.internal:8082` and `host.docker.internal:8083` → reached the test containers through the host port mapping
- Branch check: `devops-test-env != main` → skipped production deploy

**Result:**
```
git fetch + checkout + reset --hard ✓
docker compose build ✓
docker compose -p gan-shmuel-test -f docker-compose.test.yml up -d --build ✓
time.sleep(5) ✓
[PASS] billing /health returned 200
[PASS] weight /health returned 200
All tests passed ✓
Branch 'devops-test-env' is not 'main' - skipping production deploy ✓
Pipeline finished successfully ✓
```

---

### How this maps to EC2

The pipeline code is identical on EC2. The only differences are the trigger and the machine:

| | Local | EC2 |
|---|---|---|
| Trigger | Manual `curl` | GitHub webhook (fires automatically on push) |
| Machine | Developer laptop | EC2 server (3.108.241.170) |
| Prod deploy | Skipped (non-main branch) | Runs when push is to `main` |

Everything else — the Docker commands, the ports, the test script, `host.docker.internal` — works the same way on both machines.

Local testing proves the pipeline logic is correct. EC2 is where it runs permanently in production.

---

## Subtask 9: Test container cleanup

### The problem

After the pipeline runs, the 4 test containers (`gan-shmuel-test-*`) stay running. They are not needed after tests complete — they just consume memory and ports. Without cleanup, containers accumulate after every pipeline run.

### The fix

A `cleanup_test_env()` helper function that tears down the test environment:

```python
def cleanup_test_env():
    result = subprocess.run(
        ['docker', 'compose', '-p', 'gan-shmuel-test', '-f', 'docker-compose.test.yml', 'down'],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    logging.info(f"Test cleanup: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Test environment cleanup failed: {result.stderr.strip()}")
```

And in `run_pipeline()`, the step 4 block becomes:

```python
    # Step 4: Run tests
    result = subprocess.run(
        ['python', f'{REPO_DIR}/tests/test_health.py'],
        capture_output=True, text=True
    )
    logging.info(f"Tests: {result.stdout.strip()}")

    # On success/failure, we cleanup the test environment
    if result.returncode != 0:
        logging.error(f"Tests failed: {result.stderr.strip()}")
        cleanup_test_env()
        return

    cleanup_test_env()
```

### Why a separate function?

The cleanup command is called in two places: on test failure (before returning) and on test success (before proceeding to step 5). Extracting it to a function avoids duplicating the same `subprocess.run` block twice.

### Why `docker compose down` and not `docker compose down -v`?

`down` stops and removes containers and the default network, but keeps named volumes (the database data). `down -v` would also wipe the volumes — destroying the test DB on every pipeline run. We keep the volumes so the DB schema is preserved between runs.

### When cleanup runs

Cleanup runs in both the success and failure paths — test containers are always torn down before the pipeline continues to step 5 or exits. This ensures no stale test containers are left behind regardless of outcome.

---

## Subtask 10: Mailing System

### Why

Without email notifications, the only way to know the pipeline failed is to check the CI logs manually. Email alerts mean developers are notified automatically — they can act on failures without polling.

### Notification policy

| Event | Recipients |
|---|---|
| Any branch fails | Team that owns the branch + DevOps team |
| `main` fails | Everyone |
| `main` succeeds | Everyone |
| Non-main branch succeeds | Branch's team + DevOps team |

The team is extracted from the branch name using the naming convention `<team>-<feature>` — e.g. `weight-new-feature` → `weight`. If the prefix doesn't match a known team (naming convention violated), DevOps is notified as a fallback.

### Credentials

Add to `.env` (never committed):
```
GMAIL_USER=ganshmuelci@gmail.com
GMAIL_PASSWORD=<app-password>
NOTIFY_ALL=everyone@gmail.com,...
NOTIFY_DEVOPS=steve@gmail.com
NOTIFY_WEIGHT=weight1@gmail.com,weight2@gmail.com
NOTIFY_BILLING=billing1@gmail.com,billing2@gmail.com
```

`GMAIL_USER` and `GMAIL_PASSWORD` are the sender account credentials. A dedicated Gmail account (`ganshmuelci@gmail.com`) is used instead of a personal account so personal credentials are never on the server. Gmail requires an **app password** (generated under Google Account → Security → 2-Step Verification → App passwords) — regular passwords are rejected.

`NOTIFY_*` are recipient lists. `NOTIFY_ALL` is used for `main` branch events. `NOTIFY_DEVOPS`, `NOTIFY_WEIGHT`, `NOTIFY_BILLING` are used for team-specific notifications.

### New code in `app.py`

**Imports:**
```python
import smtplib
from email.mime.text import MIMEText
```

**Globals:**
```python
EMAIL_FROM = os.environ.get('GMAIL_USER')
EMAIL_TO = os.environ.get('NOTIFY_ALL', EMAIL_FROM)
EMAIL_PASSWORD = os.environ.get('GMAIL_PASSWORD')
```

**`get_recipients()` — resolves who to notify based on branch:**
```python
def get_recipients(branch):
    if branch == 'main':
        return os.environ.get('NOTIFY_ALL', '')
    team = branch.split('-')[0]
    team_emails = os.environ.get(f'NOTIFY_{team.upper()}', '')
    devops_emails = os.environ.get('NOTIFY_DEVOPS', '')
    if not team_emails:
        logging.warning(f"No recipients configured for team '{team}', notifying DevOps only")
        return devops_emails
    combined = set(filter(None, team_emails.split(',') + devops_emails.split(',')))
    return ','.join(combined)
```

`branch.split('-')[0]` extracts the team prefix — `weight-new-feature` → `weight`. The corresponding `NOTIFY_WEIGHT` env var is looked up. If not found (naming convention violated), DevOps-only fallback.

**`send_email()` — sends the notification:**
```python
def send_email(subject, body, recipients):
    if not EMAIL_FROM or not EMAIL_PASSWORD or not recipients:
        logging.warning("Email not sent: missing credentials or recipients")
        return
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = recipients
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, recipients.split(','), msg.as_string())
        logging.info(f"Email sent: {subject}")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
```

`SMTP_SSL` on port 465 connects encrypted from the start (simpler than STARTTLS on 587). `sendmail` takes a list of addresses for actual delivery — `recipients.split(',')` splits the comma-separated string. `msg['To']` is the display header; `sendmail` is what actually routes the message. The whole send is wrapped in `try/except` — if email fails, the pipeline continues rather than crashing, since the deploy already happened.

**`send_email()` calls in `run_pipeline()`:**

`recipients = get_recipients(branch)` is resolved once at the top. Every exit point calls `send_email()`:
- Step 1-3 failures: `[FAIL]` with stderr
- Step 4 failure: `[FAIL]` with stdout (test output, not stderr, is where the `[FAIL]` lines appear)
- Non-main success: `[SUCCESS]` noting prod deploy was skipped
- Step 5 failure: `[FAIL]` with stderr
- Final success: `[SUCCESS]` confirming production deployed

---

## Day 2 Status — COMPLETE

All subtasks finished and tested locally. Both feature branches merged into `devops` via PRs:
- `devops-test-env` → `devops`
- `devops-mailing` → `devops`

---

## Deploying to EC2

The EC2 server needs to be updated manually after the `devops` branch is ready. Steps:

### 1. SSH into EC2
```bash
ssh -i <key.pem> ubuntu@3.108.241.170
```

### 2. Pull the latest `devops` branch
```bash
cd ~/Gan-Shmuel-Green
git fetch origin
git checkout devops
git reset --hard origin/devops
sudo chown -R ubuntu:ubuntu ~/Gan-Shmuel-Green
```

### 3. Create `.env` on EC2
The `.env` file is gitignored and must be created manually on the server:
```
MYSQL_ROOT_PASSWORD=<password>
GMAIL_USER=ganshmuelci@gmail.com
GMAIL_PASSWORD=<app-password>
NOTIFY_ALL=<all team emails comma-separated>
NOTIFY_DEVOPS=<devops team emails>
NOTIFY_WEIGHT=<weight team emails>
NOTIFY_BILLING=<billing team emails>
```

### 4. Rebuild the CI container
```bash
sudo docker compose up -d --build ci
sudo chown -R ubuntu:ubuntu ~/Gan-Shmuel-Green
```

### 5. Verify
```bash
curl http://localhost:8085/health
```

From this point, every GitHub push fires the full pipeline automatically via the webhook — build → test → email notification → (main only) production deploy.

---

