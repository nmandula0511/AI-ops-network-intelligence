"""
Graph Query Engine
------------------
Queries the network graph to answer critical questions.
"""

import os
import sys
from dotenv import load_dotenv
from gremlin_python.driver import client, serializer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


class NetworkGraphQueries:
    def __init__(self):
        self.endpoint = os.getenv("COSMOS_GREMLIN_ENDPOINT")
        self.key = os.getenv("COSMOS_PRIMARY_KEY")
        self.database = os.getenv("COSMOS_DATABASE")
        self.graph = os.getenv("COSMOS_GRAPH")

        print("🔌 Connecting to graph database...")
        self.client = client.Client(
            self.endpoint,
            "g",
            username=f"/dbs/{self.database}/colls/{self.graph}",
            password=self.key,
            message_serializer=serializer.GraphSONSerializersV2d0()
        )
        print("✅ Connected!")

    def _extract(self, d, key):
        val = d.get(key, ["unknown"])
        return val[0] if isinstance(val, list) else val

    def get_network_summary(self) -> dict:
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

    def get_critical_devices(self, top_n: int = 5) -> list:
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

    def get_blast_radius(self, device_id: str) -> dict:
        print(f"\n💥 Calculating blast radius for: {device_id}")

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

    def get_devices_by_location(self, location: str) -> list:
        return self.client.submit(
            f"g.V().has('location', '{location}').valueMap(true)"
        ).all().result()

    def get_neighbors(self, device_id: str) -> list:
        return self.client.submit(
            f"g.V('{device_id}').both().valueMap(true)"
        ).all().result()

    def close(self):
        self.client.close()


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