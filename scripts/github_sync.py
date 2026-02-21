import shutil
from pathlib import Path
import datetime

def sync_wiki():
    source = Path("src/knowledge_base")
    dest = Path("docs/wiki_staging")
    dest.mkdir(parents=True, exist_ok=True)
    
    for file in source.glob("*.md"):
        shutil.copy(file, dest / file.name)
        print(f"✅ Synced: {file.name}")
        
    print(f"🔄 Wiki Sync Complete at {datetime.datetime.now()}")

if __name__ == "__main__":
    sync_wiki()
