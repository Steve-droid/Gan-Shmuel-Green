import hashlib
import hmac
import os

#github webhook secret for verifying payloads
#and is loaded by systemd when starting the service 
#encode() means we are converting the string to bytes, which is required for the HMAC calculation
SECRET=os.environ.get('GITHUB_WEBHOOK_SECRET', '').encode()

def verify_github_signature(request)->bool:
    # Placeholder for GitHub signature verification logic
    # You would typically use the 'X-Hub-Signature-256' header and your webhook secret to verify the payload
    signature = request.headers.get('X-Hub-Signature-256', '')
    if not signature.startswith('sha256='):
        return False
    payload = request.get_data()

    expected_signature = 'sha256=' + hmac.new(
        SECRET,
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)
    
def authenticate(request):
    
    return verify_github_signature(request)