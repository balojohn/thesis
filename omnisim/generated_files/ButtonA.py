from commlib.msg import MessageHeader, PubSubMessage
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate

class SonarRangeMessage(PubSubMessage):
    pubFreq: float
    hfov: float
    vfov: float
    minRange: float
    maxRange: float

class ButtonANode(Node):
    def __init__(self, *args, **kwargs):
        self.pub_freq = 
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="buttona",
            connection_params=conn_params,
            *args, **kwargs
        )

        self.pub = self.create_publisher(
            'sensor.sonar',
            SonarRangeMessage,
        )

    def start(self):
        self.run()
        self.pub.publish(SonarRangeMessage(
            pubFreq=,
            hfov=,
            vfov=,
            minRange=,
            maxRange=,
        ))
        rate = Rate(self.pub_freq)
        while True:
            rate.sleep()

if __name__ == '__main__':
    try:
        node = ButtonANode()

        node.start()
    except KeyboardInterrupt:
        print(f"\n[ButtonA] Stopped by user.")
        node.stop()