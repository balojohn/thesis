from commlib.msg import MessageHeader, PubSubMessage
from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from commlib.utils import Rate


class SonarNode(Node):
    def __init__(self, *args, **kwargs):
        self.pub_freq = 30.0
        conn_params = ConnectionParameters()

        super().__init__(
            node_name="sonar",
            connection_params=conn_params,
            *args, **kwargs
        )


    def start(self):
        self.run()
        rate = Rate(self.pub_freq)
        while True:
            rate.sleep()

if __name__ == '__main__':
    try:
        node = SonarNode()

        node.start()
    except KeyboardInterrupt:
        print(f"\n[Sonar] Stopped by user.")
        node.stop()