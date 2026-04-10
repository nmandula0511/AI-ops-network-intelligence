"""
Event Hubs Producer
-------------------
Streams network telemetry to Azure Event Hubs in real time.
"""

import asyncio
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.eventhub.aio import EventHubProducerClient
from azure.eventhub import EventData
from dotenv import load_dotenv
from simulator.network_simulator import NetworkSimulator
from datetime import datetime

load_dotenv()


class TelemetryProducer:
    def __init__(self):
        self.connection_string = os.getenv("AZURE_EVENT_HUB_CONNECTION_STRING")
        self.event_hub_name = os.getenv("AZURE_EVENT_HUB_NAME")
        self.interval = int(os.getenv("SIMULATOR_INTERVAL_SECONDS", 2))
        self.num_devices = int(os.getenv("NUMBER_OF_DEVICES", 50))

        if not self.connection_string:
            raise ValueError("AZURE_EVENT_HUB_CONNECTION_STRING not set in .env file")

        self.simulator = NetworkSimulator(num_devices=self.num_devices)
        print(f"\n🚀 Producer ready. Streaming every {self.interval} seconds.\n")

    async def stream(self, fault_after_seconds: int = 30):
        print("📡 Starting telemetry stream...")
        print(f"   Fault will be injected after {fault_after_seconds} seconds\n")

        start_time = asyncio.get_event_loop().time()
        fault_injected = False
        batch_count = 0

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > fault_after_seconds and not fault_injected:
                print("\n💥 INJECTING FAULT for demo...\n")
                self.simulator.inject_fault(num_devices=3)
                fault_injected = True

            telemetry_batch = self.simulator.generate_batch_telemetry()
            anomalies = [t for t in telemetry_batch if t["status"] == "critical"]

            try:
                producer = EventHubProducerClient.from_connection_string(
                    conn_str=self.connection_string,
                    eventhub_name=self.event_hub_name
                )
                async with producer:
                    event_data_batch = await producer.create_batch()
                    for telemetry in telemetry_batch:
                        event_data_batch.add(EventData(json.dumps(telemetry)))
                    await producer.send_batch(event_data_batch)

                batch_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S")
                status = "🔴 FAULT ACTIVE" if fault_injected else "✅ Normal"
                print(
                    f"[{timestamp}] Batch #{batch_count:04d} | "
                    f"Events: {len(telemetry_batch):3d} | "
                    f"Anomalies: {len(anomalies):2d} | "
                    f"{status}"
                )

            except Exception as e:
                print(f"❌ Error sending to Event Hubs: {e}")

            await asyncio.sleep(self.interval)


if __name__ == "__main__":
    producer = TelemetryProducer()
    asyncio.run(producer.stream(fault_after_seconds=30))