"""
tests/test_runner.py
====================
A standalone Python script to verify the AIOps platform features.
Requires no external testing frameworks. Runs out of the box!
"""

import sys
import os
from pathlib import Path

# Add project root to python path
sys.path.append(str(Path(__file__).parent.parent))

from src.models.requests import DeviceAnalysisRequest
from src.agent.factory import create_invincible_wifi_agent
from strands import tool

def run_tests():
    print("[TEST] STARTING STANDALONE AIOPS VERIFICATION TESTS\n")
    
    # Test 1: Pydantic Validation Checks
    print("-> Test 1: Verifying Pydantic Request validation...")
    try:
        req = DeviceAnalysisRequest(device_id="INV-WIFI-1234567890", include_history_days=7)
        print("   [OK] Valid device ID passed successfully.")
    except Exception as e:
        print(f"   [FAIL] Valid device ID failed unexpectedly: {e}")
        return False
        
    try:
        DeviceAnalysisRequest(device_id="INVALID-FORMAT-123", include_history_days=7)
        print("   [FAIL] Invalid device ID format was accepted (should have failed)!")
        return False
    except Exception:
        print("   [OK] Invalid device ID format correctly raised validation error.")

    # Test 2: Reusable Tools Schema Integrity
    print("\n-> Test 2: Verifying Reusable Tool definitions and schemas...")
    from src.tools.device_tools import get_device_lte_duration
    if not getattr(get_device_lte_duration, "is_tool", False):
        print("   [FAIL] Tool decorator not correctly registered.")
        return False
    schema = getattr(get_device_lte_duration, "tool_schema", {})
    if schema.get("id") != "get_device_lte_duration":
        print(f"   [FAIL] Tool schema name mismatch. Got: {schema.get('id')}")
        return False
    print("   [OK] Tool decorators and schemas verified successfully.")

    # Test 3: Factory Pattern User Isolation
    print("\n-> Test 3: Verifying Factory Pattern user isolation...")
    agent1 = create_invincible_wifi_agent(session_id="user1-session")
    agent2 = create_invincible_wifi_agent(session_id="user2-session")
    
    if agent1 is agent2:
        print("   [FAIL] Factory returned identical agent instances (context bleed danger)!")
        return False
        
    if agent1.session_id != "user1-session" or agent2.session_id != "user2-session":
        print("   [FAIL] Agent session IDs not isolated correctly.")
        return False
    print("   [OK] Agent Factory isolated user contexts correctly.")

    print("\n[SUCCESS] ALL LOCAL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
