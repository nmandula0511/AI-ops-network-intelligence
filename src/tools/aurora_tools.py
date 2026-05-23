"""
tools/aurora_tools.py
======================
Story 3 — Reusable @tool Decorated Functions for relational database queries (Aurora).
"""

from strands import tool
from typing import List, Optional
from datetime import datetime, timedelta

# In-memory mock database of events to simulate real Aurora queries
_MOCK_EVENTS = {}

def get_or_create_mock_events(device_id: str) -> List[dict]:
    if device_id not in _MOCK_EVENTS:
        now = datetime.utcnow()
        # Seed some realistic switch events
        _MOCK_EVENTS[device_id] = [
            {
                "event_id": f"evt-{device_id}-1",
                "timestamp": (now - timedelta(days=2)).isoformat() + "Z",
                "event_type": "WIFI_TO_LTE",
                "duration_on_lte_minutes": 45,
                "cable_modem_status": "OFFLINE"
            },
            {
                "event_id": f"evt-{device_id}-2",
                "timestamp": (now - timedelta(days=2, minutes=45)).isoformat() + "Z",
                "event_type": "LTE_TO_WIFI",
                "duration_on_lte_minutes": 0,
                "cable_modem_status": "ONLINE"
            },
            {
                "event_id": f"evt-{device_id}-3",
                "timestamp": (now - timedelta(hours=3)).isoformat() + "Z",
                "event_type": "WIFI_TO_LTE",
                "duration_on_lte_minutes": 180,
                "cable_modem_status": "ONLINE" # Stuck! Modem is back online, but still on LTE
            }
        ]
    return _MOCK_EVENTS[device_id]


@tool
def query_device_event_history(
    device_id: str,
    days: int = 7
) -> list:
    """
    Queries Aurora database for the historical switch connection events of a device.
    Use this to see patterns of flapping, connection switches (WIFI_TO_LTE, LTE_TO_WIFI),
    and historical durations.

    Args:
        device_id: Invincible WiFi device ID (INV-WIFI-XXXXXXXXXX)
        days: Retrieve history for last N days. Default 7.

    Returns:
        list of event dicts with keys: event_id, timestamp, event_type, duration_on_lte_minutes, cable_modem_status.
    """
    # Attempt to query from local simulator if available, otherwise fallback
    try:
        from src.api.main import simulator
        events = simulator.get_device_event_history(device_id)
        if events:
            return events
    except Exception:
        pass

    return get_or_create_mock_events(device_id)


@tool
def get_devices_by_region(
    region: str
) -> list:
    """
    Queries Aurora database for a list of Invincible WiFi devices active in a specific region.
    Regions supported: NE, SE, MW, SW, W.

    Args:
        region: Enterprise market region code (NE, SE, MW, SW, W)

    Returns:
        list of device dicts containing device details and current statuses.
    """
    try:
        from src.api.main import simulator
        topology = simulator.get_topology()
        devices = [
            d for d in topology.get("devices", [])
            if d.get("location", {}).get("region") == region.upper()
        ]
        if devices:
            return devices
    except Exception:
        pass

    # Mock fallback
    return [
        {
            "device_id": f"INV-WIFI-000000000{i}",
            "mac_address": f"00:11:22:33:44:0{i}",
            "customer_account_id": f"CHR-1000000{i}",
            "event_type": "WIFI_TO_LTE" if i % 2 == 0 else "LTE_TO_WIFI",
            "duration_on_lte_minutes": 120 if i % 2 == 0 else 0,
            "location": {"zip_code": "80111", "state": "CO", "region": region.upper()},
            "signal_strength_db": -68,
            "firmware_version": "3.1.2" if i % 3 == 0 else "3.2.1",
            "cable_modem_status": "ONLINE" if i % 2 == 0 else "ONLINE"
        }
        for i in range(1, 5)
    ]
