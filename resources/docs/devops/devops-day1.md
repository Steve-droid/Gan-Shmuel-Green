# Day 1 — CI Service: app.py Explained

---

## 1. Imports

```python
from flask import Flask, request, jsonify
import subprocess
import threading
import os
import logging
```

### `flask` — `Flask`, `request`, `jsonify`

**What it is:** A lightweight Python web framework for building HTTP servers.

**Why we need it:** The CI service is an HTTP server that listens for incoming requests from GitHub. Flask makes it trivial to define routes (`/health`, `/trigger`) and handle HTTP requests.

**Example in app.py:**
```python
@app.route('/trigger', methods=['POST'])
def trigger():
    payload = request.get_json(silent=True) or {}
    return jsonify({"status": "triggered", "branch": branch}), 200
```
- `Flask` creates the app
- `request` reads the incoming JSON payload from GitHub
- `jsonify` converts a Python dict into a JSON HTTP response

---

### `subprocess`

**What it is:** A Python standard library module that lets you run shell commands from within a Python script.

**Why we need it:** The CI pipeline needs to run external programs (`git`, `docker-compose`) that have no Python equivalent. `subprocess` is the bridge between the Flask app and those terminal tools.

**Example in app.py:**
```python
subprocess.run(['git', 'pull', 'origin', branch], cwd=REPO_DIR, capture_output=True, text=True)
```
Equivalent to typing `git pull origin main` in a terminal inside the `/repo` directory.

---

### `threading`

**What it is:** A Python standard library module for running code concurrently in background threads.

**Why we need it:** GitHub requires a response to its webhook POST within ~10 seconds or it marks the delivery as failed. The CI pipeline (git pull + docker build + docker up) takes 30–60 seconds. Running it in a background thread lets us respond to GitHub immediately while the pipeline continues running independently.

**Example in app.py:**
```python
thread = threading.Thread(target=run_pipeline, args=(branch,), daemon=True)
thread.start()
return jsonify({"status": "triggered", "branch": branch}), 200
```
The pipeline starts in the background, and `200` is returned to GitHub right away.

---

### `os`

**What it is:** A Python standard library module for interacting with the operating system — reading environment variables, file paths, etc.

**Why we need it:** The repo directory path is passed in as an environment variable. Using `os.environ.get()` lets us read it at runtime rather than hardcoding it, making it configurable.

**Example in app.py:**
```python
REPO_DIR = os.environ.get('REPO_DIR', '/repo')
```

---

### `logging`

**What it is:** A Python standard library module for printing structured, timestamped log messages.

**Why we need it:** The CI pipeline runs in the background — there's no user watching it run. Logging is the only way to know what happened: did `git pull` succeed? Did `docker-compose build` fail? Logs answer these questions.

**Example in app.py:**
```python
logging.info(f"git pull: {result.stdout.strip()}")
logging.error(f"Failed: {result.stderr.strip()}")
```
Prints timestamped messages like:
```
2026-02-26 09:00:01 [INFO] git pull: Already up to date.
2026-02-26 09:00:45 [ERROR] Failed: Cannot connect to Docker daemon
```

---

## 2. Logging Configuration

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
```

`logging.basicConfig()` configures the global logging system. It does not return anything — it is purely setup.

The two arguments:
- **`level=logging.INFO`** — sets the minimum severity level to display. `INFO` means you'll see `INFO`, `WARNING`, and `ERROR` messages. Messages below that (like `DEBUG`) are silently ignored.
- **`format='%(asctime)s [%(levelname)s] %(message)s'`** — defines how each log line looks. The placeholders get filled in automatically:
  - `%(asctime)s` → timestamp: `2026-02-26 09:00:01`
  - `%(levelname)s` → severity: `INFO` or `ERROR`
  - `%(message)s` → whatever you passed to `logging.info()` or `logging.error()`

So this call:
```python
logging.info("Pipeline finished successfully")
```
Produces this output:
```
2026-02-26 09:00:01 [INFO] Pipeline finished successfully
```

You call `basicConfig()` once at startup, and from then on every `logging.info()` / `logging.error()` call anywhere in the code automatically uses that format.

---

## 3. App and REPO_DIR

```python
app = Flask(__name__)
REPO_DIR = os.environ.get('REPO_DIR', '/repo')
```

**`app = Flask(__name__)`** creates the Flask application. `__name__` is a special Python variable that holds the name of the current module — Flask uses it internally to locate resources.

**`REPO_DIR`** is the path to the folder where the pipeline commands will run. `os.environ.get('REPO_DIR', '/repo')` reads it from an environment variable, defaulting to `/repo` if not set.

At this point in the code there is no container yet — `REPO_DIR` is just a Python variable. The container comes later when we write the `Dockerfile` and `docker-compose.yml`, which will mount the repo into the container at `/repo` and pass `REPO_DIR=/repo` as an environment variable. We read it from an environment variable instead of hardcoding `/repo` so the path can be changed without touching the code.

On the EC2 server the repo will be cloned to some folder (e.g. `/home/ubuntu/gan-shmuel`). That path gets passed in as `REPO_DIR` so the pipeline commands run inside the right folder — where `docker-compose.yml` and `.git` actually live.

---

## 4. `run_pipeline()`

```python
def run_pipeline(branch):
    commands = [
        ['git', 'pull', 'origin', branch],
        ['docker-compose', 'build'],
        ['docker-compose', 'up', '-d'],
    ]
    for cmd in commands:
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        logging.info(f"{' '.join(cmd)}: {result.stdout.strip()}")
        if result.returncode != 0:
            logging.error(f"Failed: {result.stderr.strip()}")
            return
    logging.info("Pipeline finished successfully")
```

**`def run_pipeline(branch)`** — takes the branch name as an argument (e.g. `"main"`), so it knows what to pull.

**`commands`** — a list of the three shell commands to run in order. Each command is itself a list of strings (how `subprocess` expects them).

**`subprocess.run(...)`**:
- `cmd` — the command to run
- `cwd=REPO_DIR` — run it in the repo directory (`cwd` = current working directory, equivalent to `cd`-ing into that folder first)
- `capture_output=True` — redirects the command's output into Python variables (`result.stdout`, `result.stderr`) instead of printing directly to the terminal. Without this, Python can't read the output.
- `text=True` — return output as a string instead of raw bytes

**`result.returncode`** — every shell command exits with a code. `0` means success, anything else means failure. If a step fails, we log the error and `return` — no point running `docker-compose up` if the build failed.

**`logging.info(f"{' '.join(cmd)}: {result.stdout.strip()}")`** — three things:
- `' '.join(cmd)` — joins the command list into a readable string:
  ```python
  ['git', 'pull', 'origin', 'main']  →  "git pull origin main"
  ```
- `result.stdout.strip()` — removes trailing newlines from the command output:
  ```python
  "Already up to date.\n"  →  "Already up to date."
  ```
- `logging.info(...)` — logs the combined message, producing a line like:
  ```
  2026-02-26 09:00:01 [INFO] git pull origin main: Already up to date.
  ```

---

## 5. `GET /health`

```python
@app.route('/health', methods=['GET'])
def health():
    return 'OK', 200
```

**`@app.route('/health', methods=['GET'])`** — a decorator that registers the function below it as the handler for `GET /health`. When Flask receives a `GET` request to `/health`, it calls `health()`.

**`return 'OK', 200`** — returns two things to Flask:
- `'OK'` — the response body
- `200` — the HTTP status code meaning "success"

That's the entire function. The CI service has no database or external dependencies, so there's nothing to check — if the server is running and this function can be called, the service is healthy.

---

## 6. `POST /trigger`

```python
@app.route('/trigger', methods=['POST'])
def trigger():
    payload = request.get_json(silent=True) or {}
    ref = payload.get('ref', 'refs/heads/main')
    branch = ref.split('/')[-1]

    if payload.get('action') == 'deleted':
        return jsonify({"status": "ignored", "reason": "branch deleted"}), 200

    thread = threading.Thread(target=run_pipeline, args=(branch,), daemon=True)
    thread.start()
    return jsonify({"status": "triggered", "branch": branch}), 200
```

**Client:** GitHub. **Server:** The CI Flask app on EC2. GitHub sends this `POST` request automatically every time someone pushes to the repo. The body is always JSON — not because HTTP requires it, but because that is what GitHub sends.

**`request.get_json(silent=True) or {}`** — parses the request body as JSON. `silent=True` means if the body isn't valid JSON, return `None` instead of crashing. The `or {}` means if we got `None`, use an empty dict — so `.get()` calls below never fail.

**`payload.get('ref', 'refs/heads/main')`** — reads the `ref` field from GitHub's payload. GitHub sends it as a full path like `"refs/heads/main"`. The default `'refs/heads/main'` is a fallback if the field is missing.

**`ref.split('/')[-1]`** — splits the string on `/` and takes the last part:
```python
"refs/heads/main".split('/')  →  ['refs', 'heads', 'main']
[-1]                           →  'main'
```

**`payload.get('action') == 'deleted'`** — GitHub also sends webhooks when a branch is deleted. There is nothing to deploy in that case, so we return early with `"ignored"`.

**`threading.Thread(target=run_pipeline, args=(branch,), daemon=True)`** — creates a background thread that will call `run_pipeline(branch)`. `daemon=True` means the thread won't prevent the server from shutting down.

**`thread.start()`** — starts the thread. The pipeline now runs independently in the background.

**`return jsonify(...), 200`** — immediately returns `200` to GitHub without waiting for the pipeline to finish. GitHub requires a response within ~10 seconds or it marks the webhook delivery as failed.

---

## 7. Entry Point

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

**`if __name__ == '__main__'`** — a Python convention that means "only run the code below if this file is being run directly, not imported as a module." It prevents the server from starting if another file imports `app.py`.

**`app.run(host='0.0.0.0', port=8080)`**:
- `host='0.0.0.0'` — listen on all network interfaces, meaning the server is reachable from outside the machine. If you used `127.0.0.1` (localhost) instead, only the machine itself could reach it — GitHub couldn't send webhooks to it.
- `port=8080` — the port the server listens on. This matches the port exposed in the EC2 security group and the one we'll register in the GitHub webhook URL.

---

# Dockerfile

## Why do we need a Dockerfile?

`app.py` is just a Python file — it can't run on its own on the EC2 server without the right environment: Python installed, Flask installed, the right version, etc. You can't guarantee the EC2 server has any of that.

A `Dockerfile` is a recipe for building a **Docker image** — a self-contained package that includes everything needed to run the app: the OS, Python, dependencies, and the code itself. Once built into an image, it runs identically on any machine that has Docker.

## What will it be used for?

When the CI pipeline runs `docker compose build`, Docker reads the `Dockerfile` and builds an image for the CI service. When it runs `docker compose up -d`, Docker starts a container from that image — that container is the running Flask app.

## Thinking process

When writing a Dockerfile, ask three questions:

**1. What base do I start from?**
We need Python, so we start from an official Python image. `python:3.11-slim` gives us Python 3.11 on a minimal Linux base — small and fast.

**2. What does the app need to run?**
- Flask (from `requirements.txt`)
- Git (to run `git pull`)
- Docker (to run `docker compose build/up`)

**3. How do I start the app?**
Run `python app.py`.

## The Dockerfile

```dockerfile
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y git docker.io && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

CMD ["python", "app.py"]
```

**Line by line:**
- `FROM python:3.11-slim` — start from the official Python 3.11 image
- `RUN apt-get install git docker.io` — install git and docker inside the image
- `rm -rf /var/lib/apt/lists/*` — clean up the package manager cache to keep the image small
- `WORKDIR /app` — set the working directory inside the container
- `COPY requirements.txt .` — copy requirements first (before the code) so Docker can cache the pip install layer and skip it if requirements haven't changed
- `RUN pip install` — install Flask
- `COPY app.py .` — copy the application code
- `EXPOSE 8080` — documents that the container listens on port 8080
- `CMD ["python", "app.py"]` — the command to run when the container starts

---

# docker-compose.yml

## Why do we need `docker-compose.yml`?

The `Dockerfile` tells Docker how to build a single image. But `docker-compose.yml` answers a different question: **how do all the services fit together and run?**

Right now we have one service (CI), but eventually we'll have three (CI, billing, weight). `docker-compose.yml` is the single file that defines all of them — their ports, volumes, environment variables, and how they relate to each other. Without it, you'd have to manually run `docker build` and `docker run` with a long list of flags for each service every time.

## What will it be used for?

When the CI pipeline runs `docker compose build` and `docker compose up -d`, Docker reads this file to know:
- Which services to build and from where
- Which ports to expose
- Which volumes to mount
- Which environment variables to pass in

## Thinking process

Ask three questions for each service:

**1. Where is the image built from?**
`build: ./ci` — points Docker to the `ci/` directory where the `Dockerfile` lives.

**2. Which ports need to be exposed?**
`8080:8080` — maps port 8080 on the EC2 host to port 8080 inside the container, so GitHub can reach it.

**3. What does the container need access to?**
Two things:
- The Docker socket (`/var/run/docker.sock`) — so the CI container can run `docker compose` commands on the host
- The repo directory (`.:/repo`) — so the CI container can run `git pull` against the actual project files

## The `docker-compose.yml`

```yaml
version: '3.8'

services:
  ci:
    build: ./ci
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - .:/repo
    environment:
      - REPO_DIR=/repo
    restart: unless-stopped
```

**Line by line:**
- `version: '3.8'` — the Docker Compose file format version
- `build: ./ci` — build the image from `ci/Dockerfile`
- `ports: "8080:8080"` — `host:container` port mapping
- `/var/run/docker.sock:/var/run/docker.sock` — mounts the host's Docker socket into the container so it can control Docker (this is called "Docker outside of Docker")
- `.:/repo` — mounts the entire repo into the container at `/repo`
- `REPO_DIR=/repo` — tells `app.py` where the repo is mounted
- `restart: unless-stopped` — automatically restarts the container if it crashes, unless you manually stop it

## Why mount the Docker socket?

The CI container's job is to run `docker compose build` and `docker compose up -d`. Those are Docker commands — they need to talk to the Docker daemon to work.

But Docker runs on the **host machine** (the EC2 server), not inside the container. By default, a container is isolated and has no way to reach the host's Docker daemon.

By mounting `/var/run/docker.sock` (a Unix socket file that Docker listens on) into the container, we give the container a direct line to the host's Docker daemon. When the CI container runs `docker compose build`, it's not running Docker itself — it's sending instructions to the host's Docker through that socket.

Without this, the CI container couldn't build or start any other containers.

## What is `/repo` in `.:/repo`?

`/repo` is just a directory path **inside the container** — we chose that name. It doesn't come from anywhere special, it's not a variable. We could have written `.:/app` or `.:/project` and it would work the same way.

The format is `host_path:container_path`:
- `.` — the current directory on the host (the repo root on EC2)
- `/repo` — where that directory will appear inside the container

It connects to `REPO_DIR=/repo` in the environment variables — that's how `app.py` knows where to find the repo. The two must match: if you changed `/repo` to `/project` in the volume, you'd also need to change `REPO_DIR=/project`.

---

## Q&A: Testing the CI Service

### Why are there two directories `/app` and `/repo` inside the container?

They serve different purposes:

- `/app` — created by the `Dockerfile`. This is where the **CI service's own code** lives (`app.py`, etc.). It's baked into the image at build time via `COPY`.
- `/repo` — created by the volume mount in `docker-compose.yml`. This is where the **project repo** is mounted from the host at runtime.

Inside the container the structure looks like this:
```
/
├── app/          ← CI service code (app.py, requirements.txt)
├── repo/         ← the entire gan-shmuel repo, mounted from the host
│   ├── ci/
│   ├── billing/
│   ├── weight/
│   └── docker-compose.yml
└── ...           ← standard Linux filesystem
```

### What is the `dubious ownership` error?

```
fatal: detected dubious ownership in repository at '/repo'
```

Git is refusing to run because `/repo` is owned by a different user than the one running inside the container. This is a Git security feature introduced in Git 2.35.2 to prevent attacks where a malicious repo is injected via a shared directory.

The fix is to add this to the `Dockerfile`:
```dockerfile
RUN git config --global --add safe.directory /repo
```

This tells Git: "I trust `/repo` even if the ownership doesn't match."

### Why is `/app` separated from `/repo/ci/`? What is stored under `/repo/ci/`?

`/repo/ci/` contains the same files as `/app` (`app.py`, `Dockerfile`, `requirements.txt`) — but they serve different roles:

- `/app` — a snapshot of the CI code **baked into the image** at build time via `COPY app.py .` in the Dockerfile. Set once when the image was built.
- `/repo/ci/` — the **live version** of those same files from the mounted repo on the host, updated every time `git pull` runs.

The reason they're separate is timing:
- `/app` is fixed at image build time
- `/repo` reflects the current state of the repo on disk

The pipeline runs `git pull` to update `/repo`, then `docker compose build` to rebuild the image (which re-copies the updated files into a new `/app`), then `docker compose up -d` to start a new container with the updated image.

So `/app` and `/repo/ci/` are in sync **after** a successful pipeline run, but during the pipeline they can briefly differ.

### Does the `ci` container create the other containers?

Yes. The `ci` container runs on the EC2 server and uses the Docker socket to build and start the `weight` and `billing` containers on the same host. It never runs Docker itself — it just sends commands to the host's Docker daemon through the mounted socket.

---

# Deploying to EC2

## Why does `ssh green` work?

Earlier you configured `~/.ssh/config` with:

```
Host green
  HostName 3.108.241.170
  User ubuntu
  IdentityFile ~/.ssh/green-key
```

`green` is just an alias. When you type `ssh green`, your SSH client looks up `green` in `~/.ssh/config` and expands it to:
```bash
ssh -i ~/.ssh/green-key ubuntu@3.108.241.170
```

## Who is the client and who is the server for `curl http://localhost:8085/health`?

This command runs **on the EC2 server** (after you SSH in):
- **Client:** `curl`, running on the EC2 server
- **Server:** The CI Flask container, also running on the EC2 server

Both are on the same machine. `localhost` refers to the EC2 server itself — `curl` is just checking that the container started correctly and is listening on port 8085.

---

# Testing on EC2 — Bugs Found and Fixes

## The port architecture

The EC2 server is a physical machine at `3.108.241.170` with ports 8080–8090 open. Docker containers run **on the host**, not nested inside each other. The port mapping format is `HOST_PORT:CONTAINER_PORT`:

```
EC2 Host (3.108.241.170)
├── gan-shmuel-green-ci-1    ← port 8085 on HOST → 8085 inside this container
│                              (the running CI service, started manually)
│
├── (future) billing-1       ← will bind e.g. 8081 on HOST
└── (future) weight-1        ← will bind e.g. 8080 on HOST
```

All containers are siblings on the host. None are nested inside another. When the CI container runs `docker compose up -d`, it sends commands through the Docker socket to the **host's Docker daemon**, which creates the new containers **on the host** — not inside the CI container.

---

## Bug 1: Port conflict on `docker compose up -d`

**Error seen in logs:**
```
Bind for :::8085 failed: port is already allocated
```

**Root cause:** `docker compose up -d` (with no service names) starts *all* services in the file, including `ci`. The host Docker daemon tries to create a new `ci` container (`repo-ci-1`) and bind it to host port 8085 — but that port is already taken by the currently running `gan-shmuel-green-ci-1`.

The CI service is infrastructure. It should never be restarted by its own pipeline. The pipeline's `docker compose up -d` should only deploy the *application* services — `billing` and `weight`.

**Fix:** Pass service names explicitly and add `--no-deps`:

```python
['docker', 'compose', 'up', '-d', '--no-deps', 'billing', 'weight']
```

- **`billing weight`** — only start those services, skipping `ci`
- **`--no-deps`** — don't also start services they `depends_on:` (prevents surprises as the compose file grows)

---

## Bug 2: `git pull` fails on diverged branches

**Error seen in logs:**
```
fatal: Not possible to fast-forward, aborting.
```

**Root cause:** `git pull origin <branch>` means "merge `origin/<branch>` INTO whatever branch I'm currently on." The EC2 repo was checked out to `devops-deploy-ec2`, but a webhook fired for `main`. Those branches have diverged, and `pull.ff only` (set in the Dockerfile) forbids merges. So the pull aborts.

This also reveals a design issue: `git pull` is the wrong tool for CI. CI doesn't want to *merge* anything — it wants to *deploy exactly what was pushed*.

**Fix:** Replace `git pull` with a fetch + checkout + hard reset:

```python
['git', 'fetch', 'origin', branch],
['git', 'checkout', branch],
['git', 'reset', '--hard', f'origin/{branch}'],
```

- `git fetch origin branch` — downloads the latest state of that branch from GitHub into the local tracking ref (`origin/<branch>`). Does not touch the working tree.
- `git checkout branch` — switches the working tree to that branch.
- `git reset --hard origin/branch` — moves the local branch pointer to match `origin/<branch>` exactly and discards all local changes. Purely local — never touches the remote or any other branch.

This pattern is safe, predictable, and immune to diverged history.

---

## Updated `run_pipeline()` in `app.py`

```python
def run_pipeline(branch):
    commands = [
        ['git', 'fetch', 'origin', branch],
        ['git', 'checkout', branch],
        ['git', 'reset', '--hard', f'origin/{branch}'],
        ['docker', 'compose', 'build'],
        ['docker', 'compose', 'up', '-d', '--no-deps', 'billing', 'weight'],
    ]

    for cmd in commands:
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        logging.info(f"{' '.join(cmd)}: {result.stdout.strip()}")
        if result.returncode != 0:
            logging.error(f"Failed: {result.stderr.strip()}")
            return
    logging.info("Pipeline finished successfully")
```

The structure of the function is unchanged — the only differences are the git commands (fetch + checkout + reset instead of pull) and the explicit service names on `up -d`.

---

## Bug 3: GitHub ping event triggers the pipeline

**What happened:** After adding the webhook on GitHub, it immediately sends a **ping** event to verify the URL is reachable. Our `/trigger` route had no event-type check, so the ping was treated as a push. The pipeline ran, defaulted to `main` (since the ping payload has no `ref` field), ran `git checkout main` + `git reset --hard origin/main`, and switched the EC2 repo to `main` — which has no `docker-compose.yml`. This broke all subsequent `docker compose` commands on EC2.

**How GitHub signals event type:** Every webhook request includes an `X-GitHub-Event` HTTP header. For a push it is `push`. For the initial verification it is `ping`. For other events (PR opened, branch deleted, etc.) it has its own value. Our code was not reading this header at all.

**Fix:** Check the header at the very top of `/trigger` and ignore anything that isn't a `push`:

```python
@app.route('/trigger', methods=['POST'])
def trigger():
    event = request.headers.get('X-GitHub-Event', '')
    if event != 'push':
        return jsonify({"status": "ignored", "reason": f"event '{event}' is not a push"}), 200

    payload = request.get_json(silent=True) or {}
    ref = payload.get('ref', 'refs/heads/main')
    branch = ref.split('/')[-1]

    if payload.get('action') == 'deleted':
        return jsonify({"status": "ignored", "reason": "branch deleted"}), 200

    thread = threading.Thread(target=run_pipeline, args=(branch,), daemon=True)
    thread.start()
    return jsonify({"status": "triggered", "branch": branch}), 200
```

The event check is the first thing in the function — pings and all other non-push events are rejected before any payload parsing or pipeline execution happens.

**`request.headers.get('X-GitHub-Event', '')`** — reads the `X-GitHub-Event` header from the incoming HTTP request. `request.headers` is a dict-like object Flask populates from the raw HTTP headers. The second argument `''` is the default if the header is absent. An empty string will not equal `'push'`, so requests with no event header are also safely ignored.
