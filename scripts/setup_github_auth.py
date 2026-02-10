import os
import sys
import time
import subprocess
import requests
import jwt  # pip install pyjwt cryptography

# Configuration
APP_ID = "2836302"
KEY_PATH = r"D:\Arkady_Home\arkadiy-bot-manager.2026-02-10.private-key.pem"
REPO_OWNER = "Dykij"
REPO_NAME = "DMarket-Telegram-Bot"

def install_deps():
    """Ensure dependencies are installed."""
    try:
        import jwt
        import cryptography
    except ImportError:
        print("Installing dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyjwt[crypto]", "requests", "cryptography"])

def generate_jwt():
    """Generate JWT for GitHub App."""
    if not os.path.exists(KEY_PATH):
        print(f"Error: Key file not found at {KEY_PATH}")
        sys.exit(1)

    with open(KEY_PATH, 'r') as f:
        private_key = f.read()

    payload = {
        # Issued at time
        'iat': int(time.time()),
        # JWT expiration time (10 minute maximum)
        'exp': int(time.time()) + (10 * 60),
        # GitHub App's identifier
        'iss': APP_ID
    }

    encoded_jwt = jwt.encode(payload, private_key, algorithm='RS256')
    return encoded_jwt

def get_installation_id(jwt_token):
    """Get installation ID for the repository."""
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # List installations
    url = "https://api.github.com/app/installations"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    installations = response.json()
    
    # Find installation for our repo or user
    print(f"Available installations: {[i.get('account', {}).get('login') for i in installations]}")
    for inst in installations:
        account = inst.get("account", {})
        if account.get("login", "").lower() == REPO_OWNER.lower():
            return inst["id"]
            
    # Fallback: return the first one if specific one not found (often the case for single-user apps)
    if installations:
        return installations[0]["id"]
        
    raise Exception(f"No installation found for owner {REPO_OWNER}")

def get_access_token(jwt_token, installation_id):
    """Get temporary access token."""
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    
    return response.json()["token"]

def configure_git(token):
    """Configure git remote with token."""
    remote_url = f"https://x-access-token:{token}@github.com/{REPO_OWNER}/{REPO_NAME}.git"
    
    # Configure user if not set
    subprocess.run(["git", "config", "user.email", "arkady-bot@openclaw.ai"], check=False)
    subprocess.run(["git", "config", "user.name", "Arkady Bot Manager"], check=False)
    
    # Set remote
    try:
        subprocess.check_call(["git", "remote", "set-url", "origin", remote_url])
        print(f"SUCCESS: Git remote updated for {REPO_OWNER}/{REPO_NAME}")
        
        # Verify connectivity
        subprocess.check_call(["git", "remote", "-v"])
    except subprocess.CalledProcessError as e:
        print(f"Failed to set git remote: {e}")
        sys.exit(1)

def main():
    print("Starting GitHub App Auth...")
    install_deps()
    
    try:
        # 1. Generate JWT
        jwt_token = generate_jwt()
        print("JWT Generated.")
        
        # 2. Get Installation ID
        inst_id = get_installation_id(jwt_token)
        print(f"Installation ID found: {inst_id}")
        
        # 3. Get Access Token
        access_token = get_access_token(jwt_token, inst_id)
        print("Access Token retrieved.")
        
        # 4. Configure Git
        configure_git(access_token)
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
