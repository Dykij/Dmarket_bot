import shutil
from pathlib import Path
import datetime
import os

# Simulated GitHub API Integration (Requires PAT/App Token)
# TODO: Integrate with 'requests' and GitHub REST API using tokens from .env

def sync_wiki():
    """
    Syncs local knowledge_base markdown files to a staging directory
    ready for pushing to the .wiki.git repository.
    """
    source = Path("src/knowledge_base")
    dest = Path("dist/wiki_staging")
    dest.mkdir(parents=True, exist_ok=True)
    
    synced_count = 0
    for file in source.glob("*.md"):
        shutil.copy(file, dest / file.name)
        synced_count += 1
        
    print(f"✅ Wiki Sync: Staged {synced_count} files to {dest}")

def create_issue_on_crash(log_file):
    """
    Parses a log file for CRITICAL errors and simulates creating a GitHub Issue.
    """
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "CRITICAL" in content or "FATAL" in content:
                print(f"🚨 CRASH DETECTED in {log_file}. Creating GitHub Issue...")
                # Real implementation would POST to /repos/:owner/:repo/issues
                print("✅ GitHub Issue Created (Simulated): 'Bot Crash Report'")
            else:
                print(f"✅ No crashes found in {log_file}.")
    except FileNotFoundError:
        print(f"⚠️ Log file not found: {log_file}")

if __name__ == "__main__":
    sync_wiki()
    # Simulated check
    create_issue_on_crash("logs/bot.log")
