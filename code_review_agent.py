#!/usr/bin/env python3
"""
Code Review Agent - Comprehensive codebase scanner for security issues,
code style problems, performance concerns, potential bugs, and best practice violations.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional


class Severity(Enum):
    """Issue severity levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __str__(self):
        return self.name.lower()


class Category(Enum):
    """Issue category types."""
    SECURITY = "security"
    STYLE = "style"
    PERFORMANCE = "performance"
    BUGS = "bugs"
    BEST_PRACTICES = "best_practices"

    def __str__(self):
        return self.value


@dataclass
class Issue:
    """Represents a detected code issue."""
    rule_id: str
    title: str
    category: Category
    severity: Severity
    file_path: str
    line_number: int
    line_content: str
    suggestion: str

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "category": str(self.category),
            "severity": str(self.severity),
            "file_path": self.file_path,
            "line_number": self.line_number,
            "line_content": self.line_content.strip()[:100],
            "suggestion": self.suggestion
        }


@dataclass
class ReviewRule:
    """Defines a detection pattern for code review."""
    rule_id: str
    title: str
    category: Category
    severity: Severity
    pattern: str
    suggestion: str
    file_patterns: list = field(default_factory=lambda: ["*"])

    def matches_file(self, filename: str) -> bool:
        """Check if this rule applies to the given file."""
        return any(fnmatch(filename, p) for p in self.file_patterns)


class CodeReviewAgent:
    """Main code review agent that scans codebases for issues."""

    DEFAULT_EXCLUDES = [
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        "dist", "build", ".claude", "*.min.js", "*.min.css",
        ".next", ".nuxt", "coverage", ".pytest_cache", ".mypy_cache",
        "*.pyc", "*.pyo", "*.egg-info", ".eggs"
    ]

    def __init__(self):
        self.rules: list[ReviewRule] = []
        self.issues: list[Issue] = []
        self.files_scanned = 0
        self._load_rules()

    def _load_rules(self):
        """Initialize all detection rules."""

        # ============== SECURITY RULES ==============
        self.rules.extend([
            ReviewRule(
                rule_id="SEC001",
                title="Hardcoded API Key/Secret",
                category=Category.SECURITY,
                severity=Severity.CRITICAL,
                pattern=r'(?i)(api[_-]?key|api[_-]?secret|secret[_-]?key|auth[_-]?token|access[_-]?token)\s*[=:]\s*["\'][a-zA-Z0-9]{16,}["\']',
                suggestion="Move secrets to environment variables or a secure vault"
            ),
            ReviewRule(
                rule_id="SEC002",
                title="Hardcoded Password",
                category=Category.SECURITY,
                severity=Severity.CRITICAL,
                pattern=r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{4,}["\']',
                suggestion="Never hardcode passwords; use environment variables or secret management"
            ),
            ReviewRule(
                rule_id="SEC003",
                title="SQL Injection Risk",
                category=Category.SECURITY,
                severity=Severity.CRITICAL,
                pattern=r'(?i)(execute|query|raw)\s*\([^)]*(%s|%d|\+\s*\w+|\{\}\.format|\$\{)',
                suggestion="Use parameterized queries or prepared statements",
                file_patterns=["*.py", "*.js", "*.ts", "*.php"]
            ),
            ReviewRule(
                rule_id="SEC004",
                title="Use of eval()",
                category=Category.SECURITY,
                severity=Severity.HIGH,
                pattern=r'\beval\s*\(',
                suggestion="Avoid eval(); use safer alternatives like JSON.parse() or ast.literal_eval()",
                file_patterns=["*.py", "*.js", "*.ts"]
            ),
            ReviewRule(
                rule_id="SEC005",
                title="Insecure Pickle Usage",
                category=Category.SECURITY,
                severity=Severity.HIGH,
                pattern=r'pickle\.(load|loads)\s*\(',
                suggestion="Pickle is insecure for untrusted data; use JSON or msgpack",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="SEC006",
                title="Shell Injection Risk",
                category=Category.SECURITY,
                severity=Severity.HIGH,
                pattern=r'(subprocess\.(call|run|Popen)|os\.system|os\.popen)\s*\([^)]*shell\s*=\s*True',
                suggestion="Avoid shell=True; pass command as list of arguments",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="SEC007",
                title="Insecure Random for Security",
                category=Category.SECURITY,
                severity=Severity.MEDIUM,
                pattern=r'\brandom\.(random|randint|choice|shuffle)\s*\(',
                suggestion="Use secrets module for security-sensitive random values",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="SEC008",
                title="Debug Mode in Production",
                category=Category.SECURITY,
                severity=Severity.HIGH,
                pattern=r'(?i)(debug\s*[=:]\s*true|DEBUG\s*=\s*True)',
                suggestion="Ensure debug mode is disabled in production",
                file_patterns=["*.py", "*.js", "*.ts", "*.env*"]
            ),
            ReviewRule(
                rule_id="SEC009",
                title="Disabled SSL Verification",
                category=Category.SECURITY,
                severity=Severity.HIGH,
                pattern=r'verify\s*=\s*False|rejectUnauthorized\s*:\s*false',
                suggestion="Always verify SSL certificates in production",
                file_patterns=["*.py", "*.js", "*.ts"]
            ),
            ReviewRule(
                rule_id="SEC010",
                title="innerHTML XSS Risk",
                category=Category.SECURITY,
                severity=Severity.HIGH,
                pattern=r'\.innerHTML\s*=|dangerouslySetInnerHTML',
                suggestion="Sanitize user input before using innerHTML; prefer textContent",
                file_patterns=["*.js", "*.ts", "*.jsx", "*.tsx"]
            ),
        ])

        # ============== STYLE RULES ==============
        self.rules.extend([
            ReviewRule(
                rule_id="STY001",
                title="Missing Docstring",
                category=Category.STYLE,
                severity=Severity.LOW,
                pattern=r'^(def|class)\s+\w+[^:]*:\s*\n\s*(?!(\'\'\'|"""|#))',
                suggestion="Add a docstring to document this function/class",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="STY002",
                title="Line Too Long",
                category=Category.STYLE,
                severity=Severity.LOW,
                pattern=r'^.{121,}$',
                suggestion="Keep lines under 120 characters for readability"
            ),
            ReviewRule(
                rule_id="STY003",
                title="Magic Number",
                category=Category.STYLE,
                severity=Severity.LOW,
                pattern=r'(?<!["\'\w])\b(?!0\b|1\b|2\b|-1\b|100\b)\d{3,}\b(?!["\'])',
                suggestion="Extract magic numbers into named constants"
            ),
            ReviewRule(
                rule_id="STY004",
                title="TODO/FIXME Comment",
                category=Category.STYLE,
                severity=Severity.LOW,
                pattern=r'#\s*(TODO|FIXME|XXX|HACK|BUG):?',
                suggestion="Address or create an issue for this TODO/FIXME"
            ),
            ReviewRule(
                rule_id="STY005",
                title="Commented Out Code",
                category=Category.STYLE,
                severity=Severity.LOW,
                pattern=r'#\s*(def |class |import |from |if |for |while |return )',
                suggestion="Remove commented-out code; use version control instead",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="STY006",
                title="Console.log in Production Code",
                category=Category.STYLE,
                severity=Severity.LOW,
                pattern=r'console\.(log|debug|info)\s*\(',
                suggestion="Remove console.log statements or use a proper logging library",
                file_patterns=["*.js", "*.ts", "*.jsx", "*.tsx"]
            ),
        ])

        # ============== PERFORMANCE RULES ==============
        self.rules.extend([
            ReviewRule(
                rule_id="PERF001",
                title="String Concatenation in Loop",
                category=Category.PERFORMANCE,
                severity=Severity.MEDIUM,
                pattern=r'(for|while)\s+[^:]+:\s*\n[^}]*\+=\s*["\']',
                suggestion="Use list and join() for string building in loops",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="PERF002",
                title="Regex Compilation in Loop",
                category=Category.PERFORMANCE,
                severity=Severity.MEDIUM,
                pattern=r'(for|while)\s+[^:]+:\s*\n[^}]*re\.(match|search|findall|sub)\s*\(',
                suggestion="Compile regex patterns outside of loops with re.compile()",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="PERF003",
                title="Synchronous File I/O in Async Context",
                category=Category.PERFORMANCE,
                severity=Severity.MEDIUM,
                pattern=r'async\s+def\s+\w+[^:]*:[^}]*(open\(|\.read\(|\.write\()',
                suggestion="Use async file I/O (aiofiles) in async functions",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="PERF004",
                title="N+1 Query Pattern",
                category=Category.PERFORMANCE,
                severity=Severity.HIGH,
                pattern=r'for\s+\w+\s+in\s+\w+[^:]*:\s*\n[^}]*(\.objects\.|\.query\.|\.find\(|\.findOne\()',
                suggestion="Use eager loading or batch queries to avoid N+1 problem",
                file_patterns=["*.py", "*.js", "*.ts"]
            ),
            ReviewRule(
                rule_id="PERF005",
                title="Inefficient List Membership Check",
                category=Category.PERFORMANCE,
                severity=Severity.LOW,
                pattern=r'\bif\s+\w+\s+in\s+\[[^\]]{50,}\]',
                suggestion="Use a set for O(1) membership checks instead of list",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="PERF006",
                title="Blocking Sleep in Async",
                category=Category.PERFORMANCE,
                severity=Severity.MEDIUM,
                pattern=r'async\s+def\s+\w+[^:]*:[^}]*time\.sleep\(',
                suggestion="Use asyncio.sleep() in async functions",
                file_patterns=["*.py"]
            ),
        ])

        # ============== BUG RULES ==============
        self.rules.extend([
            ReviewRule(
                rule_id="BUG001",
                title="Bare Except Clause",
                category=Category.BUGS,
                severity=Severity.MEDIUM,
                pattern=r'except\s*:',
                suggestion="Catch specific exceptions; bare except catches SystemExit and KeyboardInterrupt",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BUG002",
                title="Mutable Default Argument",
                category=Category.BUGS,
                severity=Severity.HIGH,
                pattern=r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|\set\(\))',
                suggestion="Use None as default and initialize inside function",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BUG003",
                title="Unclosed File Handle",
                category=Category.BUGS,
                severity=Severity.MEDIUM,
                pattern=r'(?<!with\s)open\s*\([^)]+\)(?!\s*as\b)',
                suggestion="Use 'with' statement for file handling to ensure proper cleanup",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BUG004",
                title="Comparison to None",
                category=Category.BUGS,
                severity=Severity.LOW,
                pattern=r'(==|!=)\s*None\b',
                suggestion="Use 'is None' or 'is not None' for None comparisons",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BUG005",
                title="Comparison to True/False",
                category=Category.BUGS,
                severity=Severity.LOW,
                pattern=r'(==|!=)\s*(True|False)\b',
                suggestion="Use 'if x:' or 'if not x:' instead of comparing to True/False",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BUG006",
                title="Unused Variable Assignment",
                category=Category.BUGS,
                severity=Severity.LOW,
                pattern=r'^\s*_\s*=\s*(?!.*#\s*noqa)',
                suggestion="Use explicit discard or remove unused assignment"
            ),
            ReviewRule(
                rule_id="BUG007",
                title="Assert in Production",
                category=Category.BUGS,
                severity=Severity.MEDIUM,
                pattern=r'^\s*assert\s+',
                suggestion="Assertions are disabled with -O flag; use proper error handling",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BUG008",
                title="Floating Point Equality",
                category=Category.BUGS,
                severity=Severity.MEDIUM,
                pattern=r'(?:float|[0-9]+\.[0-9]+)\s*==',
                suggestion="Use math.isclose() or a tolerance for float comparisons"
            ),
        ])

        # ============== BEST PRACTICES RULES ==============
        self.rules.extend([
            ReviewRule(
                rule_id="BP001",
                title="Function Too Long",
                category=Category.BEST_PRACTICES,
                severity=Severity.MEDIUM,
                pattern=r'def\s+\w+\s*\([^)]*\)\s*(?:->.*?)?:\s*\n(?:[^\n]*\n){50,}(?=\ndef\s|\nclass\s|\Z)',
                suggestion="Consider breaking this function into smaller, focused functions",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BP002",
                title="Too Many Function Arguments",
                category=Category.BEST_PRACTICES,
                severity=Severity.MEDIUM,
                pattern=r'def\s+\w+\s*\(([^)]*,){6,}[^)]*\)',
                suggestion="Consider using a configuration object or dataclass for many parameters",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BP003",
                title="Global Variable",
                category=Category.BEST_PRACTICES,
                severity=Severity.MEDIUM,
                pattern=r'^\s*global\s+\w+',
                suggestion="Avoid global variables; use function parameters or class attributes",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BP004",
                title="Star Import",
                category=Category.BEST_PRACTICES,
                severity=Severity.LOW,
                pattern=r'from\s+\w+\s+import\s+\*',
                suggestion="Avoid star imports; import specific names for clarity",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BP005",
                title="Deeply Nested Code",
                category=Category.BEST_PRACTICES,
                severity=Severity.MEDIUM,
                pattern=r'^(\s{16,}|\t{4,})(if|for|while|with)\s+',
                suggestion="Reduce nesting by using early returns or extracting functions"
            ),
            ReviewRule(
                rule_id="BP006",
                title="Hardcoded URL/IP",
                category=Category.BEST_PRACTICES,
                severity=Severity.LOW,
                pattern=r'["\']https?://(?!localhost|127\.0\.0\.1|example\.com)[^"\']+["\']',
                suggestion="Move URLs to configuration files or environment variables"
            ),
            ReviewRule(
                rule_id="BP007",
                title="Print Statement for Debugging",
                category=Category.BEST_PRACTICES,
                severity=Severity.LOW,
                pattern=r'\bprint\s*\([^)]*(?:debug|DEBUG|test|TEST)',
                suggestion="Use a proper logging framework instead of print statements",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BP008",
                title="Catch and Ignore Exception",
                category=Category.BEST_PRACTICES,
                severity=Severity.MEDIUM,
                pattern=r'except[^:]*:\s*\n\s*(pass|\.\.\.)\s*\n',
                suggestion="Log or handle exceptions; silent failures hide bugs",
                file_patterns=["*.py"]
            ),
            ReviewRule(
                rule_id="BP009",
                title="Long Method Chain",
                category=Category.BEST_PRACTICES,
                severity=Severity.LOW,
                pattern=r'(\.\w+\([^)]*\)){5,}',
                suggestion="Break long method chains into intermediate variables for readability"
            ),
            ReviewRule(
                rule_id="BP010",
                title="Duplicate String Literal",
                category=Category.BEST_PRACTICES,
                severity=Severity.LOW,
                pattern=r'(["\'][^"\']{20,}["\']).*\1',
                suggestion="Extract repeated string literals into constants"
            ),
        ])

    def scan_file(self, file_path: Path) -> list[Issue]:
        """Scan a single file for issues."""
        issues = []
        filename = file_path.name

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
        except Exception:
            return issues

        for rule in self.rules:
            if not rule.matches_file(filename):
                continue

            try:
                pattern = re.compile(rule.pattern, re.MULTILINE | re.IGNORECASE)

                for match in pattern.finditer(content):
                    # Calculate line number
                    line_number = content[:match.start()].count("\n") + 1
                    line_content = lines[line_number - 1] if line_number <= len(lines) else ""

                    issues.append(Issue(
                        rule_id=rule.rule_id,
                        title=rule.title,
                        category=rule.category,
                        severity=rule.severity,
                        file_path=str(file_path),
                        line_number=line_number,
                        line_content=line_content,
                        suggestion=rule.suggestion
                    ))
            except re.error:
                continue

        return issues

    def scan_directory(
        self,
        path: Path,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None
    ) -> list[Issue]:
        """Recursively scan a directory for issues."""
        all_issues = []
        exclude_patterns = exclude_patterns or []
        all_excludes = self.DEFAULT_EXCLUDES + exclude_patterns

        for root, dirs, files in os.walk(path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not any(
                fnmatch(d, pat) for pat in all_excludes
            )]

            for filename in files:
                # Check excludes
                if any(fnmatch(filename, pat) for pat in all_excludes):
                    continue

                # Check includes
                if include_patterns:
                    if not any(fnmatch(filename, pat) for pat in include_patterns):
                        continue

                file_path = Path(root) / filename
                self.files_scanned += 1
                all_issues.extend(self.scan_file(file_path))

        return all_issues

    def run(
        self,
        path: str = ".",
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
        category_filter: Optional[str] = None,
        severity_filter: Optional[str] = None
    ) -> list[Issue]:
        """Run the code review scan."""
        self.files_scanned = 0
        self.issues = self.scan_directory(
            Path(path),
            include_patterns,
            exclude_patterns
        )

        # Apply category filter
        if category_filter:
            try:
                cat = Category(category_filter.lower())
                self.issues = [i for i in self.issues if i.category == cat]
            except ValueError:
                pass

        # Apply severity filter
        if severity_filter:
            try:
                min_sev = Severity[severity_filter.upper()]
                self.issues = [i for i in self.issues if i.severity.value >= min_sev.value]
            except KeyError:
                pass

        # Sort by severity (critical first) then by file path
        self.issues.sort(key=lambda x: (-x.severity.value, x.file_path, x.line_number))

        return self.issues

    def _generate_text_report(self, quiet: bool = False) -> str:
        """Generate a text-format report."""
        lines = []
        lines.append("=" * 60)
        lines.append("CODE REVIEW REPORT")
        lines.append("=" * 60)
        lines.append(f"Files scanned: {self.files_scanned}")
        lines.append(f"Total issues: {len(self.issues)}")
        lines.append("")

        # Summary by severity
        by_severity = {}
        for sev in Severity:
            count = sum(1 for i in self.issues if i.severity == sev)
            if count > 0:
                by_severity[sev.name] = count

        if by_severity:
            lines.append("By Severity: " + ", ".join(
                f"{k}: {v}" for k, v in by_severity.items()
            ))

        # Summary by category
        by_category = {}
        for cat in Category:
            count = sum(1 for i in self.issues if i.category == cat)
            if count > 0:
                by_category[cat.value] = count

        if by_category:
            lines.append("By Category: " + ", ".join(
                f"{k}: {v}" for k, v in by_category.items()
            ))

        if quiet:
            return "\n".join(lines)

        # Detailed issues grouped by severity
        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
            sev_issues = [i for i in self.issues if i.severity == severity]
            if not sev_issues:
                continue

            lines.append("")
            lines.append("-" * 60)
            lines.append(f"{severity.name} ISSUES ({len(sev_issues)})")
            lines.append("-" * 60)

            for issue in sev_issues:
                lines.append("")
                lines.append(f"[{issue.rule_id}] {issue.title}")
                lines.append(f"  File: {issue.file_path}:{issue.line_number}")
                if issue.line_content.strip():
                    lines.append(f"  Code: {issue.line_content.strip()[:80]}")
                lines.append(f"  Suggestion: {issue.suggestion}")

        return "\n".join(lines)

    def _generate_json_report(self) -> str:
        """Generate a JSON-format report."""
        by_severity = {str(sev): 0 for sev in Severity}
        by_category = {str(cat): 0 for cat in Category}

        for issue in self.issues:
            by_severity[str(issue.severity)] += 1
            by_category[str(issue.category)] += 1

        report = {
            "summary": {
                "files_scanned": self.files_scanned,
                "total_issues": len(self.issues),
                "by_severity": {k: v for k, v in by_severity.items() if v > 0},
                "by_category": {k: v for k, v in by_category.items() if v > 0}
            },
            "issues": [issue.to_dict() for issue in self.issues]
        }

        return json.dumps(report, indent=2)

    def list_rules(self) -> str:
        """Generate a list of all available rules."""
        lines = []
        lines.append("=" * 60)
        lines.append("AVAILABLE DETECTION RULES")
        lines.append("=" * 60)

        for category in Category:
            cat_rules = [r for r in self.rules if r.category == category]
            if not cat_rules:
                continue

            lines.append("")
            lines.append(f"{category.value.upper()} ({len(cat_rules)} rules)")
            lines.append("-" * 40)

            for rule in cat_rules:
                lines.append(f"  [{rule.rule_id}] {rule.title}")
                lines.append(f"           Severity: {rule.severity.name}")
                files = ", ".join(rule.file_patterns)
                lines.append(f"           Applies to: {files}")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Code Review Agent - Scan codebase for issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python code_review_agent.py
  python code_review_agent.py --path ./src --severity high
  python code_review_agent.py --category security --json -o report.json
  python code_review_agent.py --include "*.py" --exclude "*_test.py"
  python code_review_agent.py --list-rules
        """
    )

    parser.add_argument(
        "-p", "--path",
        default=".",
        help="Directory to scan (default: current directory)"
    )
    parser.add_argument(
        "-i", "--include",
        action="append",
        help="File patterns to include (can be used multiple times)"
    )
    parser.add_argument(
        "-e", "--exclude",
        action="append",
        help="File patterns to exclude (can be used multiple times)"
    )
    parser.add_argument(
        "-c", "--category",
        choices=["security", "style", "performance", "bugs", "best_practices"],
        help="Filter by category"
    )
    parser.add_argument(
        "-s", "--severity",
        choices=["low", "medium", "high", "critical"],
        help="Minimum severity to report"
    )
    parser.add_argument(
        "-o", "--output",
        help="Save report to file"
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only show summary"
    )
    parser.add_argument(
        "-l", "--list-rules",
        action="store_true",
        help="List all available detection rules"
    )

    args = parser.parse_args()

    agent = CodeReviewAgent()

    # List rules and exit
    if args.list_rules:
        print(agent.list_rules())
        return

    # Run the scan
    agent.run(
        path=args.path,
        include_patterns=args.include,
        exclude_patterns=args.exclude,
        category_filter=args.category,
        severity_filter=args.severity
    )

    # Generate report
    if args.json:
        report = agent._generate_json_report()
    else:
        report = agent._generate_text_report(quiet=args.quiet)

    # Output report
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to: {args.output}")
    else:
        print(report)

    # Exit with non-zero if critical/high issues found
    critical_high = sum(
        1 for i in agent.issues
        if i.severity in [Severity.CRITICAL, Severity.HIGH]
    )
    if critical_high > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
