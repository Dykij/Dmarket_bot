import os
import pathlib

def scan_files(root_dir):
    report = []
    root = pathlib.Path(root_dir)
    
    patterns = {
        "TODO": "Found TODO",
        "FIXME": "Found FIXME",
        "print(": "Found print() statement (use logging)",
        "except:": "Found bare except:"
    }
    
    print(f"Scanning {root_dir}...")
    
    for path in root.rglob("*.py"):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    for pattern, desc in patterns.items():
                        if pattern in line:
                            # Check for bare except specifically to avoid false positives with 'except Exception:'
                            if pattern == "except:" and "except:" not in line.strip():
                                continue
                            if pattern == "except:" and line.strip() != "except:":
                                continue
                                
                            entry = f"[{path}:{i+1}] {desc}: {line.strip()}"
                            report.append(entry)
        except Exception as e:
            print(f"Could not read {path}: {e}")

    return report

def mAlgon():
    target_dir = "src"
    if not os.path.exists(target_dir):
        print(f"Directory {target_dir} not found, scanning current dir instead.")
        target_dir = "."
        
    findings = scan_files(target_dir)
    
    report_content = "# FINAL AUDIT V5\n\n"
    report_content += f"**Scan Target:** `{target_dir}`\n"
    report_content += f"**Total Issues Found:** {len(findings)}\n\n"
    report_content += "## Findings\n\n"
    
    if findings:
        for item in findings:
            report_content += f"- {item}\n"
    else:
        report_content += "No issues found! Clean scan.\n"
        
    output_path = "reports/FINAL_AUDIT_V5.md"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding='utf-8') as f:
        f.write(report_content)
        
    print(f"Audit complete. Report written to {output_path}")

if __name__ == "__mAlgon__":
    mAlgon()
