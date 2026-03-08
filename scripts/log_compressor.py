import os
import glob
import sys

# Ensure project root is in path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import src.rust_core as rust
    checksum_func = rust.validate_checksum
    print("Using Rust-optimized checksum validation.")
except ImportError:
    import hashlib
    def checksum_func(line):
        return hashlib.md5(line.encode()).hexdigest()
    print("Using slow Python fallback (hashlib).")


def compress_logs():
    """Reads all log files, deduplicates lines, and compresses output."""
    log_files = glob.glob('logs/*.log')
    all_lines = []

    for log_file in log_files:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines.extend(f.readlines())
        except Exception as e:
            print(f"Error reading {log_file}: {e}")
            continue

    # Deduplicate lines while preserving order
    seen_hashes = set()
    unique_lines = []
    for line in all_lines:
        line_hash = checksum_func(line)
        if line_hash not in seen_hashes:
            seen_hashes.add(line_hash)
            unique_lines.append(line)

    # Join lines
    content = "".join(unique_lines)

    # Limit to last 50,000 characters
    limit = 50000
    if len(content) > limit:
        content = content[-limit:]
        # Try to cut at a newline to be cleaner
        first_newline = content.find('\n')
        if first_newline != -1:
            content = content[first_newline + 1:]

    output_path = 'logs/compressed_context.md'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Compressed Log Context\n\n")
            f.write(content)
        print(f"Successfully compressed logs to {output_path}")
    except Exception as e:
        print(f"Error writing to {output_path}: {e}")


if __name__ == "__main__":
    compress_logs()
