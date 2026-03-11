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