import random
import time
from commlib.msg import PubSubMessage
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters


class TemperatureMessage(PubSubMessage):
    sensor_id: str
    location: str
    temperature: float


class TemperatureSource:
    def __init__(self, sensor_id: str, location: str):
        self.msg = TemperatureMessage(sensor_id=sensor_id, location=location, temperature=0.0)
        self.conn_params = ConnectionParameters()
        self.node = Node(node_name=f"sources.temperature.{sensor_id}",
                         connection_params=self.conn_params)
        self.publisher = self.node.create_publisher(
            msg_type=TemperatureMessage,
            topic=f"sensors.temperature.{sensor_id}"
        )
        self.node.run()

    def generate_temperature(self):
        self.msg.temperature = round(random.uniform(-20.0, 50.0), 2)

    def publish_temperature(self):
        self.generate_temperature()
        print(f"[Source] Publishing temperature: {self.msg.temperature}°C from {self.msg.location}")
        self.publisher.publish(self.msg)


if __name__ == "__main__":
    try:
        source = TemperatureSource(sensor_id="sensor_1", location="Living Room")
        while True:
            source.publish_temperature()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Source] Stopped by user.")
        source.node.stop()
