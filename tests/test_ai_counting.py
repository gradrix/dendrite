#!/usr/bin/env python3
"""Test AI counting with actual September 2024 data"""

import json

# Simulate the activities data (compact format)
activities = [
    {'name': 'Lunch Table Tennis', 'type': 'Workout', 'sport_type': 'TableTennis', 'date': '2024-09-30'},
    {'name': 'Morning Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-30'},
    {'name': 'crash & grill Gravel Ride', 'type': 'Ride', 'sport_type': 'GravelRide', 'date': '2024-09-28'},
    {'name': 'reikia geresnio žibinto Trail Run', 'type': 'Run', 'sport_type': 'TrailRun', 'date': '2024-09-27'},
    {'name': 'Evening Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-27'},
    {'name': 'Morning Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-27'},
    {'name': 'Afternoon Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-25'},
    {'name': 'Afternoon Table Tennis', 'type': 'Workout', 'sport_type': 'TableTennis', 'date': '2024-09-25'},
    {'name': 'Morning Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-25'},
    {'name': 'Easyish Run', 'type': 'Run', 'sport_type': 'Run', 'date': '2024-09-24'},
    {'name': 'Evening Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-24'},
    {'name': 'Lunch Table Tennis', 'type': 'Workout', 'sport_type': 'TableTennis', 'date': '2024-09-24'},
    {'name': 'Morning Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-24'},
    {'name': 'Afternoon Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-23'},
    {'name': 'Lunch Table Tennis', 'type': 'Workout', 'sport_type': 'TableTennis', 'date': '2024-09-23'},
    {'name': 'Cardio Run', 'type': 'Run', 'sport_type': 'Run', 'date': '2024-09-22'},
    {'name': 'Afternoon Walk', 'type': 'Walk', 'sport_type': 'Walk', 'date': '2024-09-22'},
    {'name': 'Afternoon Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-21'},
    {'name': 'Morning Gravel Ride', 'type': 'Ride', 'sport_type': 'GravelRide', 'date': '2024-09-21'},
    {'name': 'pasiimti akinių ir siuntinio Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-20'},
    {'name': 'Afternoon Table Tennis', 'type': 'Workout', 'sport_type': 'TableTennis', 'date': '2024-09-20'},
    {'name': 'Morning Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-20'},
    {'name': 'Evening Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-19'},
    {'name': 'Evening Table Tennis', 'type': 'Workout', 'sport_type': 'TableTennis', 'date': '2024-09-18'},
    {'name': 'Afternoon Walk', 'type': 'Walk', 'sport_type': 'Walk', 'date': '2024-09-18'},
    {'name': 'Lunch Table Tennis', 'type': 'Workout', 'sport_type': 'TableTennis', 'date': '2024-09-18'},
    {'name': 'Morning Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-18'},
    {'name': 'Evening Ride', 'type': 'Ride', 'sport_type': 'Ride', 'date': '2024-09-17'},
    {'name': 'Afternoon Table Tennis', 'type': 'Workout', 'sport_type': 'TableTennis', 'date': '2024-09-17'},
    {'name': 'Afternoon Table Tennis', 'type': 'Workout', 'sport_type': 'TableTennis', 'date': '2024-09-17'},
    {'name': 'Evening Run', 'type': 'Run', 'sport_type': 'Run', 'date': '2024-09-10'},
    {'name': '"ant durniaus" - 10k race Run', 'type': 'Run', 'sport_type': 'Run', 'date': '2024-09-08'},
    {'name': 'Afternoon Run', 'type': 'Run', 'sport_type': 'Run', 'date': '2024-09-08'},
    {'name': '"taper my ass" Run', 'type': 'Run', 'sport_type': 'Run', 'date': '2024-09-05'},
    {'name': 'Morning Run', 'type': 'Run', 'sport_type': 'Run', 'date': '2024-09-03'},
]

# Build prompt like the agent does
neuron_desc = "Filter activities where type=Run"
context_summary = f"\n\nAvailable data:\n  neuron_0_2: {len(activities)} activities (compact format)"
context_summary += f"\n    Format: name, type, sport_type, id, distance, date"
context_summary += f"\n    Activities:\n"

for i, act in enumerate(activities):
    context_summary += f"      {i+1}. {act['name']} | type={act['sport_type']} | date={act['date']}\n"

task_type = "\n\n**YOU ARE COUNTING**"
task_type += "\nInstructions:"
task_type += "\n1. Look at EVERY activity listed above"
task_type += "\n2. Check each one's 'type' or 'sport_type' field"
task_type += "\n3. Count only those matching the requested type"
task_type += "\n4. Output: 'COUNT: X activities' where X is the exact number"
task_type += "\n\nExample: If asked 'how many runs', count where sport_type contains 'Run'"

prompt = f"""Task: {neuron_desc}
{context_summary}
{task_type}

Your answer:"""

print("=== PROMPT STATS ===")
print(f"Length: {len(prompt)} chars")
print(f"Words: {len(prompt.split())} words")
print(f"Lines: {len(prompt.split(chr(10)))} lines")
print()

# Count runs in the data
run_count = sum(1 for a in activities if 'Run' in a.get('sport_type', ''))
print(f"=== ACTUAL DATA ===")
print(f"Total activities: {len(activities)}")
print(f"Activities with 'Run' in sport_type: {run_count}")
print()

print("=== RUN ACTIVITIES ===")
for i, act in enumerate(activities, 1):
    if 'Run' in act.get('sport_type', ''):
        print(f"  {i}. {act['name']} | type={act['sport_type']}")

print("\n=== PROMPT (first 1000 chars) ===")
print(prompt[:1000])
print("...")
