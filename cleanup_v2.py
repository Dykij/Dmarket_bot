import os
import shutil
import re
from pathlib import Path

# Config
BASE_DIR = Path(r"D:\Dmarket_bot\src\dmarket")
LEGACY_DIR = BASE_DIR / "_legacy_"
SCANNER_DIR = BASE_DIR / "scanner"

# 1. Setup Legacy Dir
LEGACY_DIR.mkdir(exist_ok=True)

# 2. Move Orchestrators
files_to_move = ["hft_mode.py", "auto_trader.py"]
for f_name in files_to_move:
    src = BASE_DIR / f_name
    dst = LEGACY_DIR / f_name
    if src.exists():
        shutil.move(src, dst)
        print(f"Moved {f_name} to _legacy_")

# 3. Clean Scanners (Keep aggregated_scanner.py)
if SCANNER_DIR.exists():
    for item in SCANNER_DIR.glob("*.py"):
        if item.name not in ["aggregated_scanner.py", "__init__.py"]:
            dst = LEGACY_DIR / f"scanner_{item.name}"
            shutil.move(item, dst)
            print(f"Moved scanner/{item.name} to _legacy_")

# 4. Remove Hardcoded Markup (1.15 / 15.0)
# We will do a safe replace in key files only to avoid breaking float logic elsewhere
target_files = [
    BASE_DIR / "autopilot_orchestrator.py",
    BASE_DIR / "auto_seller.py",
    BASE_DIR / "price_analyzer.py"
]

for file_path in target_files:
    if file_path.exists():
        content = file_path.read_text("utf-8")
        # Replace fixed markup with dynamic variable placeholder or method call
        # Simple string replacement for common patterns
        new_content = re.sub(r'(\s*=\s*)1\.15', r'\1self.dynamic_markup', content)
        new_content = re.sub(r'(\s*=\s*)15\.0', r'\1self.dynamic_markup * 10', content) # Context dependent
        
        if content != new_content:
            file_path.write_text(new_content, "utf-8")
            print(f"Patched hardcoded values in {file_path.name}")

print("Cleanup Complete.")
