"""
Network Simulator
-----------------
Simulates a realistic enterprise network with:
- Routers, switches, servers as devices
- Links/connections between devices
- Real-time telemetry metrics
- Fault injection for demo scenarios
"""

import json
import random
import uuid
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

DEVICE_TYPES = ["router", "switch", "firewall", "server", "load_balancer"]

LOCATIONS = [
    "datacenter-east", "datacenter-west", "datacenter-central",
    "branch-chicago", "branch-newyork", "branch-losangeles",
    "branch-houston", "branch-seattle"
]

VENDORS = ["Cisco", "Juniper", "Arista", "Palo Alto", "F5"]


def generate_network_topology(num_devices: int = 50) -> dict:
    devices = []
    links = []

    # Core routers
    core_routers = []
    for i in range(4):
        device = {
            "id": f"router-core-{i+1:02d}",
            "name": f"Core-Router-{i+1:02d}",
            "type": "router",
            "tier": "core",
            "location": LOCATIONS[i % len(LOCATIONS)],
            "vendor": random.choice(["Cisco", "Juniper"]),
            "ip_address": f"10.0.{i+1}.1",
            "status": "healthy",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        devices.append(device)
        core_routers.append(device["id"])

    # Connect core routers to each other
    for i in range(len(core_routers)):
        for j in range(i + 1, len(core_routers)):
            links.append({
                "id": f"link-{core_routers[i]}-{core_routers[j]}",
                "source": core_routers[i],
                "target": core_routers[j],
                "bandwidth_gbps": 100,
                "type": "fiber",
                "status": "healthy"
            })

    # Distribution switches
    dist_switches = []
    for i in range(8):
        device = {
            "id": f"switch-dist-{i+1:02d}",
            "name": f"Dist-Switch-{i+1:02d}",
            "type": "switch",
            "tier": "distribution",
            "location": LOCATIONS[i % len(LOCATIONS)],
            "vendor": random.choice(["Cisco", "Arista"]),
            "ip_address": f"10.1.{i+1}.1",
            "status": "healthy",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        devices.append(device)
        dist_switches.append(device["id"])

        parent_router = core_routers[i % len(core_routers)]
        links.append({
            "id": f"link-{parent_router}-{device['id']}",
            "source": parent_router,
            "target": device["id"],
            "bandwidth_gbps": 40,
            "type": "fiber",
            "status": "healthy"
        })

    # Access devices
    remaining = num_devices - len(devices)
    for i in range(remaining):
        device_type = random.choice(["switch", "server", "firewall", "load_balancer"])
        device = {
            "id": f"{device_type}-access-{i+1:02d}",
            "name": f"{device_type.title()}-{i+1:02d}",
            "type": device_type,
            "tier": "access",
            "location": random.choice(LOCATIONS),
            "vendor": random.choice(VENDORS),
            "ip_address": f"10.2.{random.randint(1,254)}.{random.randint(1,254)}",
            "status": "healthy",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        devices.append(device)

        parent_switch = random.choice(dist_switches)
        links.append({
            "id": f"link-{parent_switch}-{device['id']}",
            "source": parent_switch,
            "target": device["id"],
            "bandwidth_gbps": 10,
            "type": "ethernet",
            "status": "healthy"
        })

    return {
        "devices": devices,
        "links": links,
        "summary": {
            "total_devices": len(devices),
            "total_links": len(links),
            "core_routers": len(core_routers),
            "dist_switches": len(dist_switches),
            "access_devices": remaining
        }
    }


def generate_alerts(device: dict, is_faulty: bool) -> list:
    if not is_faulty:
        return []
    alert_templates = [
        f"HIGH CPU utilization on {device['name']} at {device['location']}",
        f"Memory exhaustion warning on {device['type']} {device['name']}",
        f"Packet loss detected on {device['name']} - threshold exceeded",
        f"BGP route flapping detected on {device['name']}",
        f"Interface error rate critical on {device['name']}",
        f"Latency spike detected on {device['name']} at {device['location']}",
    ]
    return random.sample(alert_templates, random.randint(1, 3))


def generate_telemetry(device: dict, fault_devices: set = None) -> dict:
    fault_devices = fault_devices or set()
    is_faulty = device["id"] in fault_devices

    if is_faulty:
        cpu_usage = random.uniform(85, 99)
        memory_usage = random.uniform(80, 99)
        latency_ms = random.uniform(200, 2000)
        packet_loss_pct = random.uniform(5, 30)
        bandwidth_utilization = random.uniform(90, 100)
        error_rate = random.uniform(0.1, 0.5)
    else:
        cpu_usage = random.uniform(10, 60)
        memory_usage = random.uniform(20, 70)
        latency_ms = random.uniform(1, 50)
        packet_loss_pct = random.uniform(0, 0.5)
        bandwidth_utilization = random.uniform(10, 70)
        error_rate = random.uniform(0, 0.01)

    return {
        "event_id": str(uuid.uuid4()),
        "device_id": device["id"],
        "device_name": device["name"],
        "device_type": device["type"],
        "location": device["location"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "cpu_usage_pct": round(cpu_usage, 2),
            "memory_usage_pct": round(memory_usage, 2),
            "latency_ms": round(latency_ms, 2),
            "packet_loss_pct": round(packet_loss_pct, 4),
            "bandwidth_utilization_pct": round(bandwidth_utilization, 2),
            "error_rate": round(error_rate, 4),
            "temperature_celsius": round(random.uniform(35, 75 if is_faulty else 55), 1),
            "uptime_seconds": random.randint(1000, 9999999)
        },
        "status": "critical" if is_faulty else "healthy",
        "alerts": generate_alerts(device, is_faulty)
    }


class NetworkSimulator:
    def __init__(self, num_devices: int = 50):
        print(f"🔧 Initializing network with {num_devices} devices...")
        self.topology = generate_network_topology(num_devices)
        self.fault_devices = set()
        print(f"✅ Network created:")
        print(f"   Devices : {self.topology['summary']['total_devices']}")
        print(f"   Links   : {self.topology['summary']['total_links']}")
        print(f"   Routers : {self.topology['summary']['core_routers']}")
        print(f"   Switches: {self.topology['summary']['dist_switches']}")

    def inject_fault(self, device_id=None, num_devices: int = 3):
        devices = self.topology["devices"]
        if device_id:
            self.fault_devices.add(device_id)
            print(f"🔴 Fault injected into: {device_id}")
        else:
            failing = random.sample(
                [d["id"] for d in devices],
                min(num_devices, len(devices))
            )
            self.fault_devices.update(failing)
            print(f"🔴 Fault injected into {len(failing)} devices: {failing}")

    def clear_faults(self):
        print(f"✅ Clearing all faults. Network recovering...")
        self.fault_devices.clear()

    def get_topology(self) -> dict:
        return self.topology

    def generate_batch_telemetry(self) -> list:
        return [
            generate_telemetry(device, self.fault_devices)
            for device in self.topology["devices"]
        ]


if __name__ == "__main__":
    simulator = NetworkSimulator(
        num_devices=int(os.getenv("NUMBER_OF_DEVICES", 50))
    )

    print("\n📊 Sample telemetry from 3 devices:")
    batch = simulator.generate_batch_telemetry()
    for event in batch[:3]:
        print(json.dumps(event, indent=2))

    print("\n💥 Injecting fault...")
    simulator.inject_fault(num_devices=3)

    print("\n📊 Telemetry after fault:")
    batch = simulator.generate_batch_telemetry()
    faulty = [e for e in batch if e["status"] == "critical"]
    for event in faulty[:2]:
        print(json.dumps(event, indent=2))