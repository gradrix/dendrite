"""
Demo script for Phase 8c: Analytics Engine and Scheduled Jobs.
Demonstrates analytics capabilities and insights generation.
"""

from neural_engine.core.analytics_engine import AnalyticsEngine
from neural_engine.core.execution_store import ExecutionStore
import json


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def main():
    print_section("Phase 8c: Analytics Engine Demo")
    
    # Initialize components
    print("\n1. Initializing AnalyticsEngine...")
    store = ExecutionStore()
    analytics = AnalyticsEngine(store)
    print("   ✓ Analytics engine ready")
    
    # Hourly job
    print_section("Hourly Job: Statistics Update")
    result = analytics.hourly_statistics_update()
    print(f"   Status: {result['status']}")
    print(f"   Duration: {result['duration_seconds']:.3f}s")
    
    # Daily tool analysis
    print_section("Daily Job: Tool Analysis")
    result = analytics.daily_tool_analysis()
    if result['status'] == 'success':
        cats = result['categories']
        print(f"   Tools analyzed: {result['total_tools_analyzed']}")
        print(f"   ✓ Excellent (>90%): {cats['excellent']} tools")
        print(f"   ✓ Good (70-90%): {cats['good']} tools")
        print(f"   ⚠ Struggling (50-70%): {cats['struggling']} tools")
        print(f"   ✗ Failing (<50%): {cats['failing']} tools")
        
        if result['recommendations']:
            print(f"\n   Recommendations:")
            for rec in result['recommendations'][:3]:
                priority_icon = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
                print(f"     {priority_icon} [{rec['priority'].upper()}] {rec['message']}")
    
    # Daily performance analysis
    print_section("Daily Job: Performance Analysis")
    result = analytics.daily_performance_analysis()
    if result['status'] == 'success':
        metrics = result['performance_metrics']
        print(f"   Executions analyzed: {result['executions_analyzed']}")
        print(f"   Average duration: {metrics['avg_duration_ms']:.0f}ms")
        print(f"   P50 (median): {metrics['p50_duration_ms']}ms")
        print(f"   P95: {metrics['p95_duration_ms']}ms")
        print(f"   P99: {metrics['p99_duration_ms']}ms")
        print(f"   Success rate: {metrics['success_rate']:.1%}")
        
        print(f"\n   Intent breakdown:")
        for intent, count in result['intent_breakdown'].items():
            print(f"     - {intent}: {count} executions")
        
        if result['recommendations']:
            print(f"\n   Performance recommendations:")
            for rec in result['recommendations'][:2]:
                print(f"     • {rec['message']}")
    
    # Weekly lifecycle management
    print_section("Weekly Job: Tool Lifecycle Management")
    result = analytics.weekly_tool_lifecycle_management()
    if result['status'] == 'success':
        actions = result['actions']
        print(f"   Tools reviewed: {result['tools_reviewed']}")
        print(f"   ↑ Promotion candidates: {len(actions['promote'])} tools")
        print(f"   ↓ Deprecation candidates: {len(actions['deprecate'])} tools")
        print(f"   📦 Archive candidates: {len(actions['archive'])} tools")
        
        if actions['promote']:
            print(f"\n   Ready for promotion:")
            for tool in actions['promote'][:3]:
                print(f"     - {tool['tool']}: {tool['success_rate']:.1%} success, {tool['executions']} runs")
        
        if actions['deprecate']:
            print(f"\n   ⚠️  Should be deprecated:")
            for tool in actions['deprecate'][:3]:
                print(f"     - {tool['tool']}: {tool['success_rate']:.1%} success ({tool['reason']})")
    
    # Goal pattern analysis
    print_section("On-Demand: Goal Pattern Analysis")
    result = analytics.analyze_goal_patterns(limit=50)
    if result['status'] == 'success':
        print(f"   Analyzed {result['executions_analyzed']} recent goals")
        print(f"\n   Top keywords:")
        for kw in result['top_keywords'][:10]:
            print(f"     - '{kw['word']}': {kw['count']} times")
        
        print(f"\n   Intent distribution:")
        for intent, count in result['intent_distribution'].items():
            print(f"     - {intent}: {count} goals")
    
    # Tool insights
    print_section("On-Demand: Tool Insights")
    top_tools = store.get_top_tools(limit=3, min_executions=1)
    if top_tools:
        for i, tool_data in enumerate(top_tools, 1):
            tool_name = tool_data['tool_name']
            print(f"\n   {i}. Analyzing: {tool_name}")
            insights = analytics.get_tool_insights(tool_name)
            
            if insights['status'] != 'not_found':
                stats = insights['statistics']
                print(f"      Status: {insights['status']}")
                print(f"      Health Score: {insights['health_score']:.1f}/100")
                print(f"      Success Rate: {stats['success_rate']:.1%}")
                print(f"      Total Executions: {stats['total_executions']}")
                if stats['avg_duration_ms']:
                    print(f"      Avg Duration: {stats['avg_duration_ms']:.0f}ms")
                
                if insights['recommendations']:
                    print(f"      Recommendations:")
                    for rec in insights['recommendations']:
                        print(f"        • {rec['message']}")
    else:
        print("   No tools with sufficient data yet")
    
    # Dashboard data
    print_section("Dashboard Data Generation")
    dashboard = analytics.generate_dashboard_data()
    overview = dashboard['overview']
    print(f"   Total executions today: {overview['total_executions_today']}")
    print(f"   Successful: {overview['successful_executions']}")
    print(f"   Failed: {overview['failed_executions']}")
    print(f"   Overall success rate: {overview['overall_success_rate']:.1%}")
    print(f"   Total tools tracked: {overview['total_tools']}")
    
    print(f"\n   Top {len(dashboard['top_tools'])} tools:")
    for tool in dashboard['top_tools']:
        print(f"     - {tool['name']}: {tool['success_rate']:.1%} success ({tool['executions']} runs)")
    
    print(f"\n   Recent activity (last {len(dashboard['recent_activity'])} executions):")
    for activity in dashboard['recent_activity'][:5]:
        success_icon = "✓" if activity['success'] else "✗"
        print(f"     {success_icon} [{activity['intent']}] {activity['goal_text']}")
        print(f"        Duration: {activity['duration_ms']}ms @ {activity['created_at']}")
    
    print_section("Summary")
    print("✓ Phase 8c Analytics Engine is fully operational")
    print("\nCapabilities demonstrated:")
    print("  • Hourly statistics updates")
    print("  • Daily tool performance analysis")
    print("  • Daily execution performance metrics")
    print("  • Weekly tool lifecycle management")
    print("  • Goal pattern analysis")
    print("  • Individual tool insights with health scores")
    print("  • Dashboard data generation")
    print("\nAll analytics jobs can be scheduled via cron or systemd timers")
    print("=" * 80)
    
    # Cleanup
    analytics.close()


if __name__ == "__main__":
    main()
