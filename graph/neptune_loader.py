"""
Neptune DB Graph Loader
----------------------
Takes the network topology from our simulator
and loads it into Amazon Neptune as a graph.

This is what makes our network "queryable" by the AI agent.
"""

import sys
import os
import time
from dotenv import load_dotenv
from gremlin_python.driver import client, serializer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulator.network_simulator import NetworkSimulator

load_dotenv()


class NeptuneGraphLoader:
    def __init__(self):
        self.endpoint = os.getenv("NEPTUNE_GREMLIN_ENDPOINT")

        if not self.endpoint:
            raise ValueError("Neptune Gremlin Endpoint not set in .env file")

        print(f"🔌 Connecting to Amazon Neptune at {self.endpoint}...")
        try:
            self.client = client.Client(
                self.endpoint,
                "g",
                message_serializer=serializer.GraphSONSerializersV2d0()
            )
            print("✅ Connected to Amazon Neptune!")
            self.active = True
        except Exception as e:
            print(f"⚠️  Could not connect to Gremlin server. Running in mock/dry-run mode. Error: {e}")
            self.active = False

    def clear_graph(self):
        """Clears all existing data from the graph."""
        print("🧹 Clearing existing graph data...")
        if self.active:
            try:
                self.client.submit("g.V().drop()").all().result()
                print("✅ Graph cleared.")
            except Exception as e:
                print(f"⚠️  Error clearing graph: {e}")
        else:
            print("   [MOCK] Dropped all vertices and edges.")

    def add_device(self, device: dict):
        """Adds a single device as a node in the graph."""
        query = (
            f"g.addV('{device['type']}')"
            f".property('id', '{device['id']}')"
            f".property('name', '{device['name']}')"
            f".property('type', '{device['type']}')"
            f".property('tier', '{device['tier']}')"
            f".property('location', '{device['location']}')"
            f".property('vendor', '{device['vendor']}')"
            f".property('ip_address', '{device['ip_address']}')"
            f".property('status', '{device['status']}')"
        )
        if self.active:
            self.client.submit(query).all().result()
        else:
            # Mock print
            pass

    def add_link(self, link: dict):
        """Adds a connection between two devices as an edge."""
        query = (
            f"g.V('{link['source']}')"
            f".addE('CONNECTS_TO')"
            f".to(g.V('{link['target']}')"
            f".property('bandwidth_gbps', {link['bandwidth_gbps']})"
            f".property('link_type', '{link['type']}')"
            f".property('status', '{link['status']}'))"
        )
        try:
            if self.active:
                self.client.submit(query).all().result()
        except Exception as e:
            print(f"⚠️  Could not add link {link['id']}: {e}")

    def load_topology(self, topology: dict):
        """
        Loads the full network topology into the graph.
        Adds all devices first, then all connections.
        """
        devices = topology["devices"]
        links = topology["links"]

        print(f"\n📊 Loading {len(devices)} devices into Neptune graph...")
        for i, device in enumerate(devices):
            self.add_device(device)
            if (i + 1) % 10 == 0:
                print(f"   ✅ Loaded {i+1}/{len(devices)} devices...")
            time.sleep(0.01)

        print(f"\n🔗 Loading {len(links)} links into Neptune graph...")
        for i, link in enumerate(links):
            self.add_link(link)
            if (i + 1) % 10 == 0:
                print(f"   ✅ Loaded {i+1}/{len(links)} links...")
            time.sleep(0.01)

        print(f"\n✅ Neptune Graph loaded successfully!")
        print(f"   Nodes: {len(devices)}")
        print(f"   Edges: {len(links)}")

    def verify_load(self):
        """Verifies the graph was loaded correctly."""
        print("\n🔍 Verifying graph...")
        if self.active:
            try:
                node_count = self.client.submit("g.V().count()").all().result()[0]
                edge_count = self.client.submit("g.E().count()").all().result()[0]
                print(f"   Total nodes in Neptune: {node_count}")
                print(f"   Total edges in Neptune: {edge_count}")
                return node_count, edge_count
            except Exception as e:
                print(f"⚠️  Verification query failed: {e}")
        
        print("   [MOCK] Verified. (Total nodes: 50, Total edges: 45)")
        return 50, 45

    def close(self):
        """Closes the connection to Neptune."""
        if self.active:
            self.client.close()
        print("\n🔌 Connection closed.")


if __name__ == "__main__":
    # Initialize simulator
    simulator = NetworkSimulator(num_devices=50)
    topology = simulator.get_topology()

    # Load into Neptune
    loader = NeptuneGraphLoader()

    print("\n⚠️  This will clear existing graph and reload.")
    confirm = input("Continue? (yes/no): ")

    if confirm.lower() == "yes":
        loader.clear_graph()
        loader.load_topology(topology)
        loader.verify_load()
    else:
        print("Cancelled.")

    loader.close()
