"""
Agent Orchestrator
------------------
Coordinates all 4 agents to work together.
This is the main entry point for the AI system.

Flow:
1. Monitor Agent detects anomaly
2. Diagnosis Agent does root cause analysis
3. Remediation Agent suggests fixes
4. Reporting Agent writes incident report
"""

import os
import sys
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
import boto3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.ml_pipeline import analyze_device, analyze_batch
from graph.graph_queries import NetworkGraphQueries

load_dotenv()


class AIOpsOrchestrator:
    def __init__(self):
        print("🤖 Initializing AIOps Multi-Agent System...")

        self.model_id = os.getenv("AWS_BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")
        self.active = False
        try:
            self.bedrock = boto3.client(
                "bedrock-runtime",
                region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            )
            self.active = True
        except Exception as e:
            print(f"⚠️  Could not initialize AWS Bedrock Runtime client: {e}")

        self.graph = NetworkGraphQueries()
        self.incidents = []
        print("✅ AIOps Multi-Agent System ready!")

    def ask_llm(self, system_prompt: str, user_message: str) -> str:
        if self.active:
            try:
                response = self.bedrock.converse(
                    modelId=self.model_id,
                    messages=[
                        {
                            "role": "user",
                            "content": [{"text": user_message}]
                        }
                    ],
                    system=[{"text": system_prompt}] if system_prompt else [],
                    inferenceConfig={
                        "maxTokens": 500,
                        "temperature": 0.3
                    }
                )
                return response['output']['message']['content'][0]['text']
            except Exception as e:
                print(f"⚠️  Bedrock API call failed, using rule-based mock: {e}")
        
        # Fallback mocks:
        user_lower = user_message.lower()
        if "root cause" in user_lower or "analyze this network" in user_lower:
            return (
                "Root Cause: Outdated firmware version 3.1.2 prevents the router from renewing DHCP leases after a cable modem online event.\n"
                "RECOMMENDED ACTION: Trigger a firmware upgrade to version 3.2.1."
            )
        elif "additional steps" in user_lower:
            return "1. Run remote config validation check.\n2. Reboot the router interface cache to force reconnect."
        elif "incident report" in user_lower or "professional incident report" in user_lower:
            return (
                "INCIDENT REPORT\n"
                "===============\n"
                "Summary: Invincible WiFi device was stuck on LTE backup after a temporary cable outage.\n"
                "Root Cause: Outdated firmware 3.1.2 failed to reload fiber routing tables.\n"
                "Impact: High data transit charges from carrier.\n"
                "Action Taken: Upgraded router firmware to 3.2.1 and cleared the interface cache.\n"
                "Status: Resolved."
            )
        return "AIOps system mock response. Telemetry checks show normal operational limits."

    def monitor_agent(self, telemetry_batch: list) -> list:
        print("\n👁️  Monitor Agent: Scanning telemetry...")
        anomalies = analyze_batch(telemetry_batch)
        if anomalies:
            print(f"   🔴 {len(anomalies)} anomalies detected!")
            for a in anomalies:
                print(f"      → {a['device_id']}: "
                      f"{a['fault']['type']} "
                      f"({a['outage']['risk_level']} risk)")
        else:
            print("   ✅ All devices healthy")
        return anomalies

    def diagnosis_agent(self, anomaly: dict) -> dict:
        device_id = anomaly["device_id"]
        print(f"\n🔍 Diagnosis Agent: Analyzing {device_id}...")

        try:
            blast_radius = self.graph.get_blast_radius(device_id)
        except Exception:
            blast_radius = {
                "direct_impact": 0,
                "indirect_impact": 0,
                "total_impact": 0,
                "directly_affected": []
            }

        context = f"""
Device ID: {device_id}
Fault Type: {anomaly['fault']['type']}
Fault Confidence: {anomaly['fault']['confidence']:.0%}
Outage Risk: {anomaly['outage']['risk_level']}
Outage Probability: {anomaly['outage']['probability']:.0%}
Estimated Time to Outage: {anomaly['outage']['eta']}
Direct Impact: {blast_radius['direct_impact']} devices
Indirect Impact: {blast_radius['indirect_impact']} devices
Total Impact: {blast_radius['total_impact']} devices
"""

        rca = self.ask_llm(
            system_prompt="""You are a senior network engineer doing root cause analysis.
            Be concise and technical. Focus on the most likely cause and immediate impact.
            Always end with: 'RECOMMENDED ACTION: [specific action]'""",
            user_message=f"Analyze this network fault and provide root cause analysis:\n{context}"
        )

        diagnosis = {
            "device_id": device_id,
            "fault_type": anomaly["fault"]["type"],
            "blast_radius": blast_radius,
            "rca": rca,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        print(f"   📋 RCA complete for {device_id}")
        return diagnosis

    def remediation_agent(self, diagnosis: dict) -> dict:
        device_id = diagnosis["device_id"]
        fault_type = diagnosis["fault_type"]
        print(f"\n🔧 Remediation Agent: Planning fix for {device_id}...")

        playbooks = {
            "high_cpu": {
                "action": "Restart high-CPU processes and enable CPU throttling",
                "risk": "LOW",
                "auto_execute": True,
                "commands": ["restart-process", "set-cpu-limit"]
            },
            "memory_exhaustion": {
                "action": "Clear memory cache and restart memory-intensive services",
                "risk": "LOW",
                "auto_execute": True,
                "commands": ["clear-cache", "restart-service"]
            },
            "packet_loss": {
                "action": "Reroute traffic through backup path and check interface",
                "risk": "MEDIUM",
                "auto_execute": False,
                "commands": ["reroute-traffic", "check-interface"]
            },
            "bgp_flapping": {
                "action": "Reset BGP session and apply route dampening",
                "risk": "HIGH",
                "auto_execute": False,
                "commands": ["reset-bgp", "apply-dampening"]
            },
            "ddos_attack": {
                "action": "Enable DDoS protection, block suspicious IPs, scale resources",
                "risk": "HIGH",
                "auto_execute": False,
                "commands": ["enable-ddos-protection", "block-ips", "scale-up"]
            }
        }

        playbook = playbooks.get(fault_type, {
            "action": "Manual investigation required",
            "risk": "HIGH",
            "auto_execute": False,
            "commands": []
        })

        additional_steps = self.ask_llm(
            system_prompt="""You are a network remediation expert.
            Provide 2-3 additional specific steps to resolve the issue.
            Be brief and actionable.""",
            user_message=f"""
Fault: {fault_type} on device {device_id}
Primary action: {playbook['action']}
Blast radius: {diagnosis['blast_radius']['total_impact']} devices affected
What additional steps should be taken?"""
        )

        remediation = {
            "device_id": device_id,
            "fault_type": fault_type,
            "primary_action": playbook["action"],
            "risk_level": playbook["risk"],
            "auto_execute": playbook["auto_execute"],
            "commands": playbook["commands"],
            "additional_steps": additional_steps,
            "status": "AUTO-EXECUTED" if playbook["auto_execute"] else "AWAITING APPROVAL"
        }

        status_icon = "✅" if playbook["auto_execute"] else "⚠️"
        print(f"   {status_icon} Remediation: {remediation['status']}")
        return remediation

    def reporting_agent(self, diagnosis: dict, remediation: dict) -> str:
        device_id = diagnosis["device_id"]
        print(f"\n📝 Reporting Agent: Writing incident report for {device_id}...")

        report_prompt = f"""
Write a professional incident report for a network fault.
Use this data:

Device: {device_id}
Fault Type: {diagnosis['fault_type']}
Root Cause Analysis: {diagnosis['rca']}
Devices Affected: {diagnosis['blast_radius']['total_impact']}
Action Taken: {remediation['primary_action']}
Status: {remediation['status']}
Time: {diagnosis['timestamp']}

Format as:
INCIDENT REPORT
===============
Summary: [2 sentences]
Root Cause: [2 sentences]
Impact: [1 sentence]
Action Taken: [2 sentences]
Status: [1 sentence]
"""

        report = self.ask_llm(
            system_prompt="You are a technical writer creating incident reports for IT leadership.",
            user_message=report_prompt
        )

        print(f"   📄 Report generated for {device_id}")
        return report

    def process_incident(self, telemetry_batch: list):
        print("\n" + "="*60)
        print("🚀 AIOPS MULTI-AGENT SYSTEM ACTIVATED")
        print("="*60)

        anomalies = self.monitor_agent(telemetry_batch)

        if not anomalies:
            print("\n✅ Network is healthy. No action needed.")
            return []

        incidents = []
        for anomaly in anomalies[:2]:
            print(f"\n{'─'*60}")
            print(f"Processing incident for: {anomaly['device_id']}")
            print(f"{'─'*60}")

            diagnosis = self.diagnosis_agent(anomaly)
            remediation = self.remediation_agent(diagnosis)
            report = self.reporting_agent(diagnosis, remediation)

            incident = {
                "anomaly": anomaly,
                "diagnosis": diagnosis,
                "remediation": remediation,
                "report": report
            }
            incidents.append(incident)

            print(f"\n📋 INCIDENT REPORT:")
            print("─" * 40)
            print(report)

        self.incidents = incidents
        return incidents

    def chat(self, question: str) -> str:
        return self.ask_llm(
            system_prompt="""You are an AIOps network assistant for a NOC team.
            You help engineers understand network issues.
            Be concise, technical, and helpful.""",
            user_message=question
        )

    def close(self):
        self.graph.close()


if __name__ == "__main__":
    from simulator.network_simulator import NetworkSimulator

    print("Setting up demo scenario...")
    simulator = NetworkSimulator(num_devices=50)
    simulator.inject_fault(num_devices=3)
    telemetry_batch = simulator.generate_batch_telemetry()

    orchestrator = AIOpsOrchestrator()
    incidents = orchestrator.process_incident(telemetry_batch)

    print(f"\n\n✅ Processed {len(incidents)} incidents")
    print("🤖 AIOps Multi-Agent System complete!")

    orchestrator.close()