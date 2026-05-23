"""
tools/action_tools.py
======================
Story 3 — Reusable @tool Decorated Functions for remediation and outreach actions.
"""

from strands import tool
from typing import Optional

@tool
def generate_customer_recommendation(
    device_id: str,
    root_cause: str,
    lte_duration_minutes: int
) -> dict:
    """
    Generates tailored step-by-step customer troubleshooting instructions based on diagnosed root cause.
    Prioritizes self-service (e.g. modem reboot, cable check) to prevent expensive technician truck rolls.

    Args:
        device_id: Invincible WiFi device ID (INV-WIFI-XXXXXXXXXX)
        root_cause: Diagnosed failure reason (e.g. 'Cable modem offline', 'Firmware bug', 'Cache desync')
        lte_duration_minutes: Minutes the device has been stuck on LTE

    Returns:
        dict containing recommendation summary and step-by-step instructions.
    """
    steps = []
    summary = ""
    
    if "offline" in root_cause.lower() or "modem" in root_cause.lower():
        summary = "Your primary cable connection is offline. Let's restart your hardware to resolve this."
        steps = [
            "Locate your main cable modem (connected to the coax outlet).",
            "Unplug the power cable from the back of the cable modem.",
            "Wait exactly 30 seconds.",
            "Plug the power cable back into the cable modem.",
            "Wait 2-3 minutes for the lights to stabilize and check if the internet switches back to fiber."
        ]
    elif "firmware" in root_cause.lower():
        summary = "An update is required to resolve a connection routing bug on your Invincible WiFi device."
        steps = [
            "We have queued a firmware update (v3.2.1) to be pushed to your router.",
            "This update will be applied automatically within 10 minutes.",
            "Your router will reboot briefly during the update. No manual action is required."
        ]
    elif "cache" in root_cause.lower() or "reboot" in root_cause.lower():
        summary = "Your router needs a connection refresh to clear its routing cache."
        steps = [
            "Locate the reset button on the back of your Invincible WiFi router.",
            "Using a paperclip or pen, press and hold the reset button for 3 seconds (do not hold longer as it might factory reset).",
            "Release the button and wait 1 minute for the router to refresh its connection status."
        ]
    else:
        summary = "We detected a transient connection state. A soft refresh is recommended."
        steps = [
            "Reboot your Invincible WiFi router by unplugging its power cord for 10 seconds.",
            "Plug it back in and allow it to initialize."
        ]

    return {
        "device_id": device_id,
        "recommendation_summary": summary,
        "action_steps": steps,
        "estimated_resolution_time_minutes": len(steps) * 2,
        "requires_truck_roll": False
    }


@tool
def flag_for_truck_roll(
    device_id: str,
    reason: str,
    priority: str = "MEDIUM"
) -> dict:
    """
    Escalates the issue to Field Services and schedules a physical technician visit (truck roll).
    WARNING: Only invoke this when all remote self-service and config troubleshoot options are exhausted.
    Truck rolls cost the company hundreds of dollars.

    Args:
        device_id: Invincible WiFi device ID (INV-WIFI-XXXXXXXXXX)
        reason: Explanation of why self-service failed and why a truck roll is necessary
        priority: Escalation priority: LOW / MEDIUM / HIGH / CRITICAL. Default: MEDIUM.

    Returns:
        dict containing ticket_id, status, and scheduled dispatch window.
    """
    ticket_id = f"TKT-ROLL-{device_id[-4:]}-{lte_duration_hash(device_id)}"
    
    # Notify simulator of truck roll if active
    try:
        from src.api.main import simulator
        simulator.register_truck_roll(device_id, reason)
    except Exception:
        pass

    return {
        "device_id": device_id,
        "escalation_ticket_id": ticket_id,
        "requires_truck_roll": True,
        "reason": reason,
        "priority": priority.upper(),
        "status": "QUEUED_FOR_DISPATCH",
        "dispatch_window": "Tomorrow between 8:00 AM - 12:00 PM"
    }


@tool
def create_outreach_ticket(
    device_id: str,
    channel: str = "EMAIL"
) -> dict:
    """
    Creates an outreach ticket for Enterprise Support to contact the customer proactively.
    Use this for YELLOW severity alerts where remote config checks show healthy links but device stays on LTE.

    Args:
        device_id: Invincible WiFi device ID (INV-WIFI-XXXXXXXXXX)
        channel: Notification delivery channel: EMAIL / SMS / PHONE. Default: EMAIL.

    Returns:
        dict with ticket details.
    """
    ticket_id = f"TKT-OUT-{device_id[-4:]}-{lte_duration_hash(device_id)}"
    return {
        "device_id": device_id,
        "outreach_ticket_id": ticket_id,
        "status": "OPEN",
        "channel": channel.upper(),
        "outreach_message": f"Dear Customer, your Invincible WiFi is running on backup LTE. Please check your cable modem power connections."
    }

def lte_duration_hash(s: str) -> int:
    import hashlib
    return int(hashlib.md5(s.encode()).hexdigest(), 16) % 10000
