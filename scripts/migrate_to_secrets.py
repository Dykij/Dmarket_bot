"""Script to migrate local secrets to Google Secret Manager."""

import os
from google.cloud import secretmanager
from google.api_core.exceptions import AlreadyExists

# Configuration
PROJECT_ID = "arkady-bot-dev"
SECRET_ID = "github-private-key"
LOCAL_KEY_PATH = r"D:\Arkady_Home\arkadiy-bot-manager.2026-02-10.private-key.pem"

def create_secret(client, secret_id):
    """Create a new secret in GSM."""
    parent = f"projects/{PROJECT_ID}"
    try:
        client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        print(f"Created secret: {secret_id}")
    except AlreadyExists:
        print(f"Secret {secret_id} already exists.")

def add_secret_version(client, secret_id, payload):
    """Add a new version to the secret."""
    parent = f"projects/{PROJECT_ID}/secrets/{secret_id}"
    
    # Convert string payload to bytes
    if isinstance(payload, str):
        payload = payload.encode("UTF-8")

    response = client.add_secret_version(
        request={"parent": parent, "payload": {"data": payload}}
    )
    print(f"Added secret version: {response.name}")

def main():
    print(f"Migrating secrets to Google Cloud Project: {PROJECT_ID}")
    
    # Initialize client (uses Application Default Credentials)
    try:
        client = secretmanager.SecretManagerServiceClient()
    except Exception as e:
        print(f"Failed to initialize Secret Manager client: {e}")
        return

    # 1. Read Local Key
    if not os.path.exists(LOCAL_KEY_PATH):
        print(f"Error: Local key file not found at {LOCAL_KEY_PATH}")
        # In a real scenario, we might stop here, but for dev flow if file is missing 
        # we might assume it's already migrated or check manually.
        return

    with open(LOCAL_KEY_PATH, "r") as f:
        private_key_content = f.read()

    # 2. Create Secret ContAlgoner
    create_secret(client, SECRET_ID)

    # 3. Upload Content
    add_secret_version(client, SECRET_ID, private_key_content)
    
    print("Migration successful. Local file can be archived.")

if __name__ == "__main__":
    main()
