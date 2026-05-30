"""
Graph Query Engine
------------------
Queries the Amazon Neptune network graph to answer critical questions.
Supports active database connections and local dry-run mocks.
"""

import os
import sys
from dotenv import load_dotenv
from gremlin_python.driver import client, serializer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


class NetworkGraphQueries:
    def __init__(self):
        self.endpoint = os.getenv("NEPTUNE_GREMLIN_ENDPOINT")

        print("🔌 Connecting to Neptune graph database...")
        try:
            if not self.endpoint:
                raise ValueError("NEPTUNE_GREMLIN_ENDPOINT not set in environment.")
            self.client = client.Client(
                self.endpoint,
                "g",
                message_serializer=serializer.GraphSONSerializersV2d0()
            )
            print("✅ Connected to Neptune Gremlin server!")
            self.active = True
        except Exception as e:
            print(f"⚠️  Could not connect to Gremlin database server (running in mock mode): {e}")
            self.active = False

    def _extract(self, d, key):
        val = d.get(key, ["unknown"])
        return val[0] if isinstance(val, list) else val

    def get_network_summary(self) -> dict:
        if self.active:
            try:
                total_nodes = self.client.submit("g.V().count()").all().result()[0]
                total_edges = self.client.submit("g.E().count()").all().result()[0]
                routers = self.client.submit("g.V().hasLabel('router').count()").all().result()[0]
                switches = self.client.submit("g.V().hasLabel('switch').count()").all().result()[0]
                return {
                    "total_devices": total_nodes,
                    "total_connections": total_edges,
                    "routers": routers,
                    "switches": switches,
                    "other_devices": total_nodes - routers - switches
                }
            except Exception as e:
                print(f"⚠️ Neptune summary query failed, using fallback: {e}")

        # Fallback Mock
        return {
            "total_devices": 50,
            "total_connections": 45,
            "routers": 42,
            "switches": 8,
            "other_devices": 0
        }

    def get_critical_devices(self, top_n: int = 5) -> list:
        if self.active:
            try:
                result = self.client.submit(
                    f"g.V().order().by(__.bothE().count(), decr).limit({top_n}).valueMap(true)"
                ).all().result()

                critical = []
                for device in result:
                    device_id = self._extract(device, "id")
                    connections = self.client.submit(
                        f"g.V('{device_id}').bothE().count()"
                    ).all().result()[0]
                    critical.append({
                        "id": device_id,
                        "name": self._extract(device, "name"),
                        "type": self._extract(device, "type"),
                        "location": self._extract(device, "location"),
                        "connections": connections
                    })
                return critical
            except Exception as e:
                print(f"⚠️ Neptune query failed, using fallback: {e}")

        # Fallback Mock
        return [
            {"id": "router-core-01", "name": "Core Router 01", "type": "router", "location": "CO", "connections": 8},
            {"id": "router-core-02", "name": "Core Router 02", "type": "router", "location": "NY", "connections": 7},
            {"id": "switch-dist-01", "name": "Dist Switch 01", "type": "switch", "location": "CA", "connections": 5},
            {"id": "router-edge-10", "name": "Edge Router 10", "type": "router", "location": "FL", "connections": 4},
            {"id": "router-edge-15", "name": "Edge Router 15", "type": "router", "location": "IL", "connections": 3}
        ]

    def get_blast_radius(self, device_id: str) -> dict:
        print(f"\n💥 Calculating blast radius for: {device_id}")

        if self.active:
            try:
                direct = self.client.submit(
                    f"g.V('{device_id}').out().valueMap(true)"
                ).all().result()

                indirect = self.client.submit(
                    f"g.V('{device_id}').out().out().valueMap(true)"
                ).all().result()

                blast_radius = {
                    "source_device": device_id,
                    "direct_impact": len(direct),
                    "indirect_impact": len(indirect),
                    "total_impact": len(direct) + len(indirect),
                    "directly_affected": [
                        {
                            "id": self._extract(d, "id"),
                            "name": self._extract(d, "name"),
                            "type": self._extract(d, "type"),
                            "location": self._extract(d, "location")
                        }
                        for d in direct
                    ],
                    "indirectly_affected": [
                        {
                            "id": self._extract(d, "id"),
                            "name": self._extract(d, "name"),
                            "type": self._extract(d, "type")
                        }
                        for d in indirect
                    ]
                }

                print(f"   Direct impact  : {blast_radius['direct_impact']} devices")
                print(f"   Indirect impact: {blast_radius['indirect_impact']} devices")
                print(f"   Total impact   : {blast_radius['total_impact']} devices")
                return blast_radius
            except Exception as e:
                print(f"⚠️ Neptune query failed, using fallback: {e}")

        # Fallback Mock
        blast_radius = {
            "source_device": device_id,
            "direct_impact": 2,
            "indirect_impact": 4,
            "total_impact": 6,
            "directly_affected": [
                {"id": "switch-dist-01", "name": "Dist Switch 01", "type": "switch", "location": "CO"},
                {"id": "switch-dist-02", "name": "Dist Switch 02", "type": "switch", "location": "CO"}
            ],
            "indirectly_affected": [
                {"id": "INV-WIFI-1234567801", "name": "Invincible WiFi 01", "type": "router"},
                {"id": "INV-WIFI-1234567802", "name": "Invincible WiFi 02", "type": "router"},
                {"id": "INV-WIFI-1234567803", "name": "Invincible WiFi 03", "type": "router"},
                {"id": "INV-WIFI-1234567804", "name": "Invincible WiFi 04", "type": "router"}
            ]
        }
        print(f"   [MOCK] Direct impact  : 2 devices")
        print(f"   [MOCK] Indirect impact: 4 devices")
        print(f"   [MOCK] Total impact   : 6 devices")
        return blast_radius

    def get_devices_by_location(self, location: str) -> list:
        if self.active:
            try:
                return self.client.submit(
                    f"g.V().has('location', '{location}').valueMap(true)"
                ).all().result()
            except Exception as e:
                print(f"⚠️ Neptune query failed: {e}")
        return []

    def get_neighbors(self, device_id: str) -> list:
        if self.active:
            try:
                return self.client.submit(
                    f"g.V('{device_id}').both().valueMap(true)"
                ).all().result()
            except Exception as e:
                print(f"⚠️ Neptune query failed: {e}")
        return []

    def close(self):
        if self.active:
            self.client.close()
            print("\n🔌 Graph connection closed.")


if __name__ == "__main__":
    queries = NetworkGraphQueries()

    print("\n📊 Network Summary:")
    summary = queries.get_network_summary()
    for key, value in summary.items():
        print(f"   {key}: {value}")

    print("\n🔥 Most Critical Devices:")
    critical = queries.get_critical_devices(top_n=5)
    for device in critical:
        print(f"   {device['name']} ({device['type']}) "
              f"— {device['connections']} connections "
              f"@ {device['location']}")

    print("\n💥 Blast Radius Test (Core Router 01):")
    blast = queries.get_blast_radius("router-core-01")
    print(f"   Directly affected  : {blast['direct_impact']} devices")
    print(f"   Indirectly affected: {blast['indirect_impact']} devices")
    print(f"   Total impact       : {blast['total_impact']} devices")

    queries.close()