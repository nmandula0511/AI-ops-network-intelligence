"""
Fault Scenarios
---------------
5 pre-built demo scenarios for the director presentation.
"""

FAULT_SCENARIOS = {
    "scenario_1": {
        "name": "Core Router BGP Failure",
        "description": "Core router loses BGP sessions causing cascading failures",
        "num_devices": 2,
        "expected_blast_radius": "high",
        "story": "Router R-01 loses BGP session. 47 downstream devices affected. AI detects in 8 seconds."
    },
    "scenario_2": {
        "name": "Distribution Switch Memory Exhaustion",
        "description": "Switch runs out of memory causing packet drops",
        "num_devices": 3,
        "expected_blast_radius": "medium",
        "story": "3 switches hit 95% memory. AI predicts full failure 20 mins before it happens."
    },
    "scenario_3": {
        "name": "DDoS Attack Pattern",
        "description": "Unusual traffic spike pattern resembling DDoS",
        "num_devices": 8,
        "expected_blast_radius": "low",
        "story": "8 access switches show abnormal traffic. Fault classifier identifies DDoS pattern."
    },
    "scenario_4": {
        "name": "Datacenter Network Partition",
        "description": "Entire datacenter segment becomes unreachable",
        "num_devices": 12,
        "expected_blast_radius": "critical",
        "story": "Full datacenter-west partition. AI recommends traffic rerouting."
    },
    "scenario_5": {
        "name": "Cascading Firewall Failure",
        "description": "Firewall config error causes cascading downstream failures",
        "num_devices": 5,
        "expected_blast_radius": "medium",
        "story": "Firewall policy causes 5 devices to drop. AI traces root cause and rolls back config."
    }
}


def get_scenario(scenario_id: str) -> dict:
    return FAULT_SCENARIOS.get(scenario_id, {})


def list_scenarios() -> list:
    return [
        {
            "id": k,
            "name": v["name"],
            "description": v["description"],
            "blast_radius": v["expected_blast_radius"]
        }
        for k, v in FAULT_SCENARIOS.items()
    ]


if __name__ == "__main__":
    print("Available fault scenarios:\n")
    for s in list_scenarios():
        print(f"  {s['id']}: {s['name']}")
        print(f"    {s['description']}")
        print(f"    Blast radius: {s['blast_radius']}\n")