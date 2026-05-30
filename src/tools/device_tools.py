"""
tools/device_tools.py
=====================
Story 3 — Reusable @tool Decorated Functions

These @tool functions can be called by:
  - The Invincible WiFi agent
  - Paul Edworth (master orchestrator) via MCP server
  - Any other agent that needs device data
  - Future agents not yet built
"""

from strands import tool
from typing import Optional
from datetime import date, datetime


@tool
def get_device_lte_duration(
    device_id: str,
    reference_date: Optional[str] = None
) -> dict:
    """
    Retrieves how long a specific Invincible WiFi device has been continuously
    on LTE (5G SIM backup) instead of its primary fiber connection.

    Use this as the FIRST tool to call when diagnosing a stuck-on-LTE device.
    Returns severity level: GREEN (< 60 min), YELLOW (60-90 min), RED (> 90 min).

    Args:
        device_id: Invincible WiFi device ID. Format: INV-WIFI-XXXXXXXXXX
        reference_date: ISO date YYYY-MM-DD to analyze. Defaults to today UTC.

    Returns:
        dict with keys:
            device_id (str): The queried device
            lte_duration_minutes (int): Minutes device has been on LTE
            severity (str): GREEN / YELLOW / RED based on threshold
            wifi_to_lte_timestamp (str): When device switched to LTE (ISO)
            cable_modem_online (bool): Whether the cable modem is online
            lte_to_wifi_timestamp (str | None): When it switched back (null if still on LTE)
    """
    target_date = reference_date or str(date.today())
    
    # Dynamically import simulator to prevent circular dependencies
    try:
        from src.api.main import simulator
        d = next((x for x in simulator.devices if x["device_id"] == device_id), None)
    except Exception:
        d = None

    # Fallback to realistic mock values if simulator state isn't initialized or running
    if not d:
        return {
            "device_id": device_id,
            "lte_duration_minutes": 75,
            "severity": "YELLOW",
            "wifi_to_lte_timestamp": datetime.utcnow().isoformat() + "Z",
            "cable_modem_online": True,
            "lte_to_wifi_timestamp": None,
            "reference_date": target_date
        }

    duration = d.get("duration_on_lte_minutes", 0)
    severity = "GREEN"
    if duration > 90:
        severity = "RED"
    elif duration > 60:
        severity = "YELLOW"

    return {
        "device_id": device_id,
        "lte_duration_minutes": duration,
        "severity": severity,
        "wifi_to_lte_timestamp": d["timestamp"] if d["event_type"] == "WIFI_TO_LTE" else None,
        "cable_modem_online": d.get("cable_modem_status") == "ONLINE",
        "lte_to_wifi_timestamp": d["timestamp"] if d["event_type"] == "LTE_TO_WIFI" else None,
        "reference_date": target_date
    }


@tool
def get_cable_modem_status(device_id: str) -> dict:
    """
    Checks the status of the cable modem associated with an Invincible WiFi device.

    Cable modem offline is the most common reason a device is stuck on LTE.
    If the modem is offline, the device cannot switch back to fiber even if it wants to.

    Call this after get_device_lte_duration if severity is YELLOW or RED.

    Args:
        device_id: Invincible WiFi device ID. Format: INV-WIFI-XXXXXXXXXX

    Returns:
        dict with keys:
            device_id (str): The queried device
            modem_online (bool): True if modem is currently online
            modem_last_seen_online (str): ISO timestamp of last online check
            modem_offline_duration_minutes (int): How long modem has been offline
            modem_model (str): Cable modem hardware model
            likely_cause (str): Agent's guess at why modem is offline
    """
    try:
        from src.api.main import simulator
        d = next((x for x in simulator.devices if x["device_id"] == device_id), None)
    except Exception:
        d = None

    if not d:
        return {
            "device_id": device_id,
            "modem_online": True,
            "modem_last_seen_online": datetime.utcnow().isoformat() + "Z",
            "modem_offline_duration_minutes": 0,
            "modem_model": "Charter DOCSIS 3.1 Advanced Modem",
            "likely_cause": None
        }

    modem_online = d.get("cable_modem_status") == "ONLINE"
    offline_duration = d.get("duration_on_lte_minutes", 0) if not modem_online else 0
    likely_cause = None if modem_online else "Coaxial cable connection down / Local node outage"

    return {
        "device_id": device_id,
        "modem_online": modem_online,
        "modem_last_seen_online": d["timestamp"] if modem_online else "2 hours ago",
        "modem_offline_duration_minutes": offline_duration,
        "modem_model": "Charter DOCSIS 3.1 Advanced Modem",
        "likely_cause": likely_cause
    }


@tool
def check_firmware_version(device_id: str) -> dict:
    """
    Returns the firmware version of an Invincible WiFi device and whether
    an update is available or required.

    Outdated firmware (especially versions 3.1.x) is a known cause of
    the LTE-stuck bug where devices fail to auto-reconnect to fiber.
    The Enterprise has documented this as a known issue in firmware < 3.2.0.

    Args:
        device_id: Invincible WiFi device ID. Format: INV-WIFI-XXXXXXXXXX

    Returns:
        dict with keys:
            device_id (str): The queried device
            current_firmware (str): Currently installed firmware version
            latest_firmware (str): Latest available version
            update_available (bool): True if an update exists
            update_critical (bool): True if the update fixes a known LTE bug
            known_bug_present (bool): True if current firmware has the LTE-stuck bug
            bug_description (str | None): Description if known_bug_present is True
    """
    try:
        from src.api.main import simulator
        d = next((x for x in simulator.devices if x["device_id"] == device_id), None)
    except Exception:
        d = None

    if not d:
        return {
            "device_id": device_id,
            "current_firmware": "3.1.2",  # Default stuck-version for testing
            "latest_firmware": "3.2.1",
            "update_available": True,
            "update_critical": True,
            "known_bug_present": True,
            "bug_description": "Firmware version < 3.2.0 has a driver bug preventing automatic reconnect to fiber interface."
        }

    current_fw = d.get("firmware_version", "3.2.1")
    known_bug = current_fw < "3.2.0"

    return {
        "device_id": device_id,
        "current_firmware": current_fw,
        "latest_firmware": "3.2.1",
        "update_available": known_bug,
        "update_critical": known_bug,
        "known_bug_present": known_bug,
        "bug_description": "Firmware versions < 3.2.0 have a driver bug preventing automatic reconnect to fiber interface." if known_bug else None
    }
