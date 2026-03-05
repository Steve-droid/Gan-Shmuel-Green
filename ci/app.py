from flask import Flask, request, jsonify                                                                                                                                                         
import subprocess                                                                                                                                                                                 
import threading                                                                                                                                                                                  
import os                                                                                                                                                                                         
import logging
import time

# Configure the global logging system
logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s [%(levelname)s] %(message)s'
  )

app = Flask(__name__)                                                                                                                                                                                                                       
REPO_DIR = os.environ.get('REPO_DIR', '/repo')

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
        return
    
   

    # Step 5: Deploy to production
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

@app.route('/health', methods=['GET'])
def health():
    return 'OK', 200


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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8085)