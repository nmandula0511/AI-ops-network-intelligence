"""
agent/factory.py
================
Story 4 — Factory Pattern

CRITICAL: NEVER share one agent instance across users.
Each user session gets its own isolated Agent() instance.
Without this, Engineer A sees Engineer B's conversation context.

AI IDE NOTE:
- Model: amazon.nova-pro-v1:0 (always use this unless told otherwise)
- Tools imported from src/tools/ — each is @tool decorated
- session_id isolates conversation history per user
- system_prompt can be found in agent/prompts.py
"""

import uuid
from typing import Optional
from strands import Agent

# Tools — each is @tool decorated (Story 3)
from src.tools.device_tools import (
    get_device_lte_duration,
    get_cable_modem_status,
    check_firmware_version,
    calculate_mathematical_rules_score,
)
from src.tools.aurora_tools import (
    query_device_event_history,
    get_devices_by_region,
)
from src.tools.action_tools import (
    generate_customer_recommendation,
    flag_for_truck_roll,
    create_outreach_ticket,
)
from src.tools.bedrock_tools import (
    analyze_with_bedrock,
    summarize_findings,
)

from src.agent.prompts import SMARTEDGE_DIAGNOSTICS_SYSTEM_PROMPT


# All tools available to the agent
AGENT_TOOLS = [
    # Diagnostic tools
    get_device_lte_duration,
    get_cable_modem_status,
    check_firmware_version,
    calculate_mathematical_rules_score,
    # Data retrieval tools
    query_device_event_history,
    get_devices_by_region,
    # Action tools
    generate_customer_recommendation,
    flag_for_truck_roll,
    create_outreach_ticket,
    # AI analysis tools
    analyze_with_bedrock,
    summarize_findings,
]


def create_smartedge_diagnostics_agent(
    session_id: Optional[str] = None,
    user_context: Optional[dict] = None
) -> Agent:
    """
    Factory function. Creates an ISOLATED agent instance per user/session.
    
    WHY: If two NOC engineers use the agent simultaneously and share
    one instance, Engineer A can see Engineer B's device data. The factory
    pattern prevents this by giving each user their own Agent() with its
    own conversation history.
    
    Args:
        session_id: Unique ID for this session. Auto-generated if None.
                    Use format: f"{user_id}-{device_id}" for traceability.
        user_context: Optional dict. If provided, personalizes system prompt.
                      Keys: "name" (str), "team" (str), "role" (str)
    
    Returns:
        Fresh Agent instance. Zero prior conversation history.
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    # Optionally personalize the system prompt
    system_prompt = SMARTEDGE_DIAGNOSTICS_SYSTEM_PROMPT
    if user_context:
        user_lines = [
            f"\n--- Session Context ---",
            f"Engineer: {user_context.get('name', 'Unknown')}",
            f"Team: {user_context.get('team', 'Unknown')}",
            f"Role: {user_context.get('role', 'Unknown')}",
            f"Session ID: {session_id}",
        ]
        system_prompt += "\n".join(user_lines)

    # Nova Pro configuration setup (temperature=0, streaming=False, topK=1)
    return Agent(
        model="amazon.nova-pro-v1:0",
        tools=AGENT_TOOLS,
        system_prompt=system_prompt,
        session_id=session_id
    )

