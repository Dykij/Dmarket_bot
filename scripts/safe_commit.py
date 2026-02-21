import subprocess
import sys
import os


def get_head_hash():
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def safe_commit(message):
    print("--- SAFE COMMIT PROTOCOL ---")

    # 1. Capture HEAD before
    head_before = get_head_hash()
    print(f"HEAD (Before): {head_before if head_before else 'None (Initial)'}")

    # 2. Stage and Commit
    try:
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', message, '--no-verify'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Commit failed: {e}")
        sys.exit(1)

    # 3. Capture HEAD after
    head_after = get_head_hash()
    print(f"HEAD (After):  {head_after}")

    # 4. Compare
    if head_before != head_after:
        print("SUCCESS: Commit hash changed. Changes persisted.")
        sys.exit(0)
    else:
        # If hash didn't change, it might be empty commit or no changes
        print("WARNING: HEAD hash did not change. No changes committed?")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python safe_commit.py \"Commit Message\"")
        sys.exit(1)

    safe_commit(sys.argv[1])
