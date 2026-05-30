"""
Kafka Producer
--------------
Streams network telemetry to Apache Kafka in real time.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator.network_simulator import NetworkSimulator

load_dotenv()


class TelemetryProducer:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.topic = os.getenv("KAFKA_TOPIC", "network-telemetry")
        self.interval = int(os.getenv("SIMULATOR_INTERVAL_SECONDS", 2))
        self.num_devices = int(os.getenv("NUMBER_OF_DEVICES", 50))

        self.simulator = NetworkSimulator(num_devices=self.num_devices)
        
        # Check if kafka libraries are installed, otherwise use mock publisher
        self.producer = None
        try:
            from kafka import KafkaProducer
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            print(f"🔌 Connected to Apache Kafka at {self.bootstrap_servers}")
        except ImportError:
            try:
                from confluent_kafka import Producer
                self.producer = Producer({'bootstrap.servers': self.bootstrap_servers})
                print(f"🔌 Connected to Confluent Kafka at {self.bootstrap_servers}")
            except ImportError:
                print("⚠️  No Kafka libraries installed (kafka-python/confluent-kafka). Using local logging fallback.")

        print(f"🚀 Producer ready. Streaming to topic '{self.topic}' every {self.interval} seconds.\n")

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
                if self.producer:
                    # Send to real Kafka
                    if hasattr(self.producer, 'send'): # kafka-python
                        for telemetry in telemetry_batch:
                            self.producer.send(self.topic, value=telemetry)
                        self.producer.flush()
                    else: # confluent-kafka
                        for telemetry in telemetry_batch:
                            self.producer.produce(self.topic, value=json.dumps(telemetry).encode('utf-8'))
                        self.producer.flush()
                else:
                    # Mock publisher print
                    pass

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
                print(f"❌ Error sending to Kafka: {e}")

            await asyncio.sleep(self.interval)


if __name__ == "__main__":
    producer = TelemetryProducer()
    try:
        asyncio.run(producer.stream(fault_after_seconds=30))
    except KeyboardInterrupt:
        print("\n👋 Telemetry streaming stopped.")
