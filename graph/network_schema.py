"""
Network Graph Schema
--------------------
Defines what our graph looks like.

NODES (vertices) = devices (routers, switches, servers)
EDGES (links)    = connections between devices

Think of it like:
- Nodes = cities on a map
- Edges = roads connecting cities
"""

# Node types in our graph
NODE_TYPES = {
    "router": {
        "label": "router",
        "properties": [
            "id", "name", "type", "tier",
            "location", "vendor", "ip_address",
            "status", "created_at"
        ]
    },
    "switch": {
        "label": "switch",
        "properties": [
            "id", "name", "type", "tier",
            "location", "vendor", "ip_address",
            "status", "created_at"
        ]
    },
    "firewall": {
        "label": "firewall",
        "properties": [
            "id", "name", "type", "tier",
            "location", "vendor", "ip_address",
            "status", "created_at"
        ]
    },
    "server": {
        "label": "server",
        "properties": [
            "id", "name", "type", "tier",
            "location", "vendor", "ip_address",
            "status", "created_at"
        ]
    },
    "load_balancer": {
        "label": "load_balancer",
        "properties": [
            "id", "name", "type", "tier",
            "location", "vendor", "ip_address",
            "status", "created_at"
        ]
    }
}

# Edge types in our graph
EDGE_TYPES = {
    "CONNECTS_TO": {
        "label": "CONNECTS_TO",
        "properties": [
            "id", "bandwidth_gbps",
            "type", "status"
        ]
    }
}

# Graph summary for documentation
GRAPH_SUMMARY = {
    "name": "AIOps Network Topology Graph",
    "description": "Enterprise network topology for AIOps platform",
    "node_types": list(NODE_TYPES.keys()),
    "edge_types": list(EDGE_TYPES.keys()),
    "use_cases": [
        "Blast radius analysis",
        "Dependency mapping",
        "Root cause analysis",
        "Network visualization"
    ]
}


if __name__ == "__main__":
    print("Graph Schema Summary:")
    print(f"  Node types: {GRAPH_SUMMARY['node_types']}")
    print(f"  Edge types: {GRAPH_SUMMARY['edge_types']}")
    print(f"  Use cases:")
    for use_case in GRAPH_SUMMARY["use_cases"]:
        print(f"    - {use_case}")