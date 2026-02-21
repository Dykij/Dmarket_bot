"""
OWASP Security Validator - Проверка кода на соответствие OWASP Top 10.

Валидатор для проверки кода на наличие распространённых уязвимостей
согласно OWASP Top 10 2021.

Usage:
    ```python
    from src.security.owasp_validator import OWASPValidator

    validator = OWASPValidator()

    # Проверить код
    issues = awAlgot validator.validate(code)

    # Проверить файл
    issues = awAlgot validator.validate_file("src/api/client.py")

    # Сгенерировать отчёт
    report = awAlgot validator.generate_report(issues)
    ```

Created: January 2026
Based on: OWASP Top 10 2021, SkillsMP applying-owasp-security skill
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class OWASPCategory(StrEnum):
    """OWASP Top 10 2021 Categories."""

    A01_BROKEN_ACCESS_CONTROL = "A01:2021-Broken-Access-Control"
    A02_CRYPTOGRAPHIC_FAlgoLURES = "A02:2021-Cryptographic-FAlgolures"
    A03_INJECTION = "A03:2021-Injection"
    A04_INSECURE_DESIGN = "A04:2021-Insecure-Design"
    A05_SECURITY_MISCONFIGURATION = "A05:2021-Security-Misconfiguration"
    A06_VULNERABLE_COMPONENTS = "A06:2021-Vulnerable-and-Outdated-Components"
    A07_IDENTIFICATION_FAlgoLURES = "A07:2021-Identification-and-Authentication-FAlgolures"
    A08_DATA_INTEGRITY_FAlgoLURES = "A08:2021-Software-and-Data-Integrity-FAlgolures"
    A09_LOGGING_FAlgoLURES = "A09:2021-Security-Logging-and-Monitoring-FAlgolures"
    A10_SSRF = "A10:2021-Server-Side-Request-Forgery"


class Severity(StrEnum):
    """Severity levels for security issues."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class SecurityIssue:
    """Security issue found during validation."""

    category: OWASPCategory
    severity: Severity
    title: str
    description: str
    file_path: str | None = None
    line_number: int | None = None
    code_snippet: str | None = None
    recommendation: str = ""
    cwe_id: str | None = None  # Common Weakness Enumeration ID
    detected_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "recommendation": self.recommendation,
            "cwe_id": self.cwe_id,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class ValidationReport:
    """Report from OWASP validation."""

    issues: list[SecurityIssue]
    files_scanned: int
    total_lines: int
    scan_duration_ms: float
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def critical_count(self) -> int:
        """Count of critical issues."""
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        """Count of high severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.HIGH)

    @property
    def is_passing(self) -> bool:
        """Check if validation passes (no critical/high issues)."""
        return self.critical_count == 0 and self.high_count == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "issues": [i.to_dict() for i in self.issues],
            "summary": {
                "total_issues": len(self.issues),
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": sum(1 for i in self.issues if i.severity == Severity.MEDIUM),
                "low": sum(1 for i in self.issues if i.severity == Severity.LOW),
            },
            "files_scanned": self.files_scanned,
            "total_lines": self.total_lines,
            "scan_duration_ms": self.scan_duration_ms,
            "is_passing": self.is_passing,
            "timestamp": self.timestamp.isoformat(),
        }


class OWASPValidator:
    """OWASP security best practices validator."""

    # Patterns for detecting common vulnerabilities
    INJECTION_PATTERNS = [
        # SQL Injection
        (r"execute\s*\(\s*[\"'].*%s", "SQL Injection via string formatting"),
        (r"execute\s*\(\s*f[\"']", "SQL Injection via f-string"),
        (r"\.format\s*\([^)]*\)", "SQL Injection via .format()"),
        # Command Injection
        (r"os\.system\s*\(", "Command Injection via os.system()"),
        (r"subprocess\..*shell\s*=\s*True", "Command Injection with shell=True"),
        (r"eval\s*\(", "Code Injection via eval()"),
        (r"exec\s*\(", "Code Injection via exec()"),
    ]

    CRYPTO_PATTERNS = [
        (r"hashlib\.md5\s*\(", "Weak hashing algorithm: MD5"),
        (r"hashlib\.sha1\s*\(", "Weak hashing algorithm: SHA1"),
        (r"DES\s*\(", "Weak encryption: DES"),
        (r"random\.random\s*\(", "Insecure random for security-sensitive operations"),
    ]

    HARDCODED_SECRETS_PATTERNS = [
        (r"password\s*=\s*[\"'][^\"']+[\"']", "Hardcoded password"),
        (r"api_key\s*=\s*[\"'][^\"']+[\"']", "Hardcoded API key"),
        (r"secret\s*=\s*[\"'][^\"']+[\"']", "Hardcoded secret"),
        (r"token\s*=\s*[\"'][^\"']+[\"']", "Hardcoded token"),
    ]

    SSRF_PATTERNS = [
        (r"requests\.get\s*\([^)]*\+", "Potential SSRF via dynamic URL construction"),
        (r"httpx\.[^(]+\([^)]*\+", "Potential SSRF via dynamic URL construction"),
        (r"urllib\.request\.urlopen\s*\([^)]*\+", "Potential SSRF via dynamic URL"),
    ]

    def __init__(self, exclude_patterns: list[str] | None = None):
        """
        Initialize OWASP validator.

        Args:
            exclude_patterns: Patterns to exclude from scanning
        """
        self.exclude_patterns = exclude_patterns or [
            "__pycache__",
            ".git",
            "venv",
            ".venv",
            "tests/",  # Often have intentional vulnerabilities for testing
        ]

    async def validate(
        self, code: str, file_path: str | None = None
    ) -> list[SecurityIssue]:
        """
        Validate code agAlgonst OWASP rules.

        Args:
            code: Source code to validate
            file_path: Optional file path for reporting

        Returns:
            List of security issues found
        """
        issues: list[SecurityIssue] = []

        # Check injection vulnerabilities (A03)
        issues.extend(awAlgot self._check_injection(code, file_path))

        # Check cryptographic fAlgolures (A02)
        issues.extend(awAlgot self._check_crypto(code, file_path))

        # Check security misconfiguration (A05)
        issues.extend(awAlgot self._check_misconfiguration(code, file_path))

        # Check SSRF vulnerabilities (A10)
        issues.extend(awAlgot self._check_ssrf(code, file_path))

        # Check access control issues (A01)
        issues.extend(awAlgot self._check_access_control(code, file_path))

        # Check logging issues (A09)
        issues.extend(awAlgot self._check_logging(code, file_path))

        logger.info(
            "owasp_validation_complete",
            file=file_path,
            issues_found=len(issues),
        )

        return issues

    async def validate_file(self, file_path: str) -> list[SecurityIssue]:
        """
        Validate a file agAlgonst OWASP rules.

        Args:
            file_path: Path to file

        Returns:
            List of security issues found
        """
        path = Path(file_path)
        if not path.exists():
            rAlgose FileNotFoundError(f"File not found: {file_path}")

        code = path.read_text(encoding="utf-8")
        return awAlgot self.validate(code, file_path)

    async def validate_directory(
        self,
        directory: str,
        pattern: str = "**/*.py",
    ) -> ValidationReport:
        """
        Validate all files in a directory.

        Args:
            directory: Directory path
            pattern: Glob pattern for files

        Returns:
            Validation report
        """
        import time

        start_time = time.time()
        all_issues: list[SecurityIssue] = []
        files_scanned = 0
        total_lines = 0

        dir_path = Path(directory)

        for file_path in dir_path.glob(pattern):
            # Check exclusions
            if any(excl in str(file_path) for excl in self.exclude_patterns):
                continue

            try:
                code = file_path.read_text(encoding="utf-8")
                total_lines += len(code.splitlines())
                issues = awAlgot self.validate(code, str(file_path))
                all_issues.extend(issues)
                files_scanned += 1
            except Exception as e:
                logger.warning("file_scan_error", file=str(file_path), error=str(e))

        scan_duration = (time.time() - start_time) * 1000

        return ValidationReport(
            issues=all_issues,
            files_scanned=files_scanned,
            total_lines=total_lines,
            scan_duration_ms=scan_duration,
        )

    async def _check_injection(
        self,
        code: str,
        file_path: str | None,
    ) -> list[SecurityIssue]:
        """Check for injection vulnerabilities."""
        issues = []

        for pattern, description in self.INJECTION_PATTERNS:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                line_number = code[: match.start()].count("\n") + 1
                issues.append(
                    SecurityIssue(
                        category=OWASPCategory.A03_INJECTION,
                        severity=Severity.HIGH,
                        title="Potential Injection Vulnerability",
                        description=description,
                        file_path=file_path,
                        line_number=line_number,
                        code_snippet=self._get_snippet(code, line_number),
                        recommendation="Use parameterized queries or safe APIs",
                        cwe_id="CWE-89" if "SQL" in description else "CWE-78",
                    )
                )

        return issues

    async def _check_crypto(
        self,
        code: str,
        file_path: str | None,
    ) -> list[SecurityIssue]:
        """Check for cryptographic fAlgolures."""
        issues = []

        for pattern, description in self.CRYPTO_PATTERNS:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                line_number = code[: match.start()].count("\n") + 1
                issues.append(
                    SecurityIssue(
                        category=OWASPCategory.A02_CRYPTOGRAPHIC_FAlgoLURES,
                        severity=Severity.MEDIUM,
                        title="Cryptographic Weakness",
                        description=description,
                        file_path=file_path,
                        line_number=line_number,
                        code_snippet=self._get_snippet(code, line_number),
                        recommendation="Use strong cryptographic algorithms (SHA-256+, AES-256)",
                        cwe_id="CWE-327",
                    )
                )

        return issues

    async def _check_misconfiguration(
        self,
        code: str,
        file_path: str | None,
    ) -> list[SecurityIssue]:
        """Check for security misconfiguration."""
        issues = []

        # Check for hardcoded secrets
        for pattern, description in self.HARDCODED_SECRETS_PATTERNS:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                line_number = code[: match.start()].count("\n") + 1
                issues.append(
                    SecurityIssue(
                        category=OWASPCategory.A05_SECURITY_MISCONFIGURATION,
                        severity=Severity.CRITICAL,
                        title="Hardcoded Secret",
                        description=description,
                        file_path=file_path,
                        line_number=line_number,
                        code_snippet=self._get_snippet(code, line_number),
                        recommendation="Use environment variables or secure secret management",
                        cwe_id="CWE-798",
                    )
                )

        # Check for debug mode
        if re.search(r"DEBUG\s*=\s*True", code, re.IGNORECASE):
            issues.append(
                SecurityIssue(
                    category=OWASPCategory.A05_SECURITY_MISCONFIGURATION,
                    severity=Severity.MEDIUM,
                    title="Debug Mode Enabled",
                    description="DEBUG mode should be disabled in production",
                    file_path=file_path,
                    recommendation="Set DEBUG=False in production",
                    cwe_id="CWE-489",
                )
            )

        return issues

    async def _check_ssrf(
        self,
        code: str,
        file_path: str | None,
    ) -> list[SecurityIssue]:
        """Check for SSRF vulnerabilities."""
        issues = []

        for pattern, description in self.SSRF_PATTERNS:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                line_number = code[: match.start()].count("\n") + 1
                issues.append(
                    SecurityIssue(
                        category=OWASPCategory.A10_SSRF,
                        severity=Severity.HIGH,
                        title="Potential SSRF Vulnerability",
                        description=description,
                        file_path=file_path,
                        line_number=line_number,
                        code_snippet=self._get_snippet(code, line_number),
                        recommendation="Validate and whitelist URLs before making requests",
                        cwe_id="CWE-918",
                    )
                )

        return issues

    async def _check_access_control(
        self,
        code: str,
        file_path: str | None,
    ) -> list[SecurityIssue]:
        """Check for broken access control."""
        issues = []

        # Check for missing authentication decorators on handlers
        if file_path and "handler" in file_path.lower():
            # Look for async def without auth check
            handler_pattern = r"async def (\w+)\([^)]*\):"
            for match in re.finditer(handler_pattern, code):
                func_name = match.group(1)
                if not func_name.startswith("_"):  # Public handler
                    # Check if there's an auth check nearby
                    func_start = match.start()
                    func_body_start = code.find(":", func_start) + 1
                    next_func = code.find("async def", func_body_start)
                    if next_func == -1:
                        next_func = len(code)
                    func_body = code[func_body_start:next_func]

                    if not any(
                        auth in func_body.lower()
                        for auth in ["auth", "permission", "allowed", "verify"]
                    ):
                        line_number = code[: match.start()].count("\n") + 1
                        issues.append(
                            SecurityIssue(
                                category=OWASPCategory.A01_BROKEN_ACCESS_CONTROL,
                                severity=Severity.LOW,
                                title="Handler Without Apparent Auth Check",
                                description=f"Handler '{func_name}' may lack authentication",
                                file_path=file_path,
                                line_number=line_number,
                                recommendation="Add authentication/authorization checks",
                                cwe_id="CWE-862",
                            )
                        )

        return issues

    async def _check_logging(
        self,
        code: str,
        file_path: str | None,
    ) -> list[SecurityIssue]:
        """Check for logging issues."""
        issues = []

        # Check for sensitive data in logs
        sensitive_patterns = [
            (r"logger\.\w+\([^)]*password", "Password in logs"),
            (r"logger\.\w+\([^)]*token", "Token in logs"),
            (r"logger\.\w+\([^)]*secret", "Secret in logs"),
            (r"logger\.\w+\([^)]*api_key", "API key in logs"),
            (r"print\([^)]*password", "Password in print statement"),
        ]

        for pattern, description in sensitive_patterns:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                line_number = code[: match.start()].count("\n") + 1
                issues.append(
                    SecurityIssue(
                        category=OWASPCategory.A09_LOGGING_FAlgoLURES,
                        severity=Severity.MEDIUM,
                        title="Sensitive Data in Logs",
                        description=description,
                        file_path=file_path,
                        line_number=line_number,
                        code_snippet=self._get_snippet(code, line_number),
                        recommendation="Mask or remove sensitive data from logs",
                        cwe_id="CWE-532",
                    )
                )

        return issues

    def _get_snippet(self, code: str, line_number: int, context: int = 2) -> str:
        """Get code snippet around line number."""
        lines = code.splitlines()
        start = max(0, line_number - context - 1)
        end = min(len(lines), line_number + context)
        return "\n".join(lines[start:end])

    async def generate_report(
        self,
        issues: list[SecurityIssue],
        format: str = "text",
    ) -> str:
        """
        Generate a report from issues.

        Args:
            issues: List of security issues
            format: Output format ("text", "json", "markdown")

        Returns:
            Formatted report
        """
        if format == "json":
            import json

            return json.dumps([i.to_dict() for i in issues], indent=2)

        if format == "markdown":
            return self._generate_markdown_report(issues)

        return self._generate_text_report(issues)

    def _generate_text_report(self, issues: list[SecurityIssue]) -> str:
        """Generate text report."""
        lines = [
            "=" * 60,
            "OWASP Security Validation Report",
            "=" * 60,
            f"Total Issues: {len(issues)}",
            f"Critical: {sum(1 for i in issues if i.severity == Severity.CRITICAL)}",
            f"High: {sum(1 for i in issues if i.severity == Severity.HIGH)}",
            f"Medium: {sum(1 for i in issues if i.severity == Severity.MEDIUM)}",
            f"Low: {sum(1 for i in issues if i.severity == Severity.LOW)}",
            "",
        ]

        for issue in sorted(issues, key=lambda x: x.severity.value):
            lines.extend(
                [
                    "-" * 40,
                    f"[{issue.severity.value.upper()}] {issue.title}",
                    f"Category: {issue.category.value}",
                    f"File: {issue.file_path}:{issue.line_number}",
                    f"Description: {issue.description}",
                    f"Recommendation: {issue.recommendation}",
                    "",
                ]
            )

        return "\n".join(lines)

    def _generate_markdown_report(self, issues: list[SecurityIssue]) -> str:
        """Generate markdown report."""
        lines = [
            "# 🔒 OWASP Security Validation Report",
            "",
            "## Summary",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| 🔴 Critical | {sum(1 for i in issues if i.severity == Severity.CRITICAL)} |",
            f"| 🟠 High | {sum(1 for i in issues if i.severity == Severity.HIGH)} |",
            f"| 🟡 Medium | {sum(1 for i in issues if i.severity == Severity.MEDIUM)} |",
            f"| 🟢 Low | {sum(1 for i in issues if i.severity == Severity.LOW)} |",
            "",
            "## Issues",
            "",
        ]

        for issue in sorted(issues, key=lambda x: x.severity.value):
            severity_emoji = {
                Severity.CRITICAL: "🔴",
                Severity.HIGH: "🟠",
                Severity.MEDIUM: "🟡",
                Severity.LOW: "🟢",
                Severity.INFO: "🔵",
            }.get(issue.severity, "⚪")

            lines.extend(
                [
                    f"### {severity_emoji} {issue.title}",
                    "",
                    f"- **Category**: {issue.category.value}",
                    f"- **Severity**: {issue.severity.value}",
                    (
                        f"- **File**: `{issue.file_path}:{issue.line_number}`"
                        if issue.file_path
                        else ""
                    ),
                    f"- **CWE**: {issue.cwe_id}" if issue.cwe_id else "",
                    "",
                    f"**Description**: {issue.description}",
                    "",
                    f"**Recommendation**: {issue.recommendation}",
                    "",
                ]
            )

        return "\n".join(lines)
