from flask import Flask, render_template, request, jsonify                                                                                                                                                         
import subprocess                                                                                                                                                                                 
import threading                                                                                                                                                                                  
import os                                                                                                                                                                                         
import logging
import time
import smtplib                                                                
from email.mime.text import MIMEText
from auth import authenticate
import docker as docker_sdk

#extract configuration from environment variables, with defaults.
#CI_PORT and CI_HOST are set in /etc/ci/ci.env, and loaded by systemd when starting the service.
CI_PORT=os.environ.get('CI_PORT', '8085') 
CI_HOST=os.environ.get('CI_HOST', '0.0.0.0')

#a lock to prevent multiple pipeline runs at the same time, 
# insures a single pipeline run at a time, and prevents race conditions.
bussy_lock=threading.Lock()

# Configure the global logging system
logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s [%(levelname)s] %(message)s'
  )

app = Flask(__name__)                                                                                                                                                                                                                       
REPO_DIR = os.environ.get('REPO_DIR', '/repo')
EMAIL_FROM = os.environ.get('GMAIL_USER')
EMAIL_TO = os.environ.get('NOTIFY_ALL', EMAIL_FROM)
EMAIL_PASSWORD = os.environ.get('GMAIL_PASSWORD')
ALLOWED_BRANCHES = {'main', 'billing', 'weight', 'devops'}

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

def get_recipients(branch):
      if branch == 'main':
          return os.environ.get('NOTIFY_ALL', '')
      team = branch.split('-')[0]
      team_emails = os.environ.get(f'NOTIFY_{team.upper()}', '')
      devops_emails = os.environ.get('NOTIFY_DEVOPS', '')
      if not team_emails:
          # Unknown team prefix — fall back to notifying devops only
          logging.warning(f"No recipients configured for team '{team}', notifying DevOps only")
          return devops_emails
      combined = set(filter(None, team_emails.split(',') +
  devops_emails.split(',')))
      return ','.join(combined)

def cleanup_test_env():
    result = subprocess.run(
            ['docker', 'compose', '-p', 'gan-shmuel-test', '-f', 'docker-compose.test.yml', 'down'],
            cwd=REPO_DIR, capture_output=True, text=True
    )
    logging.info(f"Test cleanup: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Test environment cleanup failed: {result.stderr.strip()}")

def safe_run_pipeline(branch):
    with bussy_lock:
        logging.info(f"Starting pipeline for branch '{branch}'")
        run_pipeline(branch)


def run_pipeline(branch):
    recipients = get_recipients(branch)

    # Step 1: Update repo
    git_commands = [
        ['git', 'stash'],
        ['git','clean','-fd'],
        ['git', 'fetch', 'origin', branch],
        ['git', 'checkout', '-B', branch, f'origin/{branch}'],
        ['git', 'reset', '--hard', f'origin/{branch}'],
    ]
    for cmd in git_commands:
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        logging.info(f"{' '.join(cmd)}: {result.stdout.strip()}")
        if result.returncode != 0:
            logging.error(f"Failed: {result.stderr.strip()}")
            #send_email(f"[FAIL] Pipeline failed on {branch}", f"Step 1 (git) failed:\n{result.stderr.strip()}", recipients)
            return

    # Step 2: Build images
    result = subprocess.run(
        ['docker', 'compose', 'build'],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    logging.info(f"docker compose build: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Build failed: {result.stderr.strip()}")
        #send_email(f"[FAIL] Pipeline failed on {branch}", f"Step 2 (build) failed:\n{result.stderr.strip()}", recipients)
        return

    # Step 3: Deploy to test environment
    result = subprocess.run(
        ['docker', 'compose', '-p', 'gan-shmuel-test', '-f', 'docker-compose.test.yml', 'up', '-d', '--build'],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    logging.info(f"Test deploy: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Test deploy failed: {result.stderr.strip()}")
        #send_email(f"[FAIL] Pipeline failed on {branch}", f"Step 3 (test deploy) failed:\n{result.stderr.strip()}", recipients)
        return

    # Wait for MySQL to be ready in both DB containers (init scripts can take 60s+ on EC2)
    db_root_pass = os.environ.get('MYSQL_ROOT_PASSWORD', 'root')
    for db_container in ['gan-shmuel-test-weight-db-1', 'gan-shmuel-test-billing-db-1']:
        deadline = time.time() + 120
        while time.time() < deadline:
            result = subprocess.run(
                ['docker', 'exec', db_container,
                 'mysqladmin', 'ping', '-h', '127.0.0.1', '-u', 'root', f'-p{db_root_pass}', '--silent'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                logging.info(f"{db_container} is ready")
                break
            time.sleep(3)
        else:
            logging.warning(f"{db_container} did not become ready within 120s — proceeding anyway")

    # Copy sample upload files into containers
    # (volume bind path fails when docker-compose runs from inside the CI container)
    for container in ['gan-shmuel-test-billing-1', 'gan-shmuel-test-weight-1']:
        subprocess.run(
            ['docker', 'cp', f'{REPO_DIR}/resources/sample_files/sample_uploads/.', f'{container}:/app/in/'],
            capture_output=True, text=True
        )

    # Step 4: Run tests
    # Step 4a-i: Billing unit tests (run inside the billing test container which has all deps)
    # billing/.dockerignore excludes tests/ and conftest.py from the image, so we copy them in first
    for src, dst in [
        (f'{REPO_DIR}/billing/tests', 'gan-shmuel-test-billing-1:/app/tests'),
        (f'{REPO_DIR}/billing/conftest.py', 'gan-shmuel-test-billing-1:/app/conftest.py'),
    ]:
        subprocess.run(['docker', 'cp', src, dst], capture_output=True, text=True)

    result = subprocess.run(
        ['docker', 'exec', 'gan-shmuel-test-billing-1',
         'sh', '-c', 'pip install pytest -q && python -m pytest tests/ -v --ignore=tests/test_integration.py'],
        capture_output=True, text=True
    )

    logging.info(f"Billing tests: {result.stdout.strip()}")

    if result.returncode != 0:
        logging.error(f"Billing tests failed:\nSTDOUT: {result.stdout.strip()}\nSTDERR: {result.stderr.strip()}")
        #send_email(f"[FAIL] Pipeline failed on {branch}", f"Billing tests failed:\n{result.stdout.strip()}", recipients)
        cleanup_test_env()
        return

    # Step 4a-ii: Weight unit tests (run inside the weight test container which has all deps)
    result = subprocess.run(
        ['docker', 'exec', 'gan-shmuel-test-weight-1',
         'python', '-m', 'pytest', 'tests/', '-v',
         '--ignore=tests/test_e2e.py',
         '--ignore=tests/test_db_functions_day2.py'],
        capture_output=True, text=True
    )

    logging.info(f"Weight tests: {result.stdout.strip()}")

    if result.returncode != 0:
        logging.error(f"Weight tests failed:\nSTDOUT: {result.stdout.strip()}\nSTDERR: {result.stderr.strip()}")
        #send_email(f"[FAIL] Pipeline failed on {branch}", f"Weight tests failed:\n{result.stdout.strip()}", recipients)
        cleanup_test_env()
        return
    
    # Step 4b: Integration tests (DevOps)
    result = subprocess.run(
        ['python', '-m', 'pytest', 'tests/', '-v'],
        cwd=REPO_DIR, capture_output=True, text=True
    )

    logging.info(f"Integration tests: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Integration tests failed:\nSTDOUT: {result.stdout.strip()}\nSTDERR: {result.stderr.strip()}")
        #send_email(f"[FAIL] Pipeline failed on {branch}", f"Integration tests failed:\n{result.stdout.strip()}", recipients)
        cleanup_test_env()
        return    

    cleanup_test_env()

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
        #send_email(f"[FAIL] Pipeline failed on {branch}", f"Step 5 (prod deploy) failed:\n{result.stderr.strip()}", recipients)
        return

    logging.info("Pipeline finished successfully")



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
        'image': c.attrs['Config']['Image'],
        'ports': ports or '—',
        })
    try:
        container=client.containers.get('gan-shmuel-green-ci-1')
        ci_logs= container.logs(tail=200).decode('utf-8').strip() or "No logs"
    except subprocess.CalledProcessError as e:
        ci_logs= f"Failed to get CI logs: {e.stderr.strip()}"
    except Exception as e:
        ci_logs= f"Error getting CI logs: {str(e)}" 
    return render_template(
        'status.html',
        containers=container_data,
        ci_logs=ci_logs
    )


@app.route('/health', methods=['GET'])
def health():
    return 'OK', 200


@app.route('/trigger', methods=['POST'])
def trigger():
    
    if not authenticate(request):
        logging.info("Authentication failed for incoming request")
        return jsonify({"status": "error", "reason": "authentication failed"}), 401
    logging.info("Authentication successful for incoming request")
    
    event = request.headers.get('X-GitHub-Event', '')
    if event != 'push':
        return jsonify({"status": "ignored", "reason": f"event '{event}' is not a push"}), 200
    payload = request.get_json(silent=True) or {}
    ref = payload.get('ref', 'refs/heads/main')
    branch = ref.split('/')[-1]

    if branch not in ALLOWED_BRANCHES:
        return jsonify({"status": "ignored", "reason": f"branch '{branch}' is not a monitored branch"}), 200

    if payload.get('action') == 'deleted':
        return jsonify({"status": "ignored", "reason": "branch deleted"}), 200

    thread = threading.Thread(target=safe_run_pipeline, args=(branch,), daemon=True)
    thread.start()
    return jsonify({"status": "triggered", "branch": branch}), 200

if __name__ == '__main__':
    app.run(host=CI_HOST, port=int(CI_PORT))
