#!/usr/bin/env python3
"""
Strava Integration Test with Full LLM

This test validates the complete flow:
1. Ollama LLM connection
2. Strava cookie authentication
3. LLM function calling with Strava tools
4. Actual API calls to Strava

HOW TO GET VALID STRAVA COOKIES:
================================

The tool supports TWO cookie formats - pick whichever is easier!

Format 1 - Raw Cookie String (EASIEST - Just Copy/Paste!):
-----------------------------------------------------------
Simply copy the entire Cookie header from your browser:

  1. Open Chrome and log into strava.com
  2. Press F12 → Network tab
  3. Click any request to strava.com
  4. Find "Request Headers" → "Cookie"
  5. Copy the ENTIRE value after "Cookie: "
  6. Paste directly into .strava_cookies

Example .strava_cookies file:
  _strava4_session=xyz123abc; CloudFront-Policy=abc; other_cookie=value

That's it! No JSON formatting needed.

Format 2 - JSON Array (Structured):
------------------------------------
If you prefer structured format:

  [
    {
      "name": "_strava4_session",
      "value": "YOUR_SESSION_VALUE_HERE",
      "domain": ".strava.com"
    }
  ]

Quick Copy/Paste Commands:
---------------------------

Method 1 (Raw String - Easiest):
  # Just paste the cookie string from browser
  echo "_strava4_session=YOUR_VALUE_HERE" > .strava_cookies

Method 2 (JSON):
  cat > .strava_cookies << 'EOF'
  [
    {
      "name": "_strava4_session",
      "value": "YOUR_VALUE_HERE",
      "domain": ".strava.com"
    }
  ]
  EOF

Getting the Cookie from Browser:
---------------------------------
Chrome/Firefox DevTools:
  1. Open DevTools (F12)
  2. Go to Network tab
  3. Visit strava.com/dashboard
  4. Click any request to strava.com
  5. Look at Request Headers > Cookie
  6. Copy everything after "Cookie: "

OR from Application tab:
  1. Open DevTools (F12)
  2. Go to Application tab
  3. Storage > Cookies > https://www.strava.com
  4. Find "_strava4_session"
  5. Copy the Value field

Note: Session cookies expire after some time (hours/days).
If you get 401 errors, get a fresh cookie from your browser.
"""

import sys
import os
import json
import yaml
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.ollama_client import OllamaClient
from agent.tool_registry import get_registry, Tool


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_strava_cookies():
    """
    Load and validate Strava cookies.
    
    Supports two formats:
    1. JSON array: [{"name": "_strava4_session", "value": "...", "domain": ".strava.com"}]
    2. Raw cookie string: "_strava4_session=xyz123; other_cookie=abc456"
    """
    cookies_path = Path(__file__).parent.parent / ".strava_cookies"
    
    if not cookies_path.exists():
        print("❌ ERROR: .strava_cookies file not found!")
        print(f"   Expected at: {cookies_path}")
        print("\n   Format 1 (JSON):")
        print('   [{"name": "_strava4_session", "value": "YOUR_SESSION", "domain": ".strava.com"}]')
        print("\n   Format 2 (Raw Cookie String):")
        print('   _strava4_session=YOUR_SESSION_VALUE; other_cookie=value')
        return None
    
    try:
        with open(cookies_path, 'r') as f:
            content = f.read().strip()
        
        session_value = None
        cookie_format = None
        
        # Try JSON format first
        try:
            cookies = json.load(open(cookies_path))
            cookie_format = "JSON"
            
            if not isinstance(cookies, list) or len(cookies) == 0:
                print("❌ ERROR: Invalid JSON cookie format - must be a JSON array")
                return None
            
            for cookie in cookies:
                if cookie.get('name') == '_strava4_session':
                    session_value = cookie.get('value')
                    break
        
        except (json.JSONDecodeError, TypeError):
            # Try raw cookie string format
            cookie_format = "Raw String"
            
            # Look for _strava4_session in the string
            for pair in content.split(';'):
                pair = pair.strip()
                if pair.startswith('_strava4_session='):
                    session_value = pair.split('=', 1)[1].strip()
                    break
        
        if not session_value:
            print("❌ ERROR: _strava4_session cookie not found in .strava_cookies")
            print(f"   Detected format: {cookie_format}")
            return None
        
        # Mask cookie for display (show first 8 and last 4 chars)
        if len(session_value) > 12:
            masked = f"{session_value[:8]}...{session_value[-4:]}"
        else:
            masked = session_value[:4] + "..." if len(session_value) > 4 else "***"
        
        print(f"✅ Found Strava session cookie ({cookie_format} format)")
        print(f"   Cookie value: {masked}")
        print(f"   Cookie length: {len(session_value)} characters")
        
        return content  # Return raw content, StravaClient will parse it
    
    except Exception as e:
        print(f"❌ ERROR loading cookies: {e}")
        return None


def print_separator(title=""):
    """Print a visual separator"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'-'*60}\n")


def test_ollama_connection(config):
    """Test connection to Ollama"""
    print_separator("Step 1: Testing Ollama Connection")
    
    try:
        ollama_config = config['ollama']
        base_url = ollama_config['base_url']
        model = ollama_config['model']
        
        print(f"Ollama URL: {base_url}")
        print(f"Model: {model}")
        
        client = OllamaClient(
            base_url=base_url,
            model=model,
            timeout=ollama_config.get('timeout', 60),
            temperature=ollama_config.get('temperature', 0.7)
        )
        
        if client.health_check():
            print(f"✅ Ollama is healthy and model '{model}' is available")
            return client
        else:
            print("❌ Ollama health check failed")
            return None
    
    except Exception as e:
        print(f"❌ ERROR connecting to Ollama: {e}")
        return None


def discover_strava_tools():
    """Discover and register Strava tools"""
    print_separator("Step 2: Discovering Strava Tools")
    
    try:
        registry = get_registry()
        registry.discover_tools("tools")
        
        all_tools = {tool.name: tool for tool in registry.list_tools()}
        print(f"✅ Found {len(all_tools)} tools:")
        
        for name, tool in all_tools.items():
            print(f"   - {name} ({tool.permissions}): {tool.description}")
        
        return registry
    
    except Exception as e:
        print(f"❌ ERROR discovering tools: {e}")
        return None


def test_strava_api_with_llm(client, registry):
    """
    Main integration test: Use LLM to call Strava API
    
    This simulates the real agent flow:
    1. Prepare available tools
    2. Send a prompt to LLM requesting Strava data
    3. LLM decides which tools to call
    4. Execute the tool calls
    5. Show results
    """
    print_separator("Step 3: LLM Function Calling Test")
    
    # Get tools that can fetch activities
    all_tools = registry.list_tools()
    available_tools = [
        Tool(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
            func=tool.func,
            returns=tool.returns,
            permissions=tool.permissions
        )
        for tool in all_tools
    ]
    
    # Prompt for LLM
    prompt = """Please fetch recent Strava activities. 
Start by getting my last day's activities (last 24 hours), and also check the friend feed to see what others are doing.
Use the available tools to get this information."""

    context = """You are a helpful AI assistant that can call Strava API tools.
Your goal is to fetch recent Strava activities and provide information about them.
The user wants to know about their recent activities and what their friends are doing."""

    print("Sending request to LLM...")
    print(f"\nPrompt: {prompt[:100]}...")
    print(f"\nContext: {context[:100]}...")
    
    try:
        # Convert tools to format expected by function_call
        tool_dicts = [tool.to_dict() for tool in available_tools]
        
        # Call LLM with function calling
        result = client.function_call(
            prompt=prompt,
            tools=tool_dicts,
            context=context
        )
        
        reasoning = result.get('reasoning', 'No reasoning provided')
        confidence = result.get('confidence', 0)
        actions = result.get('actions', [])
        
        print(f"\n✅ LLM Response received!")
        print(f"\nReasoning: {reasoning}")
        print(f"Confidence: {confidence}")
        print(f"Actions to execute: {len(actions)}")
        
        if not actions:
            print("\n⚠️  LLM didn't suggest any tool calls")
            return False
        
        # Execute each action
        print_separator("Step 4: Executing Tool Calls")
        
        success_count = 0
        for i, action in enumerate(actions, 1):
            tool_name = action.get('tool')
            parameters = action.get('parameters', {})
            
            print(f"\nAction {i}/{len(actions)}: {tool_name}")
            print(f"Parameters: {json.dumps(parameters, indent=2)}")
            
            # Get the tool
            tool = registry.get(tool_name)
            if not tool:
                print(f"❌ Tool '{tool_name}' not found in registry")
                continue
            
            # Execute the tool
            try:
                print(f"\nExecuting {tool_name}...")
                result = tool.execute(**parameters)
                
                print(f"\n✅ SUCCESS! Got response from {tool_name}")
                
                # Pretty print the result
                if isinstance(result, dict):
                    print(f"\nResult preview:")
                    # Show summary
                    if 'activities' in result:
                        activities = result['activities']
                        print(f"  - Found {len(activities)} activities")
                        for idx, activity in enumerate(activities[:3], 1):
                            name = activity.get('name', 'Unknown')
                            activity_type = activity.get('type', 'Unknown')
                            print(f"    {idx}. {name} ({activity_type})")
                        if len(activities) > 3:
                            print(f"    ... and {len(activities) - 3} more")
                    else:
                        # Show first few keys
                        print(f"  Keys in response: {list(result.keys())[:5]}")
                elif isinstance(result, list):
                    print(f"  - Got list with {len(result)} items")
                    if result:
                        print(f"  - First item preview: {str(result[0])[:100]}...")
                else:
                    print(f"  {str(result)[:200]}...")
                
                success_count += 1
                
            except Exception as e:
                print(f"\n❌ ERROR executing {tool_name}: {e}")
                print(f"   Error type: {type(e).__name__}")
                
                # Check for authentication error
                if "401" in str(e) or "Unauthorized" in str(e):
                    print("\n   🔑 AUTHENTICATION ISSUE DETECTED!")
                    print("   This means your Strava session cookie is invalid or expired.")
                    print("   Please get a fresh cookie from your browser (see docstring at top of file)")
                
                # Import requests to get more details
                import traceback
                print(f"\n   Full traceback:")
                traceback.print_exc()
        
        print_separator("Test Summary")
        print(f"✅ Successfully executed: {success_count}/{len(actions)} actions")
        
        if success_count == 0:
            print("\n⚠️  All tool calls failed!")
            print("   Most likely cause: Invalid or expired Strava session cookie")
            print("   See instructions at the top of this file for how to get a valid cookie")
            return False
        elif success_count < len(actions):
            print("\n⚠️  Some tool calls failed - check errors above")
            return False
        else:
            print("\n🎉 All tool calls succeeded! Integration test PASSED!")
            return True
    
    except Exception as e:
        print(f"\n❌ ERROR during LLM function calling: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the integration test"""
    print_separator("Strava Integration Test - Full LLM Flow")
    
    # Load configuration
    print("Loading configuration...")
    try:
        config = load_config()
        print("✅ Config loaded")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return 1
    
    # Check cookies
    cookies = load_strava_cookies()
    if not cookies:
        print("\n⚠️  Cannot proceed without valid cookies")
        return 1
    
    # Test Ollama
    client = test_ollama_connection(config)
    if not client:
        print("\n⚠️  Cannot proceed without Ollama connection")
        return 1
    
    # Discover tools
    registry = discover_strava_tools()
    if not registry:
        print("\n⚠️  Cannot proceed without tool registry")
        return 1
    
    # Run the main integration test
    success = test_strava_api_with_llm(client, registry)
    
    if success:
        print("\n" + "="*60)
        print("  ✅ INTEGRATION TEST PASSED!")
        print("="*60)
        return 0
    else:
        print("\n" + "="*60)
        print("  ❌ INTEGRATION TEST FAILED")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
