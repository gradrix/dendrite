#!/usr/bin/env python3
"""
Simple CLI tool for direct Strava queries.
Bypasses LLM for simple tool calls.

Usage:
  ./query.py activities [--limit N]
  ./query.py kudos <activity_id>
  ./query.py feed [--hours N]
  ./query.py following
  ./query.py followers
"""

import sys
import os
import argparse
import json
from datetime import datetime, timedelta

# Add current directory to path
sys.path.insert(0, os.getcwd())

from tools.strava_tools import (
    get_client,
    get_activity_kudos,
    get_my_activities,
    get_dashboard_feed
)

def format_activity(activity):
    """Format activity for display."""
    name = activity.get('name', 'Unknown')
    activity_type = activity.get('type') or activity.get('sport_type', 'Unknown')
    distance = activity.get('distance', 0)
    kudos = activity.get('kudos_count', 0)
    
    # Format distance
    if distance > 1000:
        dist_str = f"{distance/1000:.1f}km"
    else:
        dist_str = f"{distance:.0f}m"
    
    return f"{name} - {activity_type} - {dist_str} - {kudos} kudos"

def cmd_activities(args):
    """Get recent activities."""
    print(f"📱 Fetching last {args.limit} activities...")
    
    result = get_my_activities(per_page=args.limit)
    
    if not result.get('success'):
        print(f"❌ Error: {result.get('error')}")
        return 1
    
    activities = result.get('activities', [])
    print(f"\n✅ Found {len(activities)} activities:\n")
    
    for i, act in enumerate(activities, 1):
        print(f"  {i}. {format_activity(act)}")
        print(f"     ID: {act.get('id')}")
        print()
    
    return 0

def cmd_kudos(args):
    """Get kudos for an activity."""
    print(f"👍 Fetching kudos for activity {args.activity_id}...")
    
    result = get_activity_kudos(activity_id=args.activity_id)
    
    if not result.get('success'):
        print(f"❌ Error: {result.get('error')}")
        return 1
    
    athletes = result.get('athletes', [])
    count = result.get('kudos_count', len(athletes))
    
    print(f"\n✅ Found {count} kudos:\n")
    
    for i, athlete in enumerate(athletes, 1):
        name = athlete.get('name', 'Unknown')
        athlete_id = athlete.get('id', '?')
        print(f"  {i}. {name} (ID: {athlete_id})")
    
    return 0

def cmd_feed(args):
    """Get dashboard feed."""
    print(f"📰 Fetching feed from last {args.hours} hours...")
    
    result = get_dashboard_feed(hours_ago=args.hours, num_entries=args.limit)
    
    if not isinstance(result, list):
        print(f"❌ Error: Unexpected response")
        return 1
    
    print(f"\n✅ Found {len(result)} activities:\n")
    
    for i, entry in enumerate(result, 1):
        athlete = entry.get('athlete_name', 'Unknown')
        activity_type = entry.get('activity_type', 'Unknown')
        activity_name = entry.get('activity_name', '')
        kudos_given = entry.get('you_gave_kudos', False)
        total_kudos = entry.get('total_kudos', 0)
        
        kudos_emoji = "✅" if kudos_given else "⭕"
        
        print(f"  {i}. {kudos_emoji} {athlete} - {activity_type}")
        if activity_name:
            print(f"     \"{activity_name}\"")
        print(f"     Total kudos: {total_kudos}")
        print()
    
    return 0

def cmd_following(args):
    """Get athletes you follow."""
    print("👥 Fetching athletes you follow...")
    
    client = get_client()
    following = client.get_following()
    
    if not following:
        print("No following data available")
        return 1
    
    print(f"\n✅ You follow {len(following)} athletes:\n")
    
    for i, athlete in enumerate(following[:args.limit], 1):
        name = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
        username = athlete.get('username', '')
        athlete_id = athlete.get('id', '?')
        
        print(f"  {i}. {name} (@{username}) - ID: {athlete_id}")
    
    if len(following) > args.limit:
        print(f"\n  ... and {len(following) - args.limit} more")
    
    return 0

def cmd_followers(args):
    """Get your followers."""
    print("👥 Fetching your followers...")
    
    client = get_client()
    followers = client.get_followers(per_page=args.limit)
    
    if not followers:
        print("No followers data available")
        return 1
    
    print(f"\n✅ You have {len(followers)} followers:\n")
    
    for i, athlete in enumerate(followers, 1):
        name = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
        username = athlete.get('username', '')
        athlete_id = athlete.get('id', '?')
        
        print(f"  {i}. {name} (@{username}) - ID: {athlete_id}")
    
    return 0

def main():
    parser = argparse.ArgumentParser(
        description='Query Strava data directly (no LLM)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s activities --limit 5          # Get last 5 activities
  %(prog)s kudos 16229059176             # Get kudos for activity
  %(prog)s feed --hours 24               # Get feed from last 24h
  %(prog)s following --limit 20          # Get first 20 you follow
  %(prog)s followers --limit 20          # Get first 20 followers
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # activities command
    activities_parser = subparsers.add_parser('activities', help='Get your recent activities')
    activities_parser.add_argument('--limit', type=int, default=10, help='Number of activities (default: 10)')
    activities_parser.set_defaults(func=cmd_activities)
    
    # kudos command
    kudos_parser = subparsers.add_parser('kudos', help='Get kudos for an activity')
    kudos_parser.add_argument('activity_id', type=int, help='Activity ID')
    kudos_parser.set_defaults(func=cmd_kudos)
    
    # feed command
    feed_parser = subparsers.add_parser('feed', help='Get dashboard feed')
    feed_parser.add_argument('--hours', type=int, default=24, help='Hours to look back (default: 24)')
    feed_parser.add_argument('--limit', type=int, default=20, help='Number of entries (default: 20)')
    feed_parser.set_defaults(func=cmd_feed)
    
    # following command
    following_parser = subparsers.add_parser('following', help='Get athletes you follow')
    following_parser.add_argument('--limit', type=int, default=50, help='Number to show (default: 50)')
    following_parser.set_defaults(func=cmd_following)
    
    # followers command
    followers_parser = subparsers.add_parser('followers', help='Get your followers')
    followers_parser.add_argument('--limit', type=int, default=50, help='Number to show (default: 50)')
    followers_parser.set_defaults(func=cmd_followers)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
