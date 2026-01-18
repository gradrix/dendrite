"""
GenerateReportTool: Format analysis results into readable reports.
Phase 9a: Enables neurons to create human-readable insights.

This tool transforms raw analytics data into formatted reports:
- Markdown formatting
- Executive summaries
- Actionable recommendations
- Trend visualizations (ASCII)
- Comparative tables
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from neural_engine.tools.base_tool import BaseTool


class GenerateReportTool(BaseTool):
    """
    Tool for generating formatted reports from analysis data.
    
    Neurons can request reports like:
    - "Generate a health report for all tools"
    - "Create an executive summary of system performance"
    - "Format the analysis results into a readable report"
    """
    
    def __init__(self):
        """Initialize GenerateReportTool."""
        super().__init__()
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return tool definition for LLM."""
        return {
            "name": "generate_report",
            "description": (
                "Generate formatted reports from analytics data. "
                "Creates markdown reports with summaries, recommendations, "
                "and visualizations. Use this to make analysis results human-readable."
            ),
            "parameters": {
                "report_type": {
                    "type": "string",
                    "description": (
                        "Type of report to generate. Options: "
                        "'health_report' (tool health summary), "
                        "'performance_report' (performance analysis), "
                        "'executive_summary' (high-level overview), "
                        "'detailed_analysis' (comprehensive breakdown), "
                        "'comparison_report' (side-by-side comparison), "
                        "'custom' (flexible custom format)"
                    ),
                    "required": True
                },
                "data": {
                    "type": "object",
                    "description": "Analysis data to format (from AnalyzeToolPerformanceTool)",
                    "required": True
                },
                "title": {
                    "type": "string",
                    "description": "Report title (optional, auto-generated if not provided)",
                    "required": False
                },
                "include_recommendations": {
                    "type": "boolean",
                    "description": "Include recommendations section (default: True)",
                    "required": False
                }
            }
        }
    
    def execute(self, report_type: str, data: Dict[str, Any],
                title: Optional[str] = None, include_recommendations: bool = True) -> Dict[str, Any]:
        """
        Generate a formatted report.
        
        Args:
            report_type: Type of report to generate
            data: Analysis data to format
            title: Report title (auto-generated if None)
            include_recommendations: Whether to include recommendations
            
        Returns:
            Formatted report as markdown string
        """
        # Map report types to generator methods
        generators = {
            "health_report": self._generate_health_report,
            "performance_report": self._generate_performance_report,
            "executive_summary": self._generate_executive_summary,
            "detailed_analysis": self._generate_detailed_analysis,
            "comparison_report": self._generate_comparison_report,
            "custom": self._generate_custom_report,
        }
        
        if report_type not in generators:
            return {
                "success": False,
                "error": f"Unknown report type: {report_type}",
                "available_types": list(generators.keys())
            }
        
        try:
            generator = generators[report_type]
            report_markdown = generator(
                data=data,
                title=title,
                include_recommendations=include_recommendations
            )
            
            return {
                "success": True,
                "report_type": report_type,
                "report": report_markdown,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "report_type": report_type,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _generate_health_report(self, data: Dict, title: Optional[str], include_recommendations: bool) -> str:
        """Generate a health report."""
        title = title or "Tool Health Report"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        lines = [
            f"# {title}",
            f"*Generated: {timestamp}*\n",
            "---\n"
        ]
        
        # Handle single tool or multiple tools
        if "tool_name" in data:
            # Single tool health check
            lines.extend(self._format_single_health(data))
        elif "categories" in data:
            # Comparative health report
            lines.extend(self._format_comparative_health(data))
        else:
            lines.append("**Error:** Unrecognized health data format\n")
        
        if include_recommendations and "recommendations" in data:
            lines.append("\n## 📋 Recommendations\n")
            for rec in data["recommendations"]:
                lines.append(f"- {rec}")
        
        return "\n".join(lines)
    
    def _format_single_health(self, data: Dict) -> List[str]:
        """Format single tool health data."""
        lines = []
        
        tool_name = data.get("tool_name", "Unknown")
        health_score = data.get("health_score", 0)
        status = data.get("health_status", "unknown")
        
        # Status emoji
        status_emoji = {
            "excellent": "🟢",
            "good": "🟡",
            "struggling": "🟠",
            "failing": "🔴",
            "unknown": "⚪"
        }.get(status, "⚪")
        
        lines.append(f"## {status_emoji} Tool: `{tool_name}`\n")
        lines.append(f"**Health Score:** {health_score}/100")
        lines.append(f"**Status:** {status.upper()}\n")
        
        # Statistics
        stats = data.get("statistics", {})
        if stats:
            lines.append("### Statistics\n")
            lines.append(f"- **Total Executions:** {stats.get('total_executions', 0)}")
            lines.append(f"- **Successful:** {stats.get('successful_executions', 0)}")
            lines.append(f"- **Failed:** {stats.get('failed_executions', 0)}")
            
            if stats.get('avg_duration_ms'):
                lines.append(f"- **Avg Duration:** {stats['avg_duration_ms']:.1f}ms")
            
            if stats.get('last_used'):
                lines.append(f"- **Last Used:** {stats['last_used']}")
        
        return lines
    
    def _format_comparative_health(self, data: Dict) -> List[str]:
        """Format comparative health data."""
        lines = []
        
        total = data.get("total_tools_analyzed", 0)
        lines.append(f"## Overview\n")
        lines.append(f"**Total Tools Analyzed:** {total}\n")
        
        categories = data.get("categories", {})
        
        # Summary table
        lines.append("### Health Distribution\n")
        lines.append("| Category | Count | Percentage |")
        lines.append("|----------|-------|------------|")
        
        for cat_name, cat_data in categories.items():
            count = cat_data.get("count", 0)
            pct = (count / total * 100) if total > 0 else 0
            emoji = {
                "excellent": "🟢",
                "good": "🟡",
                "struggling": "🟠",
                "failing": "🔴"
            }.get(cat_name, "")
            lines.append(f"| {emoji} {cat_name.title()} | {count} | {pct:.1f}% |")
        
        lines.append("")
        
        # Best/worst performers
        if data.get("best_performer"):
            best = data["best_performer"]
            lines.append(f"### 🏆 Best Performer\n")
            lines.append(f"**Tool:** `{best['tool_name']}`")
            lines.append(f"**Success Rate:** {best['success_rate']}%")
            lines.append(f"**Executions:** {best['total_executions']}\n")
        
        if data.get("worst_performer"):
            worst = data["worst_performer"]
            lines.append(f"### ⚠️ Needs Attention\n")
            lines.append(f"**Tool:** `{worst['tool_name']}`")
            lines.append(f"**Success Rate:** {worst['success_rate']}%")
            lines.append(f"**Executions:** {worst['total_executions']}\n")
        
        return lines
    
    def _generate_performance_report(self, data: Dict, title: Optional[str], include_recommendations: bool) -> str:
        """Generate a performance report."""
        title = title or "Performance Analysis Report"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        lines = [
            f"# {title}",
            f"*Generated: {timestamp}*\n",
            "---\n"
        ]
        
        if "tool_name" in data:
            tool_name = data.get("tool_name")
            lines.append(f"## Tool: `{tool_name}`\n")
            
            # Degradation analysis
            if "degradation_detected" in data:
                degraded = data["degradation_detected"]
                emoji = "⚠️" if degraded else "✅"
                status = "DEGRADATION DETECTED" if degraded else "Performance Stable"
                
                lines.append(f"### {emoji} {status}\n")
                
                if data.get("current_success_rate") is not None:
                    lines.append(f"**Current Success Rate:** {data['current_success_rate']}%\n")
                
                if data.get("indicators"):
                    lines.append("**Indicators:**")
                    for indicator in data["indicators"]:
                        lines.append(f"- {indicator}")
                    lines.append("")
        
        if include_recommendations and data.get("recommendations"):
            lines.append("## 📋 Recommendations\n")
            for rec in data["recommendations"]:
                lines.append(f"- {rec}")
        
        return "\n".join(lines)
    
    def _generate_executive_summary(self, data: Dict, title: Optional[str], include_recommendations: bool) -> str:
        """Generate an executive summary."""
        title = title or "Executive Summary"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        lines = [
            f"# {title}",
            f"*Generated: {timestamp}*\n",
            "---\n",
            "## Key Highlights\n"
        ]
        
        # Extract key metrics
        if "total_tools_analyzed" in data:
            lines.append(f"- **Total Tools:** {data['total_tools_analyzed']}")
        
        if "categories" in data:
            categories = data["categories"]
            excellent_count = categories.get("excellent", {}).get("count", 0)
            failing_count = categories.get("failing", {}).get("count", 0)
            
            lines.append(f"- **Excellent Performers:** {excellent_count}")
            lines.append(f"- **Tools Needing Attention:** {failing_count}")
        
        if "best_performer" in data:
            best = data["best_performer"]
            lines.append(f"- **Best Tool:** `{best['tool_name']}` ({best['success_rate']}%)")
        
        lines.append("\n## Status Overview\n")
        
        # Visual indicator
        if "categories" in data:
            lines.append(self._create_ascii_bar_chart(data["categories"]))
        
        if include_recommendations and data.get("recommendations"):
            lines.append("\n## 🎯 Action Items\n")
            for rec in data["recommendations"][:5]:  # Top 5 recommendations
                lines.append(f"- {rec}")
        
        return "\n".join(lines)
    
    def _generate_detailed_analysis(self, data: Dict, title: Optional[str], include_recommendations: bool) -> str:
        """Generate a detailed analysis report."""
        title = title or "Detailed Analysis Report"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        lines = [
            f"# {title}",
            f"*Generated: {timestamp}*\n",
            "---\n",
            "## Full Analysis\n"
        ]
        
        # Include all data in structured format
        lines.append("```json")
        import json
        lines.append(json.dumps(data, indent=2, default=str))
        lines.append("```\n")
        
        return "\n".join(lines)
    
    def _generate_comparison_report(self, data: Dict, title: Optional[str], include_recommendations: bool) -> str:
        """Generate a comparison report."""
        title = title or "Tool Comparison Report"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        lines = [
            f"# {title}",
            f"*Generated: {timestamp}*\n",
            "---\n"
        ]
        
        if "categories" in data:
            categories = data["categories"]
            
            for cat_name, cat_data in categories.items():
                tools = cat_data.get("tools", [])
                if not tools:
                    continue
                
                emoji = {
                    "excellent": "🟢",
                    "good": "🟡",
                    "struggling": "🟠",
                    "failing": "🔴"
                }.get(cat_name, "")
                
                lines.append(f"## {emoji} {cat_name.title()} ({len(tools)} tools)\n")
                lines.append("| Tool Name | Success Rate | Executions | Avg Duration |")
                lines.append("|-----------|--------------|------------|--------------|")
                
                for tool in tools[:10]:  # Top 10 per category
                    name = tool['tool_name']
                    rate = tool['success_rate']
                    execs = tool['total_executions']
                    duration = tool.get('avg_duration_ms', 'N/A')
                    if duration != 'N/A':
                        duration = f"{duration:.1f}ms"
                    
                    lines.append(f"| `{name}` | {rate}% | {execs} | {duration} |")
                
                lines.append("")
        
        if include_recommendations and data.get("recommendations"):
            lines.append("## 📋 Recommendations\n")
            for rec in data["recommendations"]:
                lines.append(f"- {rec}")
        
        return "\n".join(lines)
    
    def _generate_custom_report(self, data: Dict, title: Optional[str], include_recommendations: bool) -> str:
        """Generate a custom flexible report."""
        title = title or "Custom Report"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        lines = [
            f"# {title}",
            f"*Generated: {timestamp}*\n",
            "---\n",
            "## Data\n"
        ]
        
        # Format data as key-value pairs
        for key, value in data.items():
            if key == "recommendations" and include_recommendations:
                continue  # Handle separately
            
            lines.append(f"**{key.replace('_', ' ').title()}:** {value}\n")
        
        if include_recommendations and data.get("recommendations"):
            lines.append("## 📋 Recommendations\n")
            for rec in data["recommendations"]:
                lines.append(f"- {rec}")
        
        return "\n".join(lines)
    
    def _create_ascii_bar_chart(self, categories: Dict) -> str:
        """Create a simple ASCII bar chart."""
        lines = []
        
        total = sum(cat.get("count", 0) for cat in categories.values())
        if total == 0:
            return "No data available"
        
        max_width = 40
        
        for cat_name, cat_data in categories.items():
            count = cat_data.get("count", 0)
            pct = (count / total * 100) if total > 0 else 0
            bar_width = int((count / total) * max_width) if total > 0 else 0
            
            emoji = {
                "excellent": "🟢",
                "good": "🟡",
                "struggling": "🟠",
                "failing": "🔴"
            }.get(cat_name, "")
            
            bar = "█" * bar_width
            lines.append(f"{emoji} {cat_name.title():<12} | {bar} {count} ({pct:.1f}%)")
        
        return "\n".join(lines)
    
    def close(self):
        """No resources to close."""
        pass
