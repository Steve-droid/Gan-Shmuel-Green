from flask import Flask, request, jsonify                                                                                                                                                         
import subprocess                                                                                                                                                                                 
import threading                                                                                                                                                                                  
import os                                                                                                                                                                                         
import logging  

# Configure the global logging system
logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s [%(levelname)s] %(message)s'
  )

app = Flask(__name__)                                                                                                                                                                                                                       
REPO_DIR = os.environ.get('REPO_DIR', '/repo')

def run_pipeline(branch):
    commands = [
        ['git', 'fetch', 'origin', branch],
        ['git', 'checkout', branch],
        ['git', 'reset', '--hard', f'origin/{branch}'],
        ['docker', 'compose', 'build'],
        #['docker', 'compose', 'up', '-d', '--no-deps', 'billing', 'weight'],
    ]

    for cmd in commands:
        result = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True)
        logging.info(f"{' '.join(cmd)}: {result.stdout.strip()}")
        if result.returncode != 0:
            logging.error(f"Failed: {result.stderr.strip()}")
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