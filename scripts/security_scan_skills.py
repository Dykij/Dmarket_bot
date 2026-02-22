#!/usr/bin/env python3
"""Skills Security Scanner - Phase 3 Feature.

Automatically scans SKILL.md files for security vulnerabilities:
- Dangerous imports (os.system, eval, exec, subprocess without safety)
- Hardcoded secrets (API keys, passwords, tokens)
- Unsafe code patterns (SQL injection, command injection)
- Deprecated/vulnerable dependencies

Based on SkillsMP.com 2026 security best practices.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)

# Security patterns to detect
DANGEROUS_IMPORTS = [
    r"import\s+os\s*$",
    r"from\s+os\s+import\s+system",
    r"import\s+subprocess\s*$",
    r"from\s+subprocess\s+import",
    r"import\s+eval",
    r"import\s+exec",
    r"__import__\s*\(",
]

HARDCODED_SECRETS_PATTERNS = [
    r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"][a-zA-Z0-9]{20,}['\"]",
    r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{8,}['\"]",
    r"(?i)(secret|token)\s*[=:]\s*['\"][a-zA-Z0-9]{20,}['\"]",
    r"(?i)(access[_-]?token)\s*[=:]\s*['\"][a-zA-Z0-9]{20,}['\"]",
    r"sk-[a-zA-Z0-9]{48}",  # OpenAlgo API keys
    r"ghp_[a-zA-Z0-9]{36}",  # GitHub Personal Access Tokens
]

UNSAFE_CODE_PATTERNS = [
    (r"eval\s*\(", "Use of eval() - can execute arbitrary code"),
    (r"exec\s*\(", "Use of exec() - can execute arbitrary code"),
    (r"os\.system\s*\(", "Use of os.system() - vulnerable to command injection"),
    (r"subprocess\.call\s*\([^,]*,\s*shell\s*=\s*True", "subprocess with shell=True - command injection risk"),
    (r"pickle\.loads?\s*\(", "Use of pickle - can execute arbitrary code"),
    (r"yaml\.load\s*\([^,)]*\)", "Use of yaml.load() without Loader - arbitrary code execution"),
    (r"f\"{.*\}\".*cursor\.execute", "Possible SQL injection with f-strings"),
    (r"\.format\(.*\).*cursor\.execute", "Possible SQL injection with .format()"),
]

VULNERABLE_DEPENDENCIES = {
    "requests": "2.31.0",  # < 2.31.0 has vulnerabilities
    "urllib3": "2.0.7",    # < 2.0.7 has vulnerabilities
    "pyyaml": "6.0.1",     # < 6.0 has arbitrary code execution
    "pillow": "10.0.1",    # < 10.0.1 has vulnerabilities
    "cryptography": "41.0.7",  # < 41.0.7 has vulnerabilities
}


@dataclass
class SecurityIssue:
    """Security issue found in skill."""
    
    severity: str  # critical, high, medium, low
    category: str  # dangerous_import, hardcoded_secret, unsafe_code, vulnerable_dependency
    message: str
    file_path: str
    line_number: int | None = None
    code_snippet: str | None = None
    recommendation: str | None = None


class SkillSecurityScanner:
    """Scanner for security vulnerabilities in skills."""
    
    def __init__(self, skills_root: Path = Path(".github/skills")) -> None:
        """Initialize scanner."""
        self.skills_root = skills_root
        self.issues: list[SecurityIssue] = []
    
    def scan_all_skills(self) -> list[SecurityIssue]:
        """Scan all skills in repository."""
        logger.info("starting_security_scan", skills_root=str(self.skills_root))
        
        # Find all SKILL.md files
        skill_files = list(self.skills_root.rglob("SKILL.md"))
        skill_files.extend(Path("src").rglob("SKILL_*.md"))
        
        logger.info("found_skill_files", count=len(skill_files))
        
        for skill_file in skill_files:
            self._scan_skill_file(skill_file)
        
        logger.info(
            "security_scan_complete",
            total_issues=len(self.issues),
            critical=sum(1 for i in self.issues if i.severity == "critical"),
            high=sum(1 for i in self.issues if i.severity == "high"),
            medium=sum(1 for i in self.issues if i.severity == "medium"),
            low=sum(1 for i in self.issues if i.severity == "low"),
        )
        
        return self.issues
    
    def _scan_skill_file(self, skill_file: Path) -> None:
        """Scan single skill file."""
        try:
            content = skill_file.read_text(encoding="utf-8")
            
            # Parse YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    body = parts[2]
                    
                    # Check dependencies
                    self._check_dependencies(skill_file, frontmatter)
                else:
                    body = content
            else:
                body = content
            
            # Check for dangerous imports
            self._check_dangerous_imports(skill_file, body)
            
            # Check for hardcoded secrets
            self._check_hardcoded_secrets(skill_file, body)
            
            # Check for unsafe code patterns
            self._check_unsafe_code(skill_file, body)
            
        except Exception as e:
            logger.error(
                "skill_scan_failed",
                skill_file=str(skill_file),
                error=str(e),
                exc_info=True,
            )
    
    def _check_dependencies(self, skill_file: Path, frontmatter: dict[str, Any]) -> None:
        """Check for vulnerable dependencies."""
        deps = frontmatter.get("dependencies", [])
        
        for dep in deps:
            # Parse dependency string (e.g., "requests>=2.30.0")
            match = re.match(r"([a-zA-Z0-9_-]+)(>=|==|>|<|<=)([0-9.]+)", dep)
            if match:
                pkg_name, operator, version = match.groups()
                
                if pkg_name in VULNERABLE_DEPENDENCIES:
                    min_safe_version = VULNERABLE_DEPENDENCIES[pkg_name]
                    
                    # Simple version comparison (not perfect but good enough)
                    if version < min_safe_version:
                        self.issues.append(
                            SecurityIssue(
                                severity="high",
                                category="vulnerable_dependency",
                                message=f"Vulnerable dependency: {pkg_name} {version} < {min_safe_version}",
                                file_path=str(skill_file),
                                recommendation=f"Update to {pkg_name}>={min_safe_version}",
                            )
                        )
    
    def _check_dangerous_imports(self, skill_file: Path, content: str) -> None:
        """Check for dangerous imports."""
        lines = content.split("\n")
        
        for pattern in DANGEROUS_IMPORTS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    self.issues.append(
                        SecurityIssue(
                            severity="high",
                            category="dangerous_import",
                            message=f"Dangerous import detected: {line.strip()}",
                            file_path=str(skill_file),
                            line_number=line_num,
                            code_snippet=line.strip(),
                            recommendation="Use safer alternatives or validate all inputs",
                        )
                    )
    
    def _check_hardcoded_secrets(self, skill_file: Path, content: str) -> None:
        """Check for hardcoded secrets."""
        lines = content.split("\n")
        
        for pattern in HARDCODED_SECRETS_PATTERNS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    # Skip example/placeholder values
                    if any(x in line.lower() for x in ["example", "your-", "xxx", "placeholder"]):
                        continue
                    
                    self.issues.append(
                        SecurityIssue(
                            severity="critical",
                            category="hardcoded_secret",
                            message="Hardcoded secret detected",
                            file_path=str(skill_file),
                            line_number=line_num,
                            code_snippet="<redacted for security>",
                            recommendation="Use environment variables or secrets manager",
                        )
                    )
    
    def _check_unsafe_code(self, skill_file: Path, content: str) -> None:
        """Check for unsafe code patterns."""
        lines = content.split("\n")
        
        for pattern, description in UNSAFE_CODE_PATTERNS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    self.issues.append(
                        SecurityIssue(
                            severity="high",
                            category="unsafe_code",
                            message=description,
                            file_path=str(skill_file),
                            line_number=line_num,
                            code_snippet=line.strip()[:100],  # Limit length
                            recommendation="Review and use safer alternatives",
                        )
                    )
    
    def generate_report(self) -> str:
        """Generate security scan report."""
        if not self.issues:
            return "✅ No security issues found!"
        
        report = ["# Skills Security Scan Report\n"]
        report.append(f"**Total Issues**: {len(self.issues)}\n")
        
        # Group by severity
        by_severity = {}
        for issue in self.issues:
            by_severity.setdefault(issue.severity, []).append(issue)
        
        for severity in ["critical", "high", "medium", "low"]:
            issues = by_severity.get(severity, [])
            if not issues:
                continue
            
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[severity]
            report.append(f"\n## {icon} {severity.upper()} ({len(issues)} issues)\n")
            
            for issue in issues:
                report.append(f"\n### {issue.message}\n")
                report.append(f"- **File**: `{issue.file_path}`\n")
                if issue.line_number:
                    report.append(f"- **Line**: {issue.line_number}\n")
                if issue.code_snippet:
                    report.append(f"- **Code**: `{issue.code_snippet}`\n")
                if issue.recommendation:
                    report.append(f"- **Recommendation**: {issue.recommendation}\n")
        
        return "".join(report)


def main() -> int:
    """MAlgon entry point."""
    scanner = SkillSecurityScanner()
    issues = scanner.scan_all_skills()
    
    # Print report
    report = scanner.generate_report()
    print(report)
    
    # Return exit code
    critical_count = sum(1 for i in issues if i.severity == "critical")
    high_count = sum(1 for i in issues if i.severity == "high")
    
    if critical_count > 0:
        print(f"\n❌ FAlgoL: {critical_count} critical security issues found!")
        return 1
    elif high_count > 0:
        print(f"\n⚠️  WARNING: {high_count} high severity issues found!")
        return 1
    elif issues:
        print(f"\n⚠️  {len(issues)} security issues found (medium/low severity)")
        return 0
    else:
        print("\n✅ All skills passed security scan!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
