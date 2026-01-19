"""
Chart Improvement Agent for SB19 Dashboard

This agent focuses on improving charts and visuals in the dashboard by:
1. Analyzing current chart configurations and visual patterns
2. Suggesting improvements based on data visualization best practices
3. Detecting common chart issues (accessibility, readability, performance)
4. Generating specific code recommendations
5. Optionally applying improvements automatically
"""

import os
import sys
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class ImprovementCategory(Enum):
    ACCESSIBILITY = "accessibility"
    READABILITY = "readability"
    PERFORMANCE = "performance"
    INTERACTIVITY = "interactivity"
    AESTHETICS = "aesthetics"
    DATA_PRESENTATION = "data_presentation"


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ChartConfig:
    """Represents a chart configuration found in the code"""
    name: str
    chart_type: str
    canvas_id: str
    line_number: int
    config_snippet: str
    has_animations: bool = True
    has_tooltips: bool = True
    has_legends: bool = True
    has_datalabels: bool = False
    responsive: bool = True
    datasets_count: int = 1


@dataclass
class Improvement:
    """Represents a suggested improvement"""
    id: str
    category: ImprovementCategory
    severity: Severity
    title: str
    description: str
    chart_name: Optional[str] = None
    current_code: Optional[str] = None
    suggested_code: Optional[str] = None
    line_number: Optional[int] = None
    auto_fixable: bool = False


@dataclass
class AnalysisResult:
    """Complete analysis result"""
    timestamp: str
    charts_found: List[ChartConfig]
    improvements: List[Improvement]
    summary: Dict[str, Any] = field(default_factory=dict)


# Chart.js best practices and improvement rules
CHART_RULES = {
    'accessibility': [
        {
            'id': 'ACC001',
            'name': 'Missing ARIA labels',
            'check': lambda config: 'aria-label' not in config.get('canvas_html', ''),
            'suggestion': 'Add aria-label to canvas elements for screen reader support',
            'severity': Severity.MEDIUM,
        },
        {
            'id': 'ACC002',
            'name': 'Color contrast for data',
            'check': lambda config: True,  # Always suggest reviewing
            'suggestion': 'Ensure chart colors have sufficient contrast ratio (4.5:1 for text)',
            'severity': Severity.LOW,
        },
        {
            'id': 'ACC003',
            'name': 'Missing alt descriptions',
            'check': lambda config: 'description' not in config.get('options', {}),
            'suggestion': 'Add descriptive text alternatives for charts',
            'severity': Severity.MEDIUM,
        },
    ],
    'readability': [
        {
            'id': 'READ001',
            'name': 'Dense data labels',
            'check': lambda config: config.get('datasets_count', 0) > 5,
            'suggestion': 'Consider grouping or filtering data when showing many datasets',
            'severity': Severity.LOW,
        },
        {
            'id': 'READ002',
            'name': 'Missing axis titles',
            'check': lambda config: 'title' not in str(config.get('scales', {})),
            'suggestion': 'Add descriptive titles to chart axes',
            'severity': Severity.LOW,
        },
        {
            'id': 'READ003',
            'name': 'Number formatting',
            'check': lambda config: 'callback' not in str(config.get('ticks', {})),
            'suggestion': 'Format large numbers with K/M suffixes for readability',
            'severity': Severity.LOW,
        },
    ],
    'performance': [
        {
            'id': 'PERF001',
            'name': 'Animation on large datasets',
            'check': lambda config: config.get('animation', True) and config.get('data_points', 0) > 100,
            'suggestion': 'Disable animations for large datasets to improve performance',
            'severity': Severity.MEDIUM,
        },
        {
            'id': 'PERF002',
            'name': 'Missing decimation',
            'check': lambda config: config.get('chart_type') == 'line' and config.get('data_points', 0) > 500,
            'suggestion': 'Enable data decimation for line charts with many points',
            'severity': Severity.HIGH,
        },
        {
            'id': 'PERF003',
            'name': 'Spannable gaps',
            'check': lambda config: config.get('chart_type') == 'line',
            'suggestion': 'Use spanGaps: true to improve line chart rendering with sparse data',
            'severity': Severity.LOW,
        },
    ],
    'interactivity': [
        {
            'id': 'INT001',
            'name': 'Missing hover effects',
            'check': lambda config: 'hover' not in str(config.get('options', {})),
            'suggestion': 'Add hover effects to improve user feedback',
            'severity': Severity.LOW,
        },
        {
            'id': 'INT002',
            'name': 'Click handlers',
            'check': lambda config: 'onClick' not in str(config.get('options', {})),
            'suggestion': 'Add click handlers for interactive filtering',
            'severity': Severity.LOW,
        },
        {
            'id': 'INT003',
            'name': 'Tooltip customization',
            'check': lambda config: 'callbacks' not in str(config.get('tooltip', {})),
            'suggestion': 'Customize tooltips to show more contextual information',
            'severity': Severity.LOW,
        },
    ],
    'aesthetics': [
        {
            'id': 'AES001',
            'name': 'Gradient fills',
            'check': lambda config: config.get('chart_type') in ['line', 'bar'] and 'gradient' not in str(config.get('backgroundColor', '')),
            'suggestion': 'Consider using gradient fills for more visual appeal',
            'severity': Severity.LOW,
        },
        {
            'id': 'AES002',
            'name': 'Border radius on bars',
            'check': lambda config: config.get('chart_type') == 'bar' and 'borderRadius' not in str(config.get('options', {})),
            'suggestion': 'Add borderRadius to bar charts for modern rounded look',
            'severity': Severity.LOW,
        },
        {
            'id': 'AES003',
            'name': 'Consistent color palette',
            'check': lambda config: True,
            'suggestion': 'Use a consistent, accessible color palette across all charts',
            'severity': Severity.LOW,
        },
    ],
    'data_presentation': [
        {
            'id': 'DATA001',
            'name': 'Sorted data',
            'check': lambda config: config.get('chart_type') == 'bar',
            'suggestion': 'Sort bar chart data by value for easier comparison',
            'severity': Severity.LOW,
        },
        {
            'id': 'DATA002',
            'name': 'Trend indicators',
            'check': lambda config: config.get('chart_type') == 'line',
            'suggestion': 'Add trend line or moving average for pattern recognition',
            'severity': Severity.MEDIUM,
        },
        {
            'id': 'DATA003',
            'name': 'Reference lines',
            'check': lambda config: 'annotation' not in str(config.get('plugins', {})),
            'suggestion': 'Add reference/threshold lines for context (e.g., averages, goals)',
            'severity': Severity.LOW,
        },
    ],
}


# Code snippets for common improvements
IMPROVEMENT_SNIPPETS = {
    'number_formatting': '''
// Format numbers with K/M suffixes
ticks: {
    callback: function(value) {
        if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
        if (value >= 1000) return (value / 1000).toFixed(0) + 'K';
        return value;
    }
}''',

    'gradient_fill': '''
// Create gradient fill for line/area charts
const ctx = chart.canvas.getContext('2d');
const gradient = ctx.createLinearGradient(0, 0, 0, chart.height);
gradient.addColorStop(0, 'rgba(96, 165, 250, 0.4)');
gradient.addColorStop(1, 'rgba(96, 165, 250, 0.0)');''',

    'bar_border_radius': '''
// Add rounded corners to bars
elements: {
    bar: {
        borderRadius: 4,
        borderSkipped: false
    }
}''',

    'tooltip_callbacks': '''
// Enhanced tooltip with formatted values
plugins: {
    tooltip: {
        callbacks: {
            label: function(context) {
                let value = context.parsed.y || context.parsed.x;
                if (value >= 1000000) return context.dataset.label + ': ' + (value / 1000000).toFixed(2) + 'M';
                if (value >= 1000) return context.dataset.label + ': ' + (value / 1000).toFixed(1) + 'K';
                return context.dataset.label + ': ' + value.toLocaleString();
            }
        }
    }
}''',

    'hover_effects': '''
// Add hover animation effects
interaction: {
    mode: 'nearest',
    intersect: false
},
hover: {
    animationDuration: 200
}''',

    'animation_disabled': '''
// Disable animations for better performance
animation: false,
animations: {
    colors: false,
    x: false
},
transitions: {
    active: {
        animation: {
            duration: 0
        }
    }
}''',

    'decimation': '''
// Enable data decimation for large datasets
plugins: {
    decimation: {
        enabled: true,
        algorithm: 'lttb',
        samples: 500
    }
}''',

    'aria_label': '''
// Add to canvas element
<canvas id="chartId" aria-label="Description of chart data" role="img"></canvas>''',

    'trend_line': '''
// Add trend line using annotation plugin
plugins: {
    annotation: {
        annotations: {
            trendLine: {
                type: 'line',
                borderColor: 'rgba(255, 99, 132, 0.8)',
                borderDash: [6, 6],
                borderWidth: 2,
                label: {
                    display: true,
                    content: 'Trend'
                },
                // Calculate start/end points based on data regression
                scaleID: 'y',
                value: 'calculated_average'
            }
        }
    }
}''',

    'reference_line': '''
// Add horizontal reference line (e.g., average)
plugins: {
    annotation: {
        annotations: {
            averageLine: {
                type: 'line',
                yMin: averageValue,
                yMax: averageValue,
                borderColor: 'rgba(255, 159, 64, 0.8)',
                borderWidth: 2,
                borderDash: [5, 5],
                label: {
                    display: true,
                    content: 'Average: ' + averageValue.toLocaleString(),
                    position: 'end'
                }
            }
        }
    }
}''',
}


class ChartImprovementAgent:
    def __init__(self, data_dir: str = '.'):
        self.data_dir = Path(data_dir)
        self.dashboard_path = self.data_dir / 'index.html'
        self.charts: List[ChartConfig] = []
        self.improvements: List[Improvement] = []
        self.html_content: str = ''

    def load_dashboard(self) -> bool:
        """Load the dashboard HTML file"""
        if not self.dashboard_path.exists():
            print(f"ERROR: Dashboard not found: {self.dashboard_path}")
            return False

        with open(self.dashboard_path, 'r', encoding='utf-8') as f:
            self.html_content = f.read()

        print(f"Loaded dashboard: {self.dashboard_path}")
        print(f"  Size: {len(self.html_content):,} characters")
        return True

    def find_charts(self) -> List[ChartConfig]:
        """Find all Chart.js chart definitions in the code"""
        print("\nSearching for chart definitions...")

        charts = []

        # Pattern to find canvas elements
        canvas_pattern = r'<canvas\s+id=["\']([^"\']+)["\'][^>]*>'

        # Find all canvas IDs
        canvas_ids = re.findall(canvas_pattern, self.html_content)
        print(f"  Found {len(canvas_ids)} canvas elements")

        # Find chart configurations
        lines = self.html_content.split('\n')
        for i, line in enumerate(lines):
            # Look for chart variable assignments (multiple patterns)
            # Pattern 1: this.charts.xxx = new Chart
            chart_var_match = re.search(r'(?:this\.charts\.(\w+)|(\w+Chart))\s*=\s*new\s+Chart', line)
            if chart_var_match:
                chart_name = chart_var_match.group(1) or chart_var_match.group(2)

                # Determine chart type from nearby code
                context_start = max(0, i - 5)
                context_end = min(len(lines), i + 50)
                context = '\n'.join(lines[context_start:context_end])

                chart_type = 'unknown'
                type_match = re.search(r"type:\s*['\"](\w+)['\"]", context)
                if type_match:
                    chart_type = type_match.group(1)

                # Find canvas ID
                canvas_match = re.search(r"getElementById\s*\(\s*['\"](\w+)['\"]", context)
                canvas_id = canvas_match.group(1) if canvas_match else 'unknown'

                # Check for features
                has_datalabels = 'datalabels' in context.lower()
                has_animation = 'animation' not in context or 'animation: false' not in context
                has_tooltips = 'tooltip' in context.lower()

                # Count datasets
                datasets_count = context.count('datasets')

                chart_config = ChartConfig(
                    name=chart_name,
                    chart_type=chart_type,
                    canvas_id=canvas_id,
                    line_number=i + 1,
                    config_snippet=context[:500],
                    has_animations=has_animation,
                    has_tooltips=has_tooltips,
                    has_datalabels=has_datalabels,
                    datasets_count=datasets_count
                )

                charts.append(chart_config)
                print(f"  Found: {chart_name} (type: {chart_type}, line: {i + 1})")

        self.charts = charts
        return charts

    def analyze_charts(self) -> List[Improvement]:
        """Analyze charts and generate improvement suggestions"""
        print("\nAnalyzing charts for improvements...")

        improvements = []
        improvement_id = 0

        for chart in self.charts:
            print(f"\n  Analyzing: {chart.name}")

            config_dict = {
                'name': chart.name,
                'chart_type': chart.chart_type,
                'canvas_id': chart.canvas_id,
                'has_animations': chart.has_animations,
                'has_tooltips': chart.has_tooltips,
                'has_datalabels': chart.has_datalabels,
                'datasets_count': chart.datasets_count,
                'options': chart.config_snippet,
            }

            # Check each category of rules
            for category_name, rules in CHART_RULES.items():
                category = ImprovementCategory(category_name)

                for rule in rules:
                    try:
                        if rule['check'](config_dict):
                            improvement_id += 1

                            # Get code snippet if available
                            snippet_key = self._get_snippet_key(rule['id'])
                            suggested_code = IMPROVEMENT_SNIPPETS.get(snippet_key, None)

                            improvement = Improvement(
                                id=f"IMP{improvement_id:03d}",
                                category=category,
                                severity=rule['severity'],
                                title=rule['name'],
                                description=rule['suggestion'],
                                chart_name=chart.name,
                                line_number=chart.line_number,
                                suggested_code=suggested_code,
                                auto_fixable=suggested_code is not None
                            )
                            improvements.append(improvement)
                            print(f"    [{rule['severity'].value.upper()}] {rule['name']}")

                    except Exception as e:
                        # Skip rules that fail to evaluate
                        pass

        # Add general improvements not tied to specific charts
        improvements.extend(self._get_general_improvements())

        self.improvements = improvements
        return improvements

    def _get_snippet_key(self, rule_id: str) -> Optional[str]:
        """Map rule IDs to code snippet keys"""
        mapping = {
            'READ003': 'number_formatting',
            'AES001': 'gradient_fill',
            'AES002': 'bar_border_radius',
            'INT003': 'tooltip_callbacks',
            'INT001': 'hover_effects',
            'PERF001': 'animation_disabled',
            'PERF002': 'decimation',
            'ACC001': 'aria_label',
            'DATA002': 'trend_line',
            'DATA003': 'reference_line',
        }
        return mapping.get(rule_id)

    def _get_general_improvements(self) -> List[Improvement]:
        """Get improvements that apply to the dashboard as a whole"""
        improvements = []

        # Check for responsive design
        if 'responsive: false' in self.html_content:
            improvements.append(Improvement(
                id='GEN001',
                category=ImprovementCategory.READABILITY,
                severity=Severity.MEDIUM,
                title='Non-responsive charts detected',
                description='Enable responsive: true for better mobile experience',
                auto_fixable=False
            ))

        # Check for maintainAspectRatio
        if 'maintainAspectRatio: false' not in self.html_content:
            improvements.append(Improvement(
                id='GEN002',
                category=ImprovementCategory.READABILITY,
                severity=Severity.LOW,
                title='Aspect ratio control',
                description='Consider setting maintainAspectRatio: false for more layout control',
                auto_fixable=False
            ))

        # Check for Chart.js plugins
        if 'chartjs-plugin-zoom' not in self.html_content:
            improvements.append(Improvement(
                id='GEN003',
                category=ImprovementCategory.INTERACTIVITY,
                severity=Severity.LOW,
                title='Zoom plugin not detected',
                description='Consider adding chartjs-plugin-zoom for pan/zoom functionality on dense charts',
                suggested_code='<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom"></script>',
                auto_fixable=False
            ))

        # Check for dark mode support
        if 'color-scheme' not in self.html_content and 'prefers-color-scheme' not in self.html_content:
            improvements.append(Improvement(
                id='GEN004',
                category=ImprovementCategory.AESTHETICS,
                severity=Severity.LOW,
                title='Theme switching support',
                description='Consider adding light/dark theme toggle for chart colors',
                auto_fixable=False
            ))

        return improvements

    def generate_report(self, output_format: str = 'text') -> str:
        """Generate an improvement report"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if output_format == 'json':
            return self._generate_json_report()

        # Text format
        lines = [
            "=" * 70,
            "CHART IMPROVEMENT ANALYSIS REPORT",
            f"Generated: {timestamp}",
            "=" * 70,
            ""
        ]

        # Summary
        severity_counts = {}
        category_counts = {}

        for imp in self.improvements:
            severity_counts[imp.severity.value] = severity_counts.get(imp.severity.value, 0) + 1
            category_counts[imp.category.value] = category_counts.get(imp.category.value, 0) + 1

        lines.extend([
            "SUMMARY",
            "-" * 50,
            f"Charts analyzed: {len(self.charts)}",
            f"Total improvements suggested: {len(self.improvements)}",
            f"  - Critical: {severity_counts.get('critical', 0)}",
            f"  - High: {severity_counts.get('high', 0)}",
            f"  - Medium: {severity_counts.get('medium', 0)}",
            f"  - Low: {severity_counts.get('low', 0)}",
            "",
            "By category:",
        ])

        for cat, count in sorted(category_counts.items()):
            lines.append(f"  - {cat.replace('_', ' ').title()}: {count}")

        lines.append("")

        # Charts found
        lines.extend([
            "CHARTS DETECTED",
            "-" * 50,
        ])

        for chart in self.charts:
            lines.extend([
                f"\n{chart.name}",
                f"  Type: {chart.chart_type}",
                f"  Canvas ID: {chart.canvas_id}",
                f"  Line: {chart.line_number}",
                f"  Features: animations={chart.has_animations}, datalabels={chart.has_datalabels}",
            ])

        lines.append("")

        # Improvements by priority
        lines.extend([
            "",
            "IMPROVEMENTS BY PRIORITY",
            "-" * 50,
        ])

        # Sort by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        sorted_improvements = sorted(
            self.improvements,
            key=lambda x: severity_order.get(x.severity.value, 99)
        )

        current_severity = None
        for imp in sorted_improvements:
            if imp.severity != current_severity:
                current_severity = imp.severity
                lines.extend([
                    "",
                    f"[{imp.severity.value.upper()}]",
                    "-" * 30
                ])

            chart_info = f" ({imp.chart_name})" if imp.chart_name else ""
            auto_fix = " [AUTO-FIXABLE]" if imp.auto_fixable else ""

            lines.extend([
                f"\n{imp.id}: {imp.title}{chart_info}{auto_fix}",
                f"  Category: {imp.category.value.replace('_', ' ').title()}",
                f"  {imp.description}",
            ])

            if imp.line_number:
                lines.append(f"  Line: {imp.line_number}")

            if imp.suggested_code:
                lines.extend([
                    "  Suggested code:",
                    "  " + "-" * 40,
                ])
                for code_line in imp.suggested_code.strip().split('\n'):
                    lines.append(f"    {code_line}")
                lines.append("  " + "-" * 40)

        # Quick wins section
        quick_wins = [imp for imp in self.improvements if imp.auto_fixable and imp.severity.value in ['high', 'medium']]
        if quick_wins:
            lines.extend([
                "",
                "",
                "QUICK WINS (High-impact, auto-fixable)",
                "-" * 50,
            ])
            for imp in quick_wins:
                lines.append(f"  - {imp.title} ({imp.chart_name or 'general'})")

        lines.extend([
            "",
            "=" * 70,
            "END OF REPORT",
            "=" * 70,
        ])

        return '\n'.join(lines)

    def _generate_json_report(self) -> str:
        """Generate JSON format report"""
        result = AnalysisResult(
            timestamp=datetime.now().isoformat(),
            charts_found=[asdict(c) for c in self.charts],
            improvements=[{
                'id': imp.id,
                'category': imp.category.value,
                'severity': imp.severity.value,
                'title': imp.title,
                'description': imp.description,
                'chart_name': imp.chart_name,
                'line_number': imp.line_number,
                'suggested_code': imp.suggested_code,
                'auto_fixable': imp.auto_fixable
            } for imp in self.improvements],
            summary={
                'charts_count': len(self.charts),
                'improvements_count': len(self.improvements),
                'by_severity': {},
                'by_category': {}
            }
        )

        for imp in self.improvements:
            sev = imp.severity.value
            cat = imp.category.value
            result.summary['by_severity'][sev] = result.summary['by_severity'].get(sev, 0) + 1
            result.summary['by_category'][cat] = result.summary['by_category'].get(cat, 0) + 1

        return json.dumps(asdict(result), indent=2)

    def apply_improvement(self, improvement_id: str) -> bool:
        """Apply a specific improvement (placeholder for future implementation)"""
        imp = next((i for i in self.improvements if i.id == improvement_id), None)
        if not imp:
            print(f"ERROR: Improvement {improvement_id} not found")
            return False

        if not imp.auto_fixable:
            print(f"ERROR: Improvement {improvement_id} is not auto-fixable")
            return False

        print(f"Applying improvement: {imp.title}")
        print("NOTE: Auto-apply feature is not yet implemented.")
        print("Please apply the suggested code manually.")
        return False

    def run(self, output_file: Optional[str] = None, json_output: bool = False,
            category_filter: Optional[str] = None, severity_filter: Optional[str] = None) -> int:
        """Run the chart improvement analysis"""
        print("=" * 60)
        print("Chart Improvement Agent for SB19 Dashboard")
        print("=" * 60)

        # Load dashboard
        if not self.load_dashboard():
            return 1

        # Find charts
        self.find_charts()

        if not self.charts:
            print("\nWARNING: No charts found in dashboard")

        # Analyze and generate improvements
        self.analyze_charts()

        # Apply filters if specified
        if category_filter:
            self.improvements = [
                imp for imp in self.improvements
                if imp.category.value == category_filter
            ]

        if severity_filter:
            self.improvements = [
                imp for imp in self.improvements
                if imp.severity.value == severity_filter
            ]

        # Generate report
        output_format = 'json' if json_output else 'text'
        report = self.generate_report(output_format)

        # Output
        if output_file:
            output_path = self.data_dir / output_file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\nReport saved to: {output_path}")
        else:
            print("\n" + report)

        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Chart Improvement Agent for SB19 Dashboard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python chart_improvement_agent.py                    # Analyze and show all improvements
  python chart_improvement_agent.py --json             # Output as JSON
  python chart_improvement_agent.py -o report.txt      # Save report to file
  python chart_improvement_agent.py --category performance  # Filter by category
  python chart_improvement_agent.py --severity high    # Filter by severity
  python chart_improvement_agent.py --list-categories  # List available categories
        '''
    )

    parser.add_argument('--output', '-o', type=str,
                        help='Output report to file')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Output in JSON format')
    parser.add_argument('--category', '-c', type=str,
                        choices=[c.value for c in ImprovementCategory],
                        help='Filter by improvement category')
    parser.add_argument('--severity', '-s', type=str,
                        choices=[s.value for s in Severity],
                        help='Filter by severity level')
    parser.add_argument('--list-categories', '-l', action='store_true',
                        help='List all improvement categories')
    parser.add_argument('--apply', '-a', type=str,
                        help='Apply a specific improvement by ID (e.g., IMP001)')

    args = parser.parse_args()

    # List categories mode
    if args.list_categories:
        print("Available improvement categories:")
        for cat in ImprovementCategory:
            rule_count = len(CHART_RULES.get(cat.value, []))
            print(f"  {cat.value:20} - {rule_count} rules")
        print("\nSeverity levels:")
        for sev in Severity:
            print(f"  {sev.value}")
        return 0

    # Run agent
    agent = ChartImprovementAgent()

    # Apply mode
    if args.apply:
        agent.load_dashboard()
        agent.find_charts()
        agent.analyze_charts()
        return 0 if agent.apply_improvement(args.apply) else 1

    # Analysis mode
    exit_code = agent.run(
        output_file=args.output,
        json_output=args.json,
        category_filter=args.category,
        severity_filter=args.severity
    )

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
