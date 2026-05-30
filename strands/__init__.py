"""
strands
=======
Mock Strands SDK for local execution and demo verification.
Allows import of Agent and @tool.
"""

import os
import re
import inspect
from typing import Optional, List, Callable, Any
import boto3

def tool(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to mark a function as a reusable Strands agent tool.
    Registers metadata for discovery and reasoning.
    """
    func.is_tool = True
    sig = inspect.signature(func)
    
    parameters = {}
    for name, param in sig.parameters.items():
        # Get parameter type
        ptype = "string"
        if param.annotation == int:
            ptype = "integer"
        elif param.annotation == bool:
            ptype = "boolean"
        elif param.annotation == float:
            ptype = "number"
            
        parameters[name] = {
            "type": ptype,
            "required": param.default == inspect.Parameter.empty
        }
        
    func.tool_schema = {
        "id": func.__name__,
        "name": func.__name__.replace("_", " ").title(),
        "description": func.__doc__.strip() if func.__doc__ else "",
        "parameters": parameters
    }
    return func


class Agent:
    """
    Mock Agent representing the AWS Strands Agent class.
    Uses Azure OpenAI gpt-4o (from .env) or fallback rule-based diagnostics to analyze device state.
    """
    def __init__(
        self,
        model: str,
        tools: List[Callable[..., Any]],
        system_prompt: str,
        session_id: Optional[str] = None
    ):
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        self.session_id = session_id

    def __call__(self, prompt: str) -> str:
        """
        Executes the agent logic.
        Extracts device_id, gathers telemetry and status, then calls Azure OpenAI or uses custom fallback rules.
        """
        # Find device ID in prompt (format: INV-WIFI-XXXXXXXXXX)
        device_match = re.search(r'INV-WIFI-\d{10}', prompt)
        device_id = device_match.group(0) if device_match else None
        
        # 1. Gather device metrics using our tools
        device_data = {}
        if device_id:
            # Dynamically call our tools if they are in self.tools
            for t in self.tools:
                t_name = t.__name__
                try:
                    if t_name == "get_device_lte_duration":
                        device_data["lte_duration"] = t(device_id)
                    elif t_name == "get_cable_modem_status":
                        device_data["modem_status"] = t(device_id)
                    elif t_name == "check_firmware_version":
                        device_data["firmware_info"] = t(device_id)
                    elif t_name == "query_device_event_history":
                        device_data["event_history"] = t(device_id)
                except Exception as e:
                    print(f"Error running tool {t_name}: {e}")

        # 2. Try calling AWS Bedrock if client is available
        model_id = os.getenv("AWS_BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")
        
        # Format tool data into user query
        enriched_user_message = f"User Request: {prompt}\n\n"
        if device_data:
            enriched_user_message += "Device Telemetry & Status Logs (retrieved from tools):\n"
            import json
            enriched_user_message += json.dumps(device_data, indent=2)

        try:
            bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            )
            response = bedrock_client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": enriched_user_message}]
                    }
                ],
                system=[{"text": self.system_prompt}] if self.system_prompt else [],
                inferenceConfig={
                    "maxTokens": 800,
                    "temperature": 0.3
                }
            )
            return response['output']['message']['content'][0]['text']
        except Exception:
            # Silently fallback to rules in local execution without printing stacktrace
            pass

        # 3. Fallback rule-based diagnostics (if API fails or keys aren't set)
        if device_id and device_data:
            lte_info = device_data.get("lte_duration", {})
            modem_info = device_data.get("modem_status", {})
            fw_info = device_data.get("firmware_info", {})
            
            duration = lte_info.get("lte_duration_minutes", 0)
            severity = lte_info.get("severity", "GREEN")
            modem_online = modem_info.get("modem_online", True)
            firmware = fw_info.get("current_firmware", "3.2.1")
            
            # Determine root cause & recommendations
            if not modem_online:
                root_cause = f"Cable modem associated with {device_id} is OFFLINE."
                action = (
                    "Reboot the cable modem by unplugging it for 30 seconds, then plugging it back in. "
                    "Ensure all coaxial cable connections are hand-tight."
                )
                resolution_time = 10
                truck_roll = False
                confidence = 0.95
            elif firmware != "3.2.1" and firmware < "3.2.0":
                root_cause = f"Outdated firmware ({firmware}) bug prevents automatic reconnect to fiber."
                action = (
                    "Push a remote firmware upgrade (version 3.2.1) to the router, "
                    "then trigger a remote config reload or device reboot."
                )
                resolution_time = 15
                truck_roll = False
                confidence = 0.90
            elif duration > 120 and modem_online:
                root_cause = "Device state cache is out-of-sync after a brief cable disconnect."
                action = (
                    "Perform a soft refresh of the interface cache. Ask the customer to hold the "
                    "reset button on the back of the router for 3 seconds."
                )
                resolution_time = 5
                truck_roll = False
                confidence = 0.85
            else:
                root_cause = "Transient routing instability. Device switchback is pending automatic timers."
                action = "Monitor device status. Automatic switchback should occur within 10 minutes."
                resolution_time = 10
                truck_roll = False
                confidence = 0.80

            # Green threshold fallback
            if duration < 60:
                severity = "GREEN"
                root_cause = "Device is on LTE backup within normal duration."
                action = "No action required. Telemetry metrics show active and healthy backup connection."
                resolution_time = 0
                truck_roll = False
                confidence = 1.0

            # Override for critical failures
            if duration > 1440 and not modem_online:  # 24+ hours offline
                root_cause = "Physical line damage or local hardware failure."
                action = "Escalate to Field Operations. Schedule an engineer site visit (truck roll)."
                resolution_time = 120
                truck_roll = True
                confidence = 0.90

            requires_roll_str = "Yes" if truck_roll else "No"
            reason_str = " (Physical hardware failure detected)" if truck_roll else " (Issues can be resolved via remote config or customer self-service)"
            
            return f"""Severity: {severity}
Duration: {duration} minutes on LTE
Root cause: {root_cause}
Confidence: {int(confidence * 100)}%
Action required: {action}
Truck roll needed: {requires_roll_str}{reason_str}"""
        
        # General chat response fallback
        return f"Hello! I am the Invincible WiFi agent. I can help diagnose devices stuck on LTE. Please provide a device ID like INV-WIFI-1234567890."
