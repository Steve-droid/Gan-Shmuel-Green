from flask import Flask, request, jsonify                                                                                                                                                         
import subprocess                                                                                                                                                                                 
import threading                                                                                                                                                                                  
import os                                                                                                                                                                                         
import logging
import time
import smtplib                                                                
from email.mime.text import MIMEText
from auth import authenticate

#extract configuration from environment variables, with defaults.
#CI_PORT and CI_HOST are set in /etc/ci/ci.env, and loaded by systemd when starting the service.
CI_PORT=os.environ.get('CI_PORT', '8085') 
CI_HOST=os.environ.get('CI_HOST', '0.0.0.0')


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


def run_pipeline(branch):
    recipients = get_recipients(branch)

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
            send_email(f"[FAIL] Pipeline failed on {branch}", f"Step 1 (git) failed:\n{result.stderr.strip()}", recipients)
            return

    # Step 2: Build images
    result = subprocess.run(
        ['docker', 'compose', 'build'],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    logging.info(f"docker compose build: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Build failed: {result.stderr.strip()}")
        send_email(f"[FAIL] Pipeline failed on {branch}", f"Step 2 (build) failed:\n{result.stderr.strip()}", recipients)
        return

    # Step 3: Deploy to test environment
    result = subprocess.run(
        ['docker', 'compose', '-p', 'gan-shmuel-test', '-f', 'docker-compose.test.yml', 'up', '-d', '--build'],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    logging.info(f"Test deploy: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Test deploy failed: {result.stderr.strip()}")
        send_email(f"[FAIL] Pipeline failed on {branch}", f"Step 3 (test deploy) failed:\n{result.stderr.strip()}", recipients)
        return

    # Wait for containers to finish booting
    time.sleep(5)

    # Step 4: Run tests
    result = subprocess.run(
        ['python', f'{REPO_DIR}/tests/test_health.py'],
        capture_output=True, text=True
    )
    logging.info(f"Tests: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Tests failed: {result.stderr.strip()}")
        send_email(f"[FAIL] Pipeline failed on {branch}", f"Step 4 (tests) failed:\n{result.stdout.strip()}", recipients)
        cleanup_test_env()
        return

    cleanup_test_env()

    # Step 5: Deploy to production (only from main)
    if branch != 'main':
        logging.info(f"Branch '{branch}' is not 'main' - skipping production deploy")
        logging.info("Pipeline finished successfully")
        send_email(f"[SUCCESS] Pipeline passed on {branch}", f"All tests passed on branch '{branch}'. Production deploy skipped (not main).", recipients)
        return

    result = subprocess.run(
        ['docker', 'compose', '-p', 'gan-shmuel', 'up', '-d', '--no-deps', 'billing', 'weight'],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    logging.info(f"Production deploy: {result.stdout.strip()}")
    if result.returncode != 0:
        logging.error(f"Production deploy failed: {result.stderr.strip()}")
        send_email(f"[FAIL] Pipeline failed on {branch}", f"Step 5 (prod deploy) failed:\n{result.stderr.strip()}", recipients)
        return

    logging.info("Pipeline finished successfully")
    send_email(f"[SUCCESS] Pipeline passed on {branch}", "All steps completed. Production deployed successfully.", recipients)

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

    if payload.get('action') == 'deleted':
        return jsonify({"status": "ignored", "reason": "branch deleted"}), 200

    thread = threading.Thread(target=run_pipeline, args=(branch,), daemon=True)
    thread.start()
    return jsonify({"status": "triggered", "branch": branch}), 200

if __name__ == '__main__':
    app.run(host=CI_HOST, port=int(CI_PORT))
