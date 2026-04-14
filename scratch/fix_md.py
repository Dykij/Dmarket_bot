import os
import re

files = [
    r"D:\Dmarket_bot\AGENTS.md",
    r"D:\Dmarket_bot\CHANGELOG.md",
    r"D:\Dmarket_bot\CONTRIBUTING.md",
    r"D:\Dmarket_bot\IDENTITY.md",
    r"D:\Dmarket_bot\README.md",
    r"D:\Dmarket_bot\ROADMAP_DMARKET2026.md",
    r"D:\Dmarket_bot\SECURITY.md",
    r"D:\Dmarket_bot\SOUL.md",
    r"D:\Dmarket_bot\SYSTEM_FLOW.md",
    r"D:\Dmarket_bot\docs\API_COMPLETE_REFERENCE.md",
    r"D:\Dmarket_bot\docs\ARCHITECTURE.md",
    r"D:\Dmarket_bot\docs\deployment.md",
    r"D:\Dmarket_bot\docs\DMARKET_API_FULL_SPEC.md",
    r"D:\Dmarket_bot\docs\QUICK_START.md",
    r"D:\Dmarket_bot\docs\README.md",
    r"D:\Dmarket_bot\docs\SECURITY.md",
    r"D:\Dmarket_bot\docs\STEAM_API_REFERENCE.md",
    r"D:\Dmarket_bot\docs\TELEGRAM_BOT_API.md",
    r"D:\Dmarket_bot\docs\TROUBLESHOOTING.md",
    r"D:\Dmarket_bot\memory\2026-02-22.md",
    r"D:\Dmarket_bot\memory\thinking_log.md",
    r"D:\Dmarket_bot\src\analytics\SKILL_BACKTESTING.md"
]

# We use regex to replace patterns inside words, avoiding standalone "Algo" if it starts a word (like Algorithm)
# But since most are like 'fAlgoled', 'wAlgot', they have lowercase before them.
# The core corruption seems to be 'ai' -> 'Algo', 'ro/ra' -> 'Swarm'.

def regex_replace(content):
    # Rule 1: [a-zA-Z]Algo -> ai
    # We use a lambda to preserve case of the surrounding letters if needed, 
    # but here 'Algo' itself is the target.
    
    # Specific known corrupted patterns (Case-Insensitive)
    patterns = {
        r"awAlgot": "await",
        r"wAlgot": "wait",
        r"pAlgod": "paid",
        r"fAlgoled": "failed",
        r"fAlgols": "fails",
        r"fAlgol": "fail",
        r"detAlgol": "detail",
        r"agAlgon": "again",
        r"rAlgose": "raise",
        r"mAlgon": "main",
        r"dAlgoly": "daily",
        r"trAlgoling": "trailing",
        r"DetAlgoled": "Detailed",
        r"MAlgontenance": "Maintenance",
        r"contAlgon": "contain",
        r"domAlgon": "domain",
        r"remAlgoning": "remaining",
        r"emAlgol": "email",
        r"constrAlgont": "constraint",
        r"AvAlgolable": "Available",
        r"avAlgolable": "available",
        r"Algoolimiter": "RateLimiter", # Special case
        r"Algot": "ait", # generic fallback for 'wait', 'await', etc if not caught
        r"Algon": "ain", # generic fallback for 'main', 'again', etc
        r"Algol": "ail", # generic fallback for 'detail', 'email', etc
        r"Algose": "aise", # generic fallback for 'raise'
        r"настSwarmка": "настройка",
        r"настSwarmках": "настройках",
        r"ВтоSwarm": "Второй",
        r"клавиатуSwarm": "клавиатура",
        r"клавиатуSwarmй": "клавиатурой",
        r"Swarm": "ro" # generic fallback (will handle most Russian words)
    }
    
    for pattern, replacement in patterns.items():
        # Case-insensitive replacement
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
        
    return content

footer = "\n\n----- \n🦅 *DMarket Quantitative Engine | v7.0 | 2026*"

def fix_file(path):
    if not os.path.exists(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Fallback for some windows-encoded files if any
        with open(path, 'r', encoding='windows-1251') as f:
            content = f.read()
    
    # Apply replacements
    content = regex_replace(content)
    
    # Fix Dota 2 / TF2 references in "supported" context (broader search)
    content = re.sub(r"Dota 2, TF2, Rust", "CS2, Rust", content)
    content = re.sub(r"CS:GO, Dota 2, TF2, Rust", "CS2, Rust", content)
    content = re.sub(r"Dota 2, TF2", "CS2, Rust", content) # Avoid listing them
    
    # Update versions and dates
    content = re.sub(r"v[65]\.0", "v7.0", content)
    content = re.sub(r"(Январь|Март|Февраль) 2026", "Апрель 2026", content)
    content = re.sub(r"(January|February|March) 2026", "April 2026", content)
    content = re.sub(r"December 2025", "April 2026", content)
    
    # Add footer if not present
    if "DMarket Quantitative Engine" not in content:
        content += footer
        
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

for f in files:
    print(f"Fixing {f}...")
    fix_file(f)
