import streamlit as st
import os
import time
import subprocess
import glob
from pathlib import Path

# --- Configuration ---
ROOT_DIR = Path(__file__).parent.parent.parent
LOG_FILE = ROOT_DIR / "logs" / "bot.log"
SRC_DIR = ROOT_DIR / "src"

st.set_page_config(
    page_title="DMarket Bot Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Helper Functions ---
def get_bot_status():
    # Check if a python process running main.py exists
    # This is a simplified check for Windows/Linux
    try:
        # Check for 'python' and 'main.py' in process list
        if os.name == 'nt':
            output = subprocess.check_output("tasklist", shell=True).decode()
            return "Running" if "python.exe" in output else "Stopped" # Very basic check
        else:
            output = subprocess.check_output(["pgrep", "-f", "main.py"]).decode()
            return "Running" if output.strip() else "Stopped"
    except subprocess.CalledProcessError:
        return "Stopped"
    except Exception:
        return "Unknown"

def read_logs(n_lines=50):
    if not LOG_FILE.exists():
        return ["Log file not found."]
    
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return lines[-n_lines:]
    except Exception as e:
        return [f"Error reading logs: {e}"]

def build_file_tree(startpath):
    tree = []
    for root, dirs, files in os.walk(startpath):
        level = root.replace(str(startpath), '').count(os.sep)
        indent = ' ' * 4 * (level)
        tree.append(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            tree.append(f"{subindent}{f}")
    return "\n".join(tree)

# --- Sidebar ---
with st.sidebar:
    st.title("🤖 Control Panel")
    
    status = get_bot_status()
    st.metric("Bot Status", status, delta="Active" if status == "Running" else "-Off")
    
    st.divider()
    
    if st.button("Start Bot (Simulation)"):
        st.toast("Bot start sequence initiated...", icon="🚀")
        # In a real scenario, subprocess.Popen(...)
    
    if st.button("Stop Bot"):
        st.toast("Bot stop signal sent.", icon="🛑")

    st.divider()
    st.caption(f"Root: `{ROOT_DIR}`")

# --- Main Content ---
st.title("📊 DMarket Bot Observability")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 Live Logs")
    
    # Auto-refresh logic
    if st.checkbox("Auto-refresh Logs", value=True):
        time.sleep(1)
        st.rerun()

    logs = read_logs()
    log_text = "".join(logs)
    
    st.code(log_text, language="log", line_numbers=True)

with col2:
    st.subheader("📂 Project Structure")
    
    # File Tree Visualizer
    tree_text = build_file_tree(SRC_DIR)
    st.text_area("Source Tree", tree_text, height=600, disabled=True)

# --- Footer ---
st.markdown("---")
st.caption("DMarket Bot Dashboard v0.1 | LangFuse Integration: " + ("Active" if os.environ.get("LANGFUSE_PUBLIC_KEY") else "Inactive"))
