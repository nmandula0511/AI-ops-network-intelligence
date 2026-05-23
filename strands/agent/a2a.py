"""
strands/agent/a2a.py
====================
Mock A2AServer class for Strands agent integration testing.
"""

from typing import Any

class A2AServer:
    """
    Mock A2AServer that represents the agent hosting wrapper.
    In production, this would expose GET / and POST /a2a/tasks/send.
    """
    def __init__(self, agent: Any, port: int = 8080):
        self.agent = agent
        self.port = port

    def run(self):
        """Mock running server."""
        print(f"📡 A2AServer: Serving agent '{self.agent.model}' on port {self.port}...")
        print("✅ Server active (mocked).")
