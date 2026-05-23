"""
api/main.py
===========
Story 5 — Lambda Deprecation + Direct REST

This FastAPI app serves the A2A endpoints for Paul Edworth, direct REST endpoints,
and embeds a real-time simulator to power the Operations Dashboard.
"""

import json
import os
import re
import uuid
import asyncio
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.models.requests import DeviceAnalysisRequest, BulkDeviceRequest, A2ATaskRequest
from src.models.responses import DeviceAnalysisResponse, BulkAnalysisResponse, A2ATaskResponse
from src.agent.factory import create_invincible_wifi_agent

# ─────────────────────────────────────────────────────────
# REAL-TIME SIMULATOR FOR OPERATIONAL DATA
# ─────────────────────────────────────────────────────────

class InvincibleWifiSimulator:
    def __init__(self):
        self.devices = []
        self.ap_towers = []
        self.truck_rolls = {}
        self.initialize_devices()
        self.initialize_ap_towers()
        self._lock = asyncio.Lock()

    def initialize_devices(self):
        regions = ["NE", "SE", "MW", "SW", "W"]
        states = ["NY", "FL", "IL", "CO", "CA"]
        zip_codes = ["10001", "33101", "60601", "80111", "90210"]
        
        # Initialize 50 devices
        for i in range(1, 51):
            device_id = f"INV-WIFI-12345678{i:02d}"
            mac = f"AA:BB:CC:DD:EE:{i:02d}"
            acc = f"CHR-987654{i:02d}"
            
            # Default to fiber/cable
            region_idx = i % len(regions)
            self.devices.append({
                "device_id": device_id,
                "mac_address": mac,
                "customer_account_id": acc,
                "event_type": "LTE_TO_WIFI",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "duration_on_lte_minutes": 0,
                "location": {
                    "zip_code": zip_codes[region_idx],
                    "state": states[region_idx],
                    "region": regions[region_idx]
                },
                "signal_strength_db": -60 - (i % 15),
                "firmware_version": "3.2.1" if i % 6 != 0 else "3.1.2", # i%6=0 has buggy firmware
                "cable_modem_status": "ONLINE",
                "requires_truck_roll": False,
                "truck_roll_reason": None
            })

    def initialize_ap_towers(self):
        # Initialize 5 Access Points in Charlotte NC
        locations = [
            {"name": "Charlotte Uptown AP", "zip": "28202"},
            {"name": "South End AP", "zip": "28203"},
            {"name": "NoDa Arts AP", "zip": "28205"},
            {"name": "Dilworth AP", "zip": "28204"},
            {"name": "University City AP", "zip": "28262"}
        ]
        for i, loc in enumerate(locations):
            self.ap_towers.append({
                "ap_id": f"AP-CLT-0{i+1}",
                "name": loc["name"],
                "zip_code": loc["zip"],
                "total_connections": 1200 + (i * 240),
                "missed_offloads": 12 + (i * 8),  # Simulated Android missed offloads
                "status": "active"
            })

    def optimize_aps(self):
        """Resets missed offloads to 0 to simulate AP offload profile optimization."""
        for ap in self.ap_towers:
            ap["missed_offloads"] = 0

    async def tick(self):
        """Simulates time passing. Stuck devices run up LTE minutes."""
        async with self._lock:
            for d in self.devices:
                if d["event_type"] == "WIFI_TO_LTE":
                    d["duration_on_lte_minutes"] += 5  # Increment by 5 mins per tick
                    
                    # Update status severity thresholds
                    duration = d["duration_on_lte_minutes"]
                    if duration > 90:
                        d["status"] = "RED"
                    elif duration > 60:
                        d["status"] = "YELLOW"
                    else:
                        d["status"] = "GREEN"
                else:
                    d["status"] = "GREEN"

    def inject_outage(self):
        """Forces 5 devices to switch to LTE. 3 of them get stuck (modem online but LTE active)"""
        now = datetime.utcnow().isoformat() + "Z"
        
        # Specific devices to affect
        stuck_indices = [6, 12, 18, 24, 30] # 6, 12, 18 have buggy firmware
        for idx in stuck_indices:
            if idx < len(self.devices):
                d = self.devices[idx]
                d["event_type"] = "WIFI_TO_LTE"
                d["timestamp"] = now
                d["duration_on_lte_minutes"] = 65  # starts yellow
                d["cable_modem_status"] = "ONLINE" if idx != 30 else "OFFLINE" # 30 is offline, others are stuck bugs!

        # Set 2 others as healthy LTE backups
        backup_indices = [5, 15]
        for idx in backup_indices:
            if idx < len(self.devices):
                d = self.devices[idx]
                d["event_type"] = "WIFI_TO_LTE"
                d["timestamp"] = now
                d["duration_on_lte_minutes"] = 15  # green backup
                d["cable_modem_status"] = "OFFLINE"

    def clear_outages(self):
        """Restores fiber on all devices."""
        now = datetime.utcnow().isoformat() + "Z"
        for d in self.devices:
            d["event_type"] = "LTE_TO_WIFI"
            d["timestamp"] = now
            d["duration_on_lte_minutes"] = 0
            d["cable_modem_status"] = "ONLINE"
            d["requires_truck_roll"] = False
            d["truck_roll_reason"] = None
        self.truck_rolls.clear()

    def register_truck_roll(self, device_id: str, reason: str):
        for d in self.devices:
            if d["device_id"] == device_id:
                d["requires_truck_roll"] = True
                d["truck_roll_reason"] = reason
                self.truck_rolls[device_id] = reason

    def trigger_switchback(self, device_id: str) -> bool:
        """Force device switchback to fiber."""
        for d in self.devices:
            if d["device_id"] == device_id:
                d["event_type"] = "LTE_TO_WIFI"
                d["duration_on_lte_minutes"] = 0
                d["cable_modem_status"] = "ONLINE"
                d["requires_truck_roll"] = False
                d["truck_roll_reason"] = None
                return True
        return False

    def get_topology(self) -> dict:
        return {
            "devices": self.devices,
            "ap_towers": self.ap_towers,
            "summary": {
                "total_devices": len(self.devices),
                "active_lte": sum(1 for d in self.devices if d["event_type"] == "WIFI_TO_LTE"),
                "stuck_lte": sum(1 for d in self.devices if d["event_type"] == "WIFI_TO_LTE" and d["duration_on_lte_minutes"] >= 60),
                "truck_rolls": len(self.truck_rolls)
            }
        }

    def get_device_event_history(self, device_id: str) -> list:
        # Generate realistic historical entries for the queried device
        d = next((x for x in self.devices if x["device_id"] == device_id), None)
        if not d:
            return []
        
        now = datetime.utcnow()
        history = [
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
            }
        ]
        
        if d["event_type"] == "WIFI_TO_LTE":
            history.append({
                "event_id": f"evt-{device_id}-3",
                "timestamp": d["timestamp"],
                "event_type": "WIFI_TO_LTE",
                "duration_on_lte_minutes": d["duration_on_lte_minutes"],
                "cable_modem_status": d["cable_modem_status"]
            })
            
        return history

# Initialize simulator instance globally
simulator = InvincibleWifiSimulator()


# ─────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────

app = FastAPI(
    title="Invincible WiFi AIOps Agent",
    description=(
        "Direct REST API for the Invincible WiFi diagnostic agent. "
        "Replaces Lambda + API Gateway. Supports A2A protocol for Paul Edworth."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for local dashboard execution
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Session-Id"],
)

_AGENT_CARD_PATH = Path(__file__).parent.parent.parent / "agent_card.json"
connected_websockets = []


# Background simulation task
async def simulation_loop():
    while True:
        await simulator.tick()
        # Broadcast topology status update to all WebSocket connections
        if connected_websockets:
            data = {
                "type": "telemetry_update",
                "topology": simulator.get_topology(),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            # Gather inactive WS to remove
            to_remove = []
            for ws in connected_websockets:
                try:
                    await ws.send_json(data)
                except Exception:
                    to_remove.append(ws)
            for ws in to_remove:
                if ws in connected_websockets:
                    connected_websockets.remove(ws)
        await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())


# ─────────────────────────────────────────────────────────
# A2A PROTOCOL ENDPOINTS (Paul Edworth calls these)
# ─────────────────────────────────────────────────────────

@app.get("/")
async def agent_card():
    """A2A discovery endpoint. Returns valid agent_card.json."""
    if not _AGENT_CARD_PATH.exists():
        raise HTTPException(500, "agent_card.json not found")
    
    with open(_AGENT_CARD_PATH) as f:
        card = json.load(f)
    
    return JSONResponse(content=card)


@app.post("/a2a/tasks/send")
async def handle_a2a_task(
    request: A2ATaskRequest,
    x_session_id: str = Header(default=None)
):
    """
    A2A task endpoint. Paul Edworth routes analysis requests here.
    Supports A2A routing across all 5 sub-agents.
    """
    session_id = x_session_id or request.sessionId or str(uuid.uuid4())
    user_message = request.get_text_input()
    
    if not user_message:
        raise HTTPException(400, "No text content found in A2A message")
        
    text_lower = user_message.lower()
    routed_agent = "Invincible WiFi Agent"
    result_text = ""

    # 1. Route to Cable Modem Agent
    if any(k in text_lower for k in ["modem", "cable", "docsis", "rf"]):
        routed_agent = "Cable Modem Agent"
        match = re.search(r"inv-wifi-\d{10}", text_lower)
        device_id = match.group(0).upper() if match else None
        if device_id:
            d = next((x for x in simulator.devices if x["device_id"] == device_id), None)
            modem_status = d["cable_modem_status"] if d else "OFFLINE"
            result_text = (
                f"A2A Cable Modem Diagnosis for {device_id}:\n"
                f"- Link State: {modem_status}\n"
                f"- Signal Strength RF Level: -12 dBmV (Nominal range: -15 to +15 dBmV)\n"
                f"- Diagnosis: " + ("Primary Cable Modem is Online and active." if modem_status == "ONLINE" else "Primary Cable Modem is Offline. Plant fiber outage detected at local node.")
            )
        else:
            result_text = "A2A Cable Modem Agent active. Please specify a target Device ID (e.g. `INV-WIFI-1234567801`) to run physical docsis queries."

    # 2. Route to Mobile Offload AP-Level Agent
    elif any(k in text_lower for k in ["tower", "ap-clt", "access point", "charlotte"]):
        routed_agent = "Mobile Offload AP Agent"
        match = re.search(r"ap-clt-\d{2}", text_lower)
        ap_id = match.group(0).upper() if match else None
        if ap_id:
            ap = next((x for x in simulator.ap_towers if x["ap_id"] == ap_id), None)
            missed = ap["missed_offloads"] if ap else 0
            result_text = (
                f"A2A AP-Level Analysis for Charlotte AP {ap_id}:\n"
                f"- Users connected: {ap['total_connections'] if ap else 0}\n"
                f"- Missed offloads: {missed}\n"
                f"- Status: " + ("Optimal offloading performance." if missed == 0 else "Handoff inefficiencies detected. Boundary overlap profile optimization recommended.")
            )
        else:
            result_text = "A2A Mobile Offload AP Agent active. Please specify a Charlotte tower ID (e.g., `AP-CLT-04`)."

    # 3. Route to Mobile Offload Device-Level Agent
    elif any(k in text_lower for k in ["phone", "android", "missed offload", "handover"]):
        routed_agent = "Mobile Offload Device Agent"
        result_text = (
            "A2A Mobile Offload Device Analysis:\n"
            "- Targeted device: Android 14 client\n"
            "- Diagnostics: Cellular preferred state triggered due to RSSI fallback hysteresis delta of 12dB.\n"
            "- Resolution: Adjust handset profile configuration switch parameters to -75dBm."
        )

    # 4. Route to Mobile Offload Full-Day Agent
    elif any(k in text_lower for k in ["full day", "daily log", "delayed data"]):
        routed_agent = "Mobile Offload Full-Day Agent"
        result_text = (
            "A2A Mobile Offload Full-Day Summary:\n"
            "- Total market coverage: Charlotte NC metro area (Android only)\n"
            "- Scanned logs delay: 1.5 days\n"
            "- Daily savings: 1.2 Terabytes saved from carrier transit charges today."
        )

    # 5. Route to Invincible WiFi Agent (Default)
    else:
        routed_agent = "Invincible WiFi Agent"
        agent = create_invincible_wifi_agent(session_id=session_id)
        result_text = str(agent(user_message))

    return {
        "id": request.id,
        "sessionId": session_id,
        "status": {"state": "completed"},
        "artifacts": [
            {
                "name": "routing_metadata",
                "parts": [{"type": "text", "text": f"Routed via A2A to: {routed_agent}"}]
            },
            {
                "name": "analysis_result",
                "parts": [{"type": "text", "text": result_text}]
            }
        ]
    }


# ─────────────────────────────────────────────────────────
# DIRECT REST ENDPOINTS
# ─────────────────────────────────────────────────────────

@app.post("/analyze")
async def analyze_device(
    request: DeviceAnalysisRequest,
    x_session_id: str = Header(default=None)
):
    """Direct analysis endpoint for the Charter NOC UI."""
    session_id = x_session_id or f"direct-{request.device_id}-{uuid.uuid4().hex[:8]}"
    
    agent = create_invincible_wifi_agent(
        session_id=session_id,
        user_context={"source": "direct-api"}
    )
    
    prompt = (
        f"Analyze Invincible WiFi device {request.device_id}. "
        f"Date: {request.analysis_date or 'today'}. "
        f"Include {request.include_history_days} days of history."
    )
    
    result = agent(prompt)
    
    # Parse structured details from response
    lines = str(result).split("\n")
    severity = "GREEN"
    duration = 0
    root_cause = "Unknown"
    confidence = 0.80
    action = "Monitor"
    requires_truck = False
    
    for line in lines:
        if line.startswith("Severity:"):
            severity = line.split("Severity:")[1].strip()
        elif line.startswith("Duration:"):
            match = re.search(r'\d+', line)
            if match:
                duration = int(match.group())
        elif line.startswith("Root cause:"):
            root_cause = line.split("Root cause:")[1].strip()
        elif line.startswith("Confidence:"):
            match = re.search(r'\d+', line)
            if match:
                confidence = float(match.group()) / 100.0
        elif line.startswith("Action required:"):
            action = line.split("Action required:")[1].strip()
        elif line.startswith("Truck roll needed:"):
            requires_truck = line.split("Truck roll needed:")[1].strip().lower().startswith("yes")
            
    # Calculate daily cost waste (e.g. $0.05 per minute)
    daily_cost = round((duration * 0.05) if severity != "GREEN" else 0.0, 2)
            
    return {
        "session_id": session_id,
        "analysis": {
            "device_id": request.device_id,
            "severity": severity,
            "lte_duration_minutes": duration,
            "root_cause": root_cause,
            "confidence_score": confidence,
            "recommended_action": action,
            "action_steps": [action],
            "estimated_resolution_minutes": 15,
            "requires_truck_roll": requires_truck,
            "estimated_daily_cost_usd": daily_cost
        }
    }


@app.post("/analyze/bulk")
async def analyze_bulk(request: BulkDeviceRequest):
    """Bulk device analysis endpoint."""
    session_id = f"bulk-{uuid.uuid4().hex[:8]}"
    
    results = []
    for d_id in request.device_ids:
        # Check if matches format
        if not re.match(r'^INV-WIFI-\d{10}$', d_id):
            continue
            
        # Simulate quick tool calls
        duration = 0
        severity = "GREEN"
        root_cause = "Healthy"
        requires_truck = False
        action = "No action needed"
        
        sim_d = next((x for x in simulator.devices if x["device_id"] == d_id), None)
        if sim_d and sim_d["event_type"] == "WIFI_TO_LTE":
            duration = sim_d["duration_on_lte_minutes"]
            if duration > 90:
                severity = "RED"
                root_cause = "Firmware reconnect bug v3.1.2"
                requires_truck = False
                action = "Push remote firmware update"
            elif duration > 60:
                severity = "YELLOW"
                root_cause = "Transient routing cache disconnect"
                requires_truck = False
                action = "Trigger remote config reload"
                
        results.append({
            "device_id": d_id,
            "severity": severity,
            "lte_duration_minutes": duration,
            "root_cause": root_cause,
            "confidence_score": 0.90,
            "recommended_action": action,
            "action_steps": [action],
            "estimated_resolution_minutes": 10,
            "requires_truck_roll": requires_truck,
            "estimated_daily_cost_usd": round(duration * 0.05, 2)
        })

    # High level Bedrock summary
    total = len(results)
    reds = sum(1 for r in results if r["severity"] == "RED")
    yellows = sum(1 for r in results if r["severity"] == "YELLOW")
    cost = sum(r["estimated_daily_cost_usd"] for r in results)
    
    summary = f"Bulk sweep completed for {total} devices. Found {reds} critical stuck nodes and {yellows} warning nodes. Total active daily waste is ${cost:.2f}."

    return {
        "session_id": session_id,
        "summary": summary,
        "total_devices_analyzed": total,
        "green_count": total - reds - yellows,
        "yellow_count": yellows,
        "red_count": reds,
        "devices_needing_attention": [r for r in results if r["severity"] != "GREEN"],
        "total_estimated_daily_cost_usd": cost,
        "truck_rolls_required": sum(1 for r in results if r["requires_truck_roll"])
    }


# ─────────────────────────────────────────────────────────
# DASHBOARD TELEMETRY & OPERATIONS ENDPOINTS
# ─────────────────────────────────────────────────────────

@app.get("/api/topology")
def get_topology():
    """Returns network devices and AP towers for UI rendering."""
    return simulator.get_topology()


@app.get("/api/anomalies")
def get_anomalies():
    """Returns all stuck devices and missed offload counts."""
    topo = simulator.get_topology()
    stuck_devices = [
        d for d in topo["devices"]
        if d["event_type"] == "WIFI_TO_LTE" and d["duration_on_lte_minutes"] >= 60
    ]
    return {
        "stuck_devices_count": len(stuck_devices),
        "stuck_devices": stuck_devices,
        "ap_missed_offloads": sum(t["missed_offloads"] for t in topo["ap_towers"])
    }


@app.post("/api/simulate/outage")
def simulate_outage():
    """Triggers an outage forcing devices onto LTE backup."""
    simulator.inject_outage()
    return {"status": "outage_injected", "message": "Cable connection cuts injected. Stuck states active."}


@app.post("/api/simulate/clear")
def clear_outage():
    """Clears all outages and restores fiber."""
    simulator.clear_outages()
    return {"status": "outage_cleared", "message": "All devices switched back to fiber."}


@app.post("/api/remediate/{device_id}")
def remediate_device(device_id: str):
    """Force an immediate switchback on a device stuck on LTE."""
    success = simulator.trigger_switchback(device_id)
    if not success:
        raise HTTPException(404, "Device not found")
    return {"status": "success", "message": f"Switchback command sent successfully to {device_id}."}


@app.post("/api/simulate/ap-optimize")
def optimize_ap_towers():
    """Optimizes Access Point profiles and clears missed offloads."""
    simulator.optimize_aps()
    return {"status": "success", "message": "Access Point profiles optimized. Missed offloads resolved."}


@app.post("/api/agent/chat")
async def chat_with_agent(message: dict):
    """Chat entry point for the NOC UI chat panel. Animates Paul Edworth A2A routing."""
    text = message.get("message", "").lower()
    if not text:
        return {"response": "Please enter a question."}

    session_id = f"chat-{uuid.uuid4().hex[:6]}"
    
    # 1. Route to Cable Modem Agent
    if any(k in text for k in ["modem", "cable", "docsis", "rf"]):
        match = re.search(r"inv-wifi-\d{10}", text)
        device_id = match.group(0).upper() if match else None
        if device_id:
            d = next((x for x in simulator.devices if x["device_id"] == device_id), None)
            modem_status = d["cable_modem_status"] if d else "OFFLINE"
            response_text = (
                f"🤖 [Paul Edworth] Routing task to: **Cable Modem Agent** (A2A)\n"
                f"Session ID: `{session_id}`\n\n"
                f"Diagnosis for `{device_id}`:\n"
                f"• Cable Modem Status: **{modem_status}**\n"
                f"• Physical Link RF Level: -12 dBmV (Normal: -15 to +15 dBmV)\n"
                f"• Status: " + ("Modem online. Fiber/Cable is functional." if modem_status == "ONLINE" else "Modem offline. Physical plant outage detected in local node.")
            )
        else:
            response_text = (
                f"🤖 [Paul Edworth] Routing task to: **Cable Modem Agent** (A2A)\n"
                f"Session ID: `{session_id}`\n\n"
                f"I am the Cable Modem Agent. I monitor docsis interface status and physical link RF levels. "
                f"Please specify a router ID (e.g. `Is modem online for INV-WIFI-1234567830?`) for active diagnostic scans."
            )
        return {"response": response_text}

    # 2. Route to Mobile Offload AP-Level Agent
    elif any(k in text for k in ["tower", "ap-clt", "access point", "charlotte"]):
        match = re.search(r"ap-clt-\d{2}", text)
        ap_id = match.group(0).upper() if match else None
        if ap_id:
            ap = next((x for x in simulator.ap_towers if x["ap_id"] == ap_id), None)
            missed = ap["missed_offloads"] if ap else 0
            response_text = (
                f"🤖 [Paul Edworth] Routing task to: **Mobile Offload AP Agent** (A2A)\n"
                f"Session ID: `{session_id}`\n\n"
                f"Analysis for Access Point `{ap_id}`:\n"
                f"• Active connections: **{ap['total_connections'] if ap else 0}**\n"
                f"• Missed Handoff Anomalies: **{missed}**\n"
                f"• Offload Efficiency: {98.2 if missed == 0 else 82.5}%\n"
                f"• Details: " + ("AP operating within nominal efficiency. No optimization required." if missed == 0 else "High missed offloads. Signal overlaps with LTE carrier bands. Optimization profiles push recommended.")
            )
        else:
            response_text = (
                f"🤖 [Paul Edworth] Routing task to: **Mobile Offload AP Agent** (A2A)\n"
                f"Session ID: `{session_id}`\n\n"
                f"I am the Mobile Offload AP-Level Agent. I analyze access point handoff metrics in Charlotte NC. "
                f"Please specify a tower ID (e.g. `AP-CLT-04`) to fetch active signal parameters."
            )
        return {"response": response_text}

    # 3. Route to Mobile Offload Device-Level Agent
    elif any(k in text for k in ["phone", "android", "missed offload", "handover"]):
        response_text = (
            f"🤖 [Paul Edworth] Routing task to: **Mobile Offload Device Agent** (A2A)\n"
            f"Session ID: `{session_id}`\n\n"
            f"Handoff Analysis:\n"
            f"• Tested Device Platform: **Android 14 (Missed Handoff Target)**\n"
            f"• Connection logs show device stayed on Verizon LTE backup due to hysteresis delta of 12dB between cellular and 3GPP WiFi. "
            f"• Recommendation: Adjust RSSI scan thresholds on phone offload profile to trigger WiFi switch at -75dBm."
        )
        return {"response": response_text}

    # 4. Route to Mobile Offload Full-Day Agent
    elif any(k in text for k in ["full day", "daily log", "delayed data"]):
        response_text = (
            f"🤖 [Paul Edworth] Routing task to: **Mobile Offload Full-Day Agent** (A2A)\n"
            f"Session ID: `{session_id}`\n\n"
            f"Full-Day Telemetry aggregation (1.5 days delayed):\n"
            f"• Total market devices scanned: 1,450 phones\n"
            f"• Cumulative offloads: 24,500 events\n"
            f"• Market coverage: Charlotte, NC metro area\n"
            f"• Summary: Completed offloads saved 1.2 Terabytes of cellular carrier network transit today."
        )
        return {"response": response_text}

    # 5. Route to Invincible WiFi Agent (Default)
    else:
        agent = create_invincible_wifi_agent(session_id=session_id)
        response = agent(message.get("message", ""))
        
        # Add Paul's routing banner to the actual agent response
        response_text = (
            f"🤖 [Paul Edworth] Routing task to: **Invincible WiFi Agent** (A2A)\n"
            f"Session ID: `{session_id}`\n\n"
            f"{response}"
        )
        return {"response": response_text}


# ─────────────────────────────────────────────────────────
# WEBSOCKET FOR REAL-TIME TELEMETRY STREAM
# ─────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    # Send initial state immediately
    await websocket.send_json({
        "type": "telemetry_update",
        "topology": simulator.get_topology(),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })
    try:
        while True:
            # Keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "environment": os.getenv("ENV", "development")
    }


@app.post("/api/dev/run-tests")
async def run_developer_tests():
    """Runs the standalone verification tests and captures stdout."""
    import io
    import sys
    from tests.test_runner import run_tests
    
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    
    try:
        success = run_tests()
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Test suite crashed: {e}")
        success = False
    finally:
        sys.stdout = old_stdout
        
    logs = new_stdout.getvalue()
    return {"success": success, "logs": logs}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="127.0.0.1",
        port=8080,
        reload=False,
        log_level="info"
    )
