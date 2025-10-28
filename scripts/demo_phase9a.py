#!/usr/bin/env python3
"""
Phase 9a Demo: Neuron-Driven Analytics
======================================

Demonstrates how neurons can use analytics tools to investigate their own performance.
This is revolutionary - the system becomes self-aware and can answer questions like:
- "Why did tool X fail yesterday?"
- "Which tools need attention?"
- "How is my overall system health?"

The complete pipeline: Query → Analyze → Report
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neural_engine.core.execution_store import ExecutionStore
from neural_engine.tools.query_execution_store_tool import QueryExecutionStoreTool
from neural_engine.tools.analyze_tool_performance_tool import AnalyzeToolPerformanceTool
from neural_engine.tools.generate_report_tool import GenerateReportTool


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def demo_query_tool():
    """Demo 1: Query execution history."""
    print_section("DEMO 1: Querying Execution History")
    
    store = ExecutionStore()
    query_tool = QueryExecutionStoreTool(execution_store=store)
    
    # Query 1: Get statistics for a specific tool
    print("🔍 Query: 'Show me statistics for prime_checker_tool'")
    print("-" * 80)
    result = query_tool.execute(
        query_type="tool_stats",
        tool_name="prime_checker_tool"
    )
    
    if result["success"] and result["results"]:
        stats = result["results"]
        print(f"Tool: {stats.get('tool_name', 'N/A')}")
        print(f"Total Executions: {stats.get('total_executions', 0)}")
        print(f"Successful: {stats.get('successful_executions', 0)}")
        print(f"Failed: {stats.get('failed_executions', 0)}")
        print(f"Success Rate: {stats.get('success_rate', 0) * 100:.1f}%")
        print(f"Avg Duration: {stats.get('avg_duration_ms', 0):.1f}ms")
    else:
        print("No statistics found for prime_checker_tool")
    
    # Query 2: Show recent failures
    print("\n🔍 Query: 'What tools have failed recently?'")
    print("-" * 80)
    result = query_tool.execute(
        query_type="recent_failures",
        limit=5
    )
    
    if result["success"] and result["count"] > 0:
        print(f"Found {result['count']} recent failures:\n")
        for i, failure in enumerate(result["results"][:5], 1):
            print(f"{i}. {failure.get('tool_name', 'unknown')}")
            print(f"   Error: {failure.get('error', 'No error message')}")
            print(f"   Time: {failure.get('created_at', 'unknown')}")
            print()
    else:
        print("No recent failures found!")
    
    # Query 3: Find slow executions
    print("🔍 Query: 'Which executions took longer than 1 second?'")
    print("-" * 80)
    result = query_tool.execute(
        query_type="slow_executions",
        threshold_ms=1000,
        limit=5
    )
    
    if result["success"] and result["count"] > 0:
        print(f"Found {result['count']} slow executions:\n")
        for i, slow in enumerate(result["results"][:5], 1):
            print(f"{i}. {slow.get('tool_name', 'unknown')}: {slow.get('duration_ms', 0)}ms")
    else:
        print("No slow executions found!")
    
    # Query 4: Top performing tools
    print("\n🔍 Query: 'Which are my most frequently used tools?'")
    print("-" * 80)
    result = query_tool.execute(
        query_type="top_tools",
        limit=5
    )
    
    if result["success"] and result["count"] > 0:
        print("Top Tools by Usage:\n")
        for i, tool in enumerate(result["results"], 1):
            print(f"{i}. {tool.get('tool_name', 'unknown')}")
            print(f"   Executions: {tool.get('total_executions', 0)}")
            print(f"   Success Rate: {tool.get('success_rate', 0) * 100:.1f}%")
            print()
    else:
        print("No tools with sufficient usage found")
    
    query_tool.close()
    store.close()


def demo_analyze_tool():
    """Demo 2: Analyze tool performance."""
    print_section("DEMO 2: Analyzing Tool Performance")
    
    store = ExecutionStore()
    analyzer = AnalyzeToolPerformanceTool(execution_store=store)
    
    # Get a tool to analyze
    query_tool = QueryExecutionStoreTool(execution_store=store)
    top_tools_result = query_tool.execute(query_type="top_tools", limit=1)
    
    if top_tools_result["success"] and top_tools_result["count"] > 0:
        tool_name = top_tools_result["results"][0]["tool_name"]
        
        # Analysis 1: Health Check
        print(f"🏥 Analysis: 'How healthy is {tool_name}?'")
        print("-" * 80)
        result = analyzer.execute(
            analysis_type="health_check",
            tool_name=tool_name
        )
        
        if result["success"]:
            analysis = result["results"]
            status_emoji = {
                "excellent": "🟢",
                "good": "🟡",
                "struggling": "🟠",
                "failing": "🔴",
                "unknown": "⚪"
            }.get(analysis.get("health_status", "unknown"), "⚪")
            
            print(f"{status_emoji} Health Score: {analysis.get('health_score', 0):.1f}/100")
            print(f"Status: {analysis.get('health_status', 'unknown').upper()}")
            print(f"\nStatistics:")
            stats = analysis.get("statistics", {})
            print(f"  Total Executions: {stats.get('total_executions', 0)}")
            print(f"  Success Rate: {stats.get('success_rate', 0) * 100:.1f}%")
            print(f"  Avg Duration: {stats.get('avg_duration_ms', 0):.1f}ms")
            
            print(f"\n💡 Recommendations:")
            for rec in analysis.get("recommendations", []):
                print(f"  - {rec}")
        
        # Analysis 2: Performance Degradation
        print(f"\n📉 Analysis: 'Is {tool_name} degrading?'")
        print("-" * 80)
        result = analyzer.execute(
            analysis_type="performance_degradation",
            tool_name=tool_name
        )
        
        if result["success"]:
            analysis = result["results"]
            degraded = analysis.get("degradation_detected", False)
            
            if degraded:
                print("⚠️ DEGRADATION DETECTED!")
                print(f"Current Success Rate: {analysis.get('current_success_rate', 0)}%")
                print("\nIndicators:")
                for indicator in analysis.get("indicators", []):
                    print(f"  - {indicator}")
            else:
                print("✅ No degradation detected")
                print(f"Current Success Rate: {analysis.get('current_success_rate', 0)}%")
    
    # Analysis 3: Comparative Analysis
    print("\n📊 Analysis: 'How do all my tools compare?'")
    print("-" * 80)
    result = analyzer.execute(analysis_type="comparative_analysis")
    
    if result["success"]:
        analysis = result["results"]
        categories = analysis.get("categories", {})
        
        print(f"Total Tools Analyzed: {analysis.get('total_tools_analyzed', 0)}\n")
        
        for cat_name, cat_data in categories.items():
            emoji = {
                "excellent": "🟢",
                "good": "🟡",
                "struggling": "🟠",
                "failing": "🔴"
            }.get(cat_name, "")
            count = cat_data.get("count", 0)
            print(f"{emoji} {cat_name.title()}: {count} tools")
        
        best = analysis.get("best_performer")
        worst = analysis.get("worst_performer")
        
        if best:
            print(f"\n🏆 Best Performer: {best['tool_name']}")
            print(f"   Success Rate: {best['success_rate']}%")
        
        if worst:
            print(f"\n⚠️ Needs Attention: {worst['tool_name']}")
            print(f"   Success Rate: {worst['success_rate']}%")
    
    analyzer.close()
    query_tool.close()
    store.close()


def demo_generate_report():
    """Demo 3: Generate formatted reports."""
    print_section("DEMO 3: Generating Reports")
    
    store = ExecutionStore()
    analyzer = AnalyzeToolPerformanceTool(execution_store=store)
    reporter = GenerateReportTool()
    
    # Get comparative analysis
    print("📝 Generating Executive Summary Report...")
    print("-" * 80)
    
    analysis_result = analyzer.execute(analysis_type="comparative_analysis")
    
    if analysis_result["success"]:
        report_result = reporter.execute(
            report_type="executive_summary",
            data=analysis_result["results"],
            title="System Health Executive Summary"
        )
        
        if report_result["success"]:
            print(report_result["report"])
    
    # Generate health report for specific tool
    query_tool = QueryExecutionStoreTool(execution_store=store)
    top_tools = query_tool.execute(query_type="top_tools", limit=1)
    
    if top_tools["success"] and top_tools["count"] > 0:
        tool_name = top_tools["results"][0]["tool_name"]
        
        print(f"\n📝 Generating Detailed Health Report for {tool_name}...")
        print("-" * 80)
        
        health_result = analyzer.execute(
            analysis_type="health_check",
            tool_name=tool_name
        )
        
        if health_result["success"]:
            report_result = reporter.execute(
                report_type="health_report",
                data=health_result["results"],
                include_recommendations=True
            )
            
            if report_result["success"]:
                print(report_result["report"])
    
    reporter.close()
    analyzer.close()
    query_tool.close()
    store.close()


def demo_full_pipeline():
    """Demo 4: Complete Query → Analyze → Report pipeline."""
    print_section("DEMO 4: Complete Self-Investigation Pipeline")
    
    print("🧠 Neuron Question: 'Why are some of my tools failing?'\n")
    print("Pipeline: Query → Analyze → Report")
    print("-" * 80)
    
    store = ExecutionStore()
    
    # Step 1: Query for failures
    print("\n📍 STEP 1: Query execution history")
    query_tool = QueryExecutionStoreTool(execution_store=store)
    failures = query_tool.execute(query_type="recent_failures", limit=10)
    
    if failures["success"] and failures["count"] > 0:
        print(f"✓ Found {failures['count']} recent failures")
        
        # Group failures by tool
        tool_failures = {}
        for failure in failures["results"]:
            tool = failure.get("tool_name", "unknown")
            if tool not in tool_failures:
                tool_failures[tool] = 0
            tool_failures[tool] += 1
        
        print(f"✓ Identified {len(tool_failures)} tools with failures")
    else:
        print("✓ No recent failures (system is healthy!)")
        tool_failures = {}
    
    # Step 2: Analyze failure patterns
    print("\n📍 STEP 2: Analyze failure patterns")
    analyzer = AnalyzeToolPerformanceTool(execution_store=store)
    failure_analysis = analyzer.execute(analysis_type="failure_patterns")
    
    if failure_analysis["success"]:
        print(f"✓ Analysis complete")
        total_failing = failure_analysis["results"].get("total_failing_tools", 0)
        print(f"✓ {total_failing} tools have recorded failures")
    
    # Step 3: Generate comprehensive report
    print("\n📍 STEP 3: Generate actionable report")
    reporter = GenerateReportTool()
    
    # Create custom report data
    report_data = {
        "question": "Why are some of my tools failing?",
        "failure_count": failures["count"] if failures["success"] else 0,
        "tools_with_failures": len(tool_failures),
        "failure_analysis": failure_analysis["results"] if failure_analysis["success"] else {},
        "recommendations": [
            "Review error logs for failing tools",
            "Check if external dependencies are available",
            "Consider adding retry logic for transient failures",
            "Monitor degradation patterns over time"
        ]
    }
    
    report_result = reporter.execute(
        report_type="custom",
        data=report_data,
        title="Failure Investigation Report",
        include_recommendations=True
    )
    
    if report_result["success"]:
        print("✓ Report generated\n")
        print(report_result["report"])
    
    # Cleanup
    reporter.close()
    analyzer.close()
    query_tool.close()
    store.close()


def demo_real_world_questions():
    """Demo 5: Answering real-world questions."""
    print_section("DEMO 5: Self-Aware System - Real World Questions")
    
    store = ExecutionStore()
    query_tool = QueryExecutionStoreTool(execution_store=store)
    analyzer = AnalyzeToolPerformanceTool(execution_store=store)
    reporter = GenerateReportTool()
    
    questions = [
        {
            "question": "🤔 Which tools should I optimize first?",
            "approach": "Find tools with high usage but struggling performance"
        },
        {
            "question": "🤔 Are there any tools I should deprecate?",
            "approach": "Find tools with consistently low success rates"
        },
        {
            "question": "🤔 What's my system's overall health?",
            "approach": "Get comparative analysis and generate executive summary"
        }
    ]
    
    for q in questions:
        print(f"\n{q['question']}")
        print(f"Approach: {q['approach']}")
        print("-" * 80)
        
        if "optimize first" in q["question"]:
            # Find high-usage tools with issues
            top_tools = query_tool.execute(query_type="top_tools", limit=10)
            if top_tools["success"] and top_tools["count"] > 0:
                # Check health of each
                optimization_candidates = []
                for tool in top_tools["results"][:5]:
                    health = analyzer.execute(
                        analysis_type="health_check",
                        tool_name=tool["tool_name"]
                    )
                    if health["success"]:
                        score = health["results"]["health_score"]
                        if 50 <= score < 80:  # Struggling but used
                            optimization_candidates.append({
                                "tool": tool["tool_name"],
                                "score": score,
                                "usage": tool["total_executions"]
                            })
                
                if optimization_candidates:
                    print("💡 Optimization Priorities:\n")
                    for i, candidate in enumerate(optimization_candidates, 1):
                        print(f"{i}. {candidate['tool']}")
                        print(f"   Health: {candidate['score']:.1f}/100")
                        print(f"   Usage: {candidate['usage']} executions")
                        print()
                else:
                    print("✅ All high-usage tools are performing well!")
        
        elif "deprecate" in q["question"]:
            # Find consistently failing tools
            failure_patterns = analyzer.execute(analysis_type="failure_patterns")
            if failure_patterns["success"]:
                failing = failure_patterns["results"].get("top_failing_tools", [])
                if failing:
                    print("🚨 Tools to Consider Deprecating:\n")
                    for i, tool in enumerate(failing[:3], 1):
                        if tool["failure_rate"] > 70:
                            print(f"{i}. {tool['tool_name']}")
                            print(f"   Failure Rate: {tool['failure_rate']}%")
                            print(f"   Total Failures: {tool['failures']}")
                            print()
                else:
                    print("✅ No tools with excessive failure rates!")
        
        elif "overall health" in q["question"]:
            # Comprehensive system health
            comp = analyzer.execute(analysis_type="comparative_analysis")
            if comp["success"]:
                report = reporter.execute(
                    report_type="executive_summary",
                    data=comp["results"],
                    title="System Health Overview"
                )
                if report["success"]:
                    # Print just the highlights
                    categories = comp["results"]["categories"]
                    total = comp["results"]["total_tools_analyzed"]
                    excellent = categories.get("excellent", {}).get("count", 0)
                    failing = categories.get("failing", {}).get("count", 0)
                    
                    overall_health = (excellent / total * 100) if total > 0 else 0
                    
                    print(f"System Health: {overall_health:.1f}%")
                    print(f"Total Tools: {total}")
                    print(f"🟢 Excellent: {excellent}")
                    print(f"🔴 Failing: {failing}")
                    
                    if overall_health >= 80:
                        print("\n✅ System is healthy!")
                    elif overall_health >= 60:
                        print("\n⚠️ System needs attention")
                    else:
                        print("\n🚨 System requires immediate action")
    
    reporter.close()
    analyzer.close()
    query_tool.close()
    store.close()


def main():
    """Run all demos."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                   PHASE 9a: NEURON-DRIVEN ANALYTICS                          ║
║                        Self-Aware System Demo                                ║
║                                                                              ║
║  The system can now investigate its own performance and answer questions:    ║
║  • "Why did tool X fail yesterday?"                                          ║
║  • "Which tools need attention?"                                             ║
║  • "How is my overall system health?"                                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Run demos
        demo_query_tool()
        demo_analyze_tool()
        demo_generate_report()
        demo_full_pipeline()
        demo_real_world_questions()
        
        print_section("✅ DEMO COMPLETE")
        print("""
Phase 9a Tools Demonstrated:
✓ QueryExecutionStoreTool - 8 query types for execution history
✓ AnalyzeToolPerformanceTool - 6 analysis types for performance insights
✓ GenerateReportTool - 6 report formats for human-readable output

Key Benefits:
✓ Neurons can investigate themselves (self-awareness)
✓ Natural language analytics queries
✓ Automated health monitoring
✓ Proactive problem detection
✓ Data-driven decision making

Next Steps:
→ Phase 9b: Create Self-Investigation Neuron
→ Phase 9c: Autonomous Improvement Capabilities
→ Fractal Architecture: Recursive self-improvement
        """)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Demo interrupted by user")
        return 130
    except Exception as e:
        print(f"\n\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
