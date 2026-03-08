# Day 2 Bonus: Monitoring Page

## What this is

A web page at `/status` served by the CI container that shows the live state of all Docker containers — which are running, which are down, their uptime, and their ports. It reads from the Docker socket (already mounted in the CI container) using the Docker Python SDK, and renders a color-coded HTML page.

Accessible at: `http://3.108.241.170:8085/status`

---

## Branch structure

```
devops-monitor (base, branched off devops)
├── devops-monitor-backend  (Sami: subtasks 1 + 2)
└── devops-monitor-frontend (Steve: subtask 3)
```

Both sub-branches merge into `devops-monitor` via PR, then `devops-monitor` → `devops`.

---

## Subtasks

### Subtask 1: Add Docker SDK to `ci/requirements.txt` — Sami

The Docker Python SDK allows Python code to interact with the Docker daemon directly — list containers, inspect them, check status — without parsing subprocess output.

```
Flask==3.0.3
requests==2.32.3
docker==7.1.0
```

---

### Subtask 2: Add `/status` route to `ci/app.py` — Sami

A new Flask route that queries the Docker daemon for all containers and passes the data to an HTML template.

Add `render_template` to the Flask import:
```python
from flask import Flask, request, jsonify, render_template
```

Add the Docker SDK import:
```python
import docker as docker_sdk
```

Add the route:
```python
@app.route('/status', methods=['GET'])
def status():
    client = docker_sdk.from_env()
    containers = client.containers.list(all=True)
    container_data = []
    for c in containers:
        ports = ', '.join([
            f"{v[0]['HostPort']}→{k.split('/')[0]}"
            for k, v in (c.ports or {}).items() if v
        ])
        container_data.append({
            'name': c.name,
            'status': c.status,
            'image': c.image.tags[0] if c.image.tags else c.short_id,
            'ports': ports or '—',
        })
    return render_template('status.html', containers=container_data)
```

### Why `client.containers.list(all=True)`?

Without `all=True`, only running containers are returned. Passing `all=True` includes stopped/exited containers — useful for spotting services that have crashed.

### Why `docker_sdk` alias?

The package is named `docker`, which would conflict with the `docker` CLI subprocess calls elsewhere in the file. The alias avoids any ambiguity.

---

### Subtask 3: Create `ci/templates/status.html` — Steve

Flask looks for templates in a `templates/` folder relative to the app file. Create `ci/templates/status.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Gan Shmuel — System Status</title>
  <style>
    body { font-family: sans-serif; background: #f4f4f4; padding: 2rem; }
    h1 { color: #333; }
    table { border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
    th { background: #333; color: white; padding: 0.75rem 1rem; text-align: left; }
    td { padding: 0.75rem 1rem; border-bottom: 1px solid #eee; }
    .running { color: green; font-weight: bold; }
    .exited  { color: red;   font-weight: bold; }
  </style>
</head>
<body>
  <h1>System Status</h1>
  <table>
    <tr>
      <th>Container</th>
      <th>Image</th>
      <th>Status</th>
      <th>Ports</th>
    </tr>
    {% for c in containers %}
    <tr>
      <td>{{ c.name }}</td>
      <td>{{ c.image }}</td>
      <td class="{{ c.status }}">{{ c.status }}</td>
      <td>{{ c.ports }}</td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
```

### Why a separate `templates/` folder?

Flask's `render_template()` looks for HTML files in a `templates/` directory by convention. Keeping HTML separate from Python code is cleaner than embedding HTML strings directly in `app.py`.

### Why `{% for c in containers %}`?

This is Jinja2 — Flask's built-in templating engine. It lets you loop over Python data passed from the route and generate HTML dynamically. The `containers` list is passed from the `/status` route via `render_template('status.html', containers=container_data)`.

---

## Q&A

**What is an SDK?**

SDK stands for Software Development Kit. It's a pre-built library that gives you a clean, high-level interface to interact with some system or service — so you don't have to deal with the low-level details yourself.

For example, instead of manually sending HTTP requests to the Docker API and parsing raw JSON responses, the Docker SDK gives you simple Python calls like `client.containers.list()` that handle all of that for you.

---

**What is the Docker Python SDK?**

It's an official Python library (`pip install docker`) that lets Python code talk to the Docker daemon — the background process that manages containers on your machine. It exposes Docker's functionality as Python objects and methods:

```python
client = docker.from_env()             # connect to Docker daemon
containers = client.containers.list() # list running containers
c.name                                 # container name
c.status                               # "running", "exited", etc.
c.ports                                # port mappings
```

Under the hood it talks to the Docker socket (`/var/run/docker.sock`) — the same socket that's already mounted into the CI container. That's why this works without any extra setup.

---

**HTML breakdown**

```html
<!DOCTYPE html>
<html lang="en">
```
Declares this is an HTML5 document. `lang="en"` tells the browser the content is in English.

```html
<head>
  <meta charset="UTF-8">
  <title>Gan Shmuel — System Status</title>
```
The `<head>` section contains metadata — not visible on the page. `charset="UTF-8"` supports all characters. `<title>` sets the browser tab text.

```html
  <style>
    body { font-family: sans-serif; background: #f4f4f4; padding: 2rem; }
```
Inline CSS (styling rules). `body` styles the whole page — sans-serif font, light grey background, padding around the edges.

```html
    table { border-collapse: collapse; width: 100%; background: white; box-shadow: ... }
    th { background: #333; color: white; padding: 0.75rem 1rem; text-align: left; }
    td { padding: 0.75rem 1rem; border-bottom: 1px solid #eee; }
```
`table` — full width, white background, subtle shadow. `th` — dark header row with white text. `td` — table cells with padding and a light bottom border between rows.

```html
    .running { color: green; font-weight: bold; }
    .exited  { color: red;   font-weight: bold; }
```
CSS classes. Any element with `class="running"` gets green bold text. `class="exited"` gets red. These are applied to the status cell.

```html
<body>
  <h1>System Status</h1>
  <table>
    <tr>
      <th>Container</th><th>Image</th><th>Status</th><th>Ports</th>
    </tr>
```
`<body>` is the visible page content. `<h1>` is a heading. `<table>` starts the table. `<tr>` is a table row. `<th>` is a header cell.

```html
    {% for c in containers %}
    <tr>
      <td>{{ c.name }}</td>
      <td>{{ c.image }}</td>
      <td class="{{ c.status }}">{{ c.status }}</td>
      <td>{{ c.ports }}</td>
    </tr>
    {% endfor %}
```
This is Jinja2 mixed into HTML. `{% for c in containers %}` loops over the list passed from Flask. `{{ c.name }}` inserts the value into the HTML. `class="{{ c.status }}"` sets the CSS class to either `"running"` or `"exited"` — which triggers the green or red color defined above. `{% endfor %}` closes the loop.

---

## Testing

Once implemented and CI is rebuilt:
```bash
curl http://localhost:8085/status        # on EC2
curl http://localhost:8085/status        # locally
```

Or open in a browser: `http://3.108.241.170:8085/status`
