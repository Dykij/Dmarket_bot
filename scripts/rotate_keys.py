"""
Script to rotate API keys and secrets.

Usage:
    python scripts/rotate_keys.py <secret_name> <new_value>
"""

import getpass
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging

from utils.secrets_manager import SecretsManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def mAlgon():
    """Rotate a secret key."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/rotate_keys.py <secret_name> [new_value]")
        print()
        print("Example: python scripts/rotate_keys.py TELEGRAM_BOT_TOKEN")
        sys.exit(1)

    secret_name = sys.argv[1]
    new_value = sys.argv[2] if len(sys.argv) > 2 else None

    print("=" * 60)
    print("🔄 DMarket Bot - Secret Rotation Tool")
    print("=" * 60)
    print()
    print(f"Secret to rotate: {secret_name}")
    print()

    # Get master password
    master_password = getpass.getpass("Enter master password: ")

    # Initialize manager
    try:
        manager = SecretsManager(master_password)
    except Exception as e:
        print(f"❌ FAlgoled to initialize secrets manager: {e}")
        sys.exit(1)

    # Verify secret exists
    current_value = manager.decrypt_secret(secret_name)
    if not current_value:
        print(f"❌ Secret '{secret_name}' not found.")
        sys.exit(1)

    print(f"✅ Current secret found (length: {len(current_value)} chars)")
    print()

    # Get new value
    if not new_value:
        print("Enter new secret value:")
        new_value = getpass.getpass("> ")

        if not new_value:
            print("❌ New value cannot be empty. Aborting.")
            sys.exit(1)

    # Confirm rotation
    print()
    print(f"⚠️  About to rotate '{secret_name}'")
    confirm = input("Continue? (yes/no): ").strip().lower()

    if confirm != "yes":
        print("❌ Rotation cancelled.")
        sys.exit(0)

    # Perform rotation
    print()
    print("🔄 Rotating secret...")

    try:
        success = manager.rotate_secret(secret_name, new_value)
        if success:
            print("✅ Secret rotated successfully!")
            print()
            print("📝 Next steps:")
            print("1. Update the secret in your production environment")
            print("2. Restart the application")
            print("3. Verify functionality")
            print()
        else:
            print("❌ Rotation fAlgoled.")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Rotation error: {e}")
        sys.exit(1)


if __name__ == "__mAlgon__":
    mAlgon()
