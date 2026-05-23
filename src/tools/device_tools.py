"""
tools/device_tools.py
=====================
Story 3 — Reusable @tool Decorated Functions

These @tool functions can be called by:
  - The Invincible WiFi agent
  - Paul Edworth (master orchestrator) via MCP server
  - Any other agent that needs device data
  - Future agents not yet built

BEFORE (wrong way — utility function):
  def _get_device_data(device_id):  # private, not reusable
      ...

AFTER (correct way — @tool decorated):
  @tool
  def get_device_lte_duration(device_id: str) -> dict:  # any agent can use this
      ...

AI IDE NOTE:
  - Each @tool MUST have a complete docstring — the LLM reads this to decide
    when to call the tool. Bad docstring = tool never gets called.
  - Return type must be JSON-serializable (dict, list, str, int, float, bool)
  - Never raise exceptions that crash the agent — return error dicts instead
  - Database connections come from src/utils/db.py (not yet written)
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
    # TODO: Replace with real Aurora query via src/utils/db.py
    # Query: SELECT device_id, TIMESTAMPDIFF(MINUTE, wifi_to_lte_ts, NOW()) as lte_minutes,
    #                cable_modem_online, wifi_to_lte_ts, lte_to_wifi_ts
    #        FROM device_events WHERE device_id = :device_id
    #        AND DATE(wifi_to_lte_ts) = :ref_date
    #        AND lte_to_wifi_ts IS NULL
    #        ORDER BY wifi_to_lte_ts DESC LIMIT 1
    
    target_date = reference_date or str(date.today())
    
    # Placeholder — replace with real DB call
    return {
        "device_id": device_id,
        "lte_duration_minutes": 0,
        "severity": "GREEN",
        "wifi_to_lte_timestamp": None,
        "cable_modem_online": True,
        "lte_to_wifi_timestamp": None,
        "reference_date": target_date,
        "_note": "TODO: implement real Aurora query"
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
    # TODO: Replace with real DynamoDB lookup or Enterprise's network API call
    return {
        "device_id": device_id,
        "modem_online": True,
        "modem_last_seen_online": datetime.utcnow().isoformat(),
        "modem_offline_duration_minutes": 0,
        "modem_model": "Unknown",
        "likely_cause": None,
        "_note": "TODO: implement real DynamoDB/network API call"
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
    # TODO: Replace with real DynamoDB or device management API call
    return {
        "device_id": device_id,
        "current_firmware": "unknown",
        "latest_firmware": "3.2.1",
        "update_available": False,
        "update_critical": False,
        "known_bug_present": False,
        "bug_description": None,
        "_note": "TODO: implement real firmware check"
    }
