"""
FastAPI Backend
---------------
Main entry point for the AIOps API.
Connects all components into one unified interface.

Endpoints:
- /api/topology     → network graph data
- /api/anomalies    → current anomalies
- /api/simulate     → trigger fault scenarios
- /api/agent/rca    → invoke AI agent
- /api/agent/chat   → NOC assistant chat
- /api/incidents    → incident history
- /ws               → WebSocket for live updates
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Import our components
from simulator.network_simulator import NetworkSimulator
from simulator.fault_scenerios import list_scenarios, get_scenario
from graph.graph_queries import NetworkGraphQueries
from ml.ml_pipeline import analyze_batch
from agents.orchestrator import AIOpsOrchestrator

# Initialize FastAPI
app = FastAPI(
    title="AIOps Network Intelligence API",
    description="AI-powered network operations platform",
    version="1.0.0"
)

# Allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
print("🚀 Initializing AIOps Platform...")
simulator = NetworkSimulator(num_devices=50)
graph = NetworkGraphQueries()
orchestrator = AIOpsOrchestrator()
incidents_store = []
connected_websockets = []
print("✅ Platform ready!")


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "running",
        "platform": "AIOps Network Intelligence",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "components": {
            "simulator": "running",
            "graph_db": "connected",
            "ml_models": "loaded",
            "ai_agents": "ready"
        }
    }


# ─────────────────────────────────────────
# TOPOLOGY ENDPOINTS
# ─────────────────────────────────────────

@app.get("/api/topology")
def get_topology():
    """Returns full network topology for visualization."""
    topology = simulator.get_topology()
    return {
        "devices": topology["devices"],
        "links": topology["links"],
        "summary": topology["summary"]
    }


@app.get("/api/topology/device/{device_id}")
def get_device(device_id: str):
    """Returns a specific device details."""
    devices = simulator.get_topology()["devices"]
    device = next((d for d in devices if d["id"] == device_id), None)
    if not device:
        return {"error": "Device not found"}
    return device


@app.get("/api/topology/blast-radius/{device_id}")
def get_blast_radius(device_id: str):
    """Returns blast radius if device fails."""
    try:
        blast = graph.get_blast_radius(device_id)
        return blast
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/topology/critical-devices")
def get_critical_devices():
    """Returns most critical devices in network."""
    try:
        critical = graph.get_critical_devices(top_n=10)
        return {"critical_devices": critical}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────
# ANOMALY ENDPOINTS
# ─────────────────────────────────────────

@app.get("/api/anomalies")
def get_anomalies():
    """Returns current anomalies in the network."""
    telemetry = simulator.generate_batch_telemetry()
    anomalies = analyze_batch(telemetry)
    return {
        "total_devices": len(telemetry),
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ─────────────────────────────────────────
# SIMULATION ENDPOINTS
# ─────────────────────────────────────────

@app.get("/api/scenarios")
def get_scenarios():
    """Returns available fault scenarios."""
    return {"scenarios": list_scenarios()}


@app.post("/api/simulate/{scenario_id}")
async def simulate_fault(scenario_id: str):
    """Triggers a fault scenario."""
    scenario = get_scenario(scenario_id)
    if not scenario:
        return {"error": "Scenario not found"}

    num_devices = scenario.get("num_devices", 3)
    simulator.inject_fault(num_devices=num_devices)

    # Notify WebSocket clients
    message = {
        "type": "fault_injected",
        "scenario": scenario,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await broadcast_websocket(message)

    return {
        "status": "fault_injected",
        "scenario": scenario,
        "message": f"Fault scenario '{scenario['name']}' activated"
    }


@app.post("/api/simulate/clear")
async def clear_faults():
    """Clears all faults."""
    simulator.clear_faults()
    await broadcast_websocket({
        "type": "faults_cleared",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    return {"status": "faults_cleared"}


# ─────────────────────────────────────────
# AI AGENT ENDPOINTS
# ─────────────────────────────────────────

@app.post("/api/agent/rca")
async def run_rca():
    """
    Runs full multi-agent RCA on current network state.
    This is the main demo endpoint.
    """
    telemetry = simulator.generate_batch_telemetry()
    incidents = orchestrator.process_incident(telemetry)

    # Store incidents
    incidents_store.extend(incidents)

    # Notify WebSocket clients
    await broadcast_websocket({
        "type": "rca_complete",
        "incidents_count": len(incidents),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {
        "status": "complete",
        "incidents_processed": len(incidents),
        "incidents": [
            {
                "device_id": i["diagnosis"]["device_id"],
                "fault_type": i["diagnosis"]["fault_type"],
                "blast_radius": i["diagnosis"]["blast_radius"]["total_impact"],
                "risk_level": i["anomaly"]["outage"]["risk_level"],
                "report": i["report"],
                "remediation_status": i["remediation"]["status"]
            }
            for i in incidents
        ]
    }


@app.post("/api/agent/chat")
async def chat_with_agent(message: dict):
    """
    Chat with the NOC AI assistant.
    Powers the chat panel in the React dashboard.
    """
    question = message.get("message", "")
    if not question:
        return {"error": "No message provided"}

    response = orchestrator.chat(question)
    return {
        "question": question,
        "response": response,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ─────────────────────────────────────────
# INCIDENTS ENDPOINTS
# ─────────────────────────────────────────

@app.get("/api/incidents")
def get_incidents():
    """Returns incident history."""
    return {
        "total": len(incidents_store),
        "incidents": [
            {
                "device_id": i["diagnosis"]["device_id"],
                "fault_type": i["diagnosis"]["fault_type"],
                "timestamp": i["diagnosis"]["timestamp"],
                "report": i["report"]
            }
            for i in incidents_store[-10:]
        ]
    }


# ─────────────────────────────────────────
# WEBSOCKET
# ─────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket for live updates to the React dashboard.
    Sends telemetry updates every 3 seconds.
    """
    await websocket.accept()
    connected_websockets.append(websocket)
    print(f"📡 WebSocket client connected. Total: {len(connected_websockets)}")

    try:
        while True:
            # Send live telemetry every 3 seconds
            telemetry = simulator.generate_batch_telemetry()
            anomalies = analyze_batch(telemetry)

            data = {
                "type": "telemetry_update",
                "total_devices": len(telemetry),
                "anomalies": len(anomalies),
                "faulty_devices": [
                    {
                        "device_id": a["device_id"],
                        "fault_type": a["fault"]["type"],
                        "risk_level": a["outage"]["risk_level"]
                    }
                    for a in anomalies
                ],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            await websocket.send_json(data)
            await asyncio.sleep(3)

    except WebSocketDisconnect:
        connected_websockets.remove(websocket)
        print(f"📡 WebSocket client disconnected.")


async def broadcast_websocket(message: dict):
    """Broadcasts a message to all connected WebSocket clients."""
    for ws in connected_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            pass


# ─────────────────────────────────────────
# RUN SERVER
# ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )