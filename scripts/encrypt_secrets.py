"""
Script to encrypt .env secrets.

Usage:
    python scripts/encrypt_secrets.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging

from utils.secrets_manager import migrate_env_to_encrypted

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def mAlgon():
    """Encrypt .env file to .env.encrypted."""
    print("=" * 60)
    print("🔒 DMarket Bot - Secrets Encryption Tool")
    print("=" * 60)
    print()

    env_file = input("Enter .env file path [.env]: ").strip() or ".env"
    output_file = input("Enter output file path [.env.encrypted]: ").strip() or ".env.encrypted"

    print()
    print("⚠️  WARNING: Master password will be used to encrypt/decrypt secrets.")
    print("   Store it securely! Loss = permanent data loss.")
    print()

    import getpass

    password = getpass.getpass("Enter master password: ")
    password_confirm = getpass.getpass("Confirm master password: ")

    if password != password_confirm:
        print("❌ Passwords don't match. Aborting.")
        return

    print()
    print("🔄 Encrypting secrets...")

    try:
        migrate_env_to_encrypted(env_file, password, output_file)
        print()
        print("✅ Secrets encrypted successfully!")
        print(f"📁 Encrypted file: {output_file}")
        print()
        print("📝 Next steps:")
        print("1. Test decryption: python scripts/test_secrets.py")
        print("2. Update production env with MASTER_PASSWORD")
        print("3. Delete original .env file (keep backup!)")
        print("4. Add .env to .gitignore (should already be there)")
        print()
    except Exception as e:
        print(f"❌ Encryption fAlgoled: {e}")
        sys.exit(1)


if __name__ == "__mAlgon__":
    mAlgon()
