"""
Cosmos DB Graph Loader
----------------------
Takes the network topology from our simulator
and loads it into Azure Cosmos DB as a graph.

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


class CosmosGraphLoader:
    def __init__(self):
        self.endpoint = os.getenv("COSMOS_GREMLIN_ENDPOINT")
        self.key = os.getenv("COSMOS_PRIMARY_KEY")
        self.database = os.getenv("COSMOS_DATABASE")
        self.graph = os.getenv("COSMOS_GRAPH")

        if not self.endpoint or not self.key:
            raise ValueError("Cosmos DB credentials not set in .env file")

        print("🔌 Connecting to Azure Cosmos DB...")
        self.client = client.Client(
            self.endpoint,
            "g",
            username=f"/dbs/{self.database}/colls/{self.graph}",
            password=self.key,
            message_serializer=serializer.GraphSONSerializersV2d0()
        )
        print("✅ Connected to Cosmos DB!")

    def clear_graph(self):
        """Clears all existing data from the graph."""
        print("🧹 Clearing existing graph data...")
        self.client.submit("g.V().drop()").all().result()
        print("✅ Graph cleared.")

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
            f".property('pk', '{device['type']}')"
        )
        self.client.submit(query).all().result()

    def add_link(self, link: dict):
        """Adds a connection between two devices as an edge."""
        query = (
            f"g.V('{link['source']}')"
            f".addE('CONNECTS_TO')"
            f".to(g.V('{link['target']}')"
            f".property('bandwidth_gbps', {link['bandwidth_gbps']})"
            f".property('link_type', '{link['type']}')"
            f".property('status', '{link['status']}')"
            f".property('pk', 'CONNECTS_TO'))"
        )
        try:
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

        print(f"\n📊 Loading {len(devices)} devices into graph...")
        for i, device in enumerate(devices):
            self.add_device(device)
            if (i + 1) % 10 == 0:
                print(f"   ✅ Loaded {i+1}/{len(devices)} devices...")
            time.sleep(0.1)

        print(f"\n🔗 Loading {len(links)} links into graph...")
        for i, link in enumerate(links):
            self.add_link(link)
            if (i + 1) % 10 == 0:
                print(f"   ✅ Loaded {i+1}/{len(links)} links...")
            time.sleep(0.1)

        print(f"\n✅ Graph loaded successfully!")
        print(f"   Nodes: {len(devices)}")
        print(f"   Edges: {len(links)}")

    def verify_load(self):
        """Verifies the graph was loaded correctly."""
        print("\n🔍 Verifying graph...")

        node_count = self.client.submit(
            "g.V().count()"
        ).all().result()[0]

        edge_count = self.client.submit(
            "g.E().count()"
        ).all().result()[0]

        print(f"   Total nodes in graph: {node_count}")
        print(f"   Total edges in graph: {edge_count}")
        return node_count, edge_count

    def close(self):
        """Closes the connection to Cosmos DB."""
        self.client.close()
        print("\n🔌 Connection closed.")


if __name__ == "__main__":
    # Initialize simulator
    simulator = NetworkSimulator(num_devices=50)
    topology = simulator.get_topology()

    # Load into Cosmos DB
    loader = CosmosGraphLoader()

    print("\n⚠️  This will clear existing graph and reload.")
    confirm = input("Continue? (yes/no): ")

    if confirm.lower() == "yes":
        loader.clear_graph()
        loader.load_topology(topology)
        loader.verify_load()
    else:
        print("Cancelled.")

    loader.close()