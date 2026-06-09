import sys

from commlib.node import Node
from commlib.transports.redis import ConnectionParameters
from streamsimdsl.utils.geometry import VelocityMessage

lin = float(sys.argv[1])
ang = float(sys.argv[2])

node = Node(
    node_name="teleop",
    connection_params=ConnectionParameters()
)

pub = node.create_publisher(
    topic="composite.robot.r_1.cmd_vel",
    msg_type=VelocityMessage
)

node.run()

pub.publish(VelocityMessage(
    vel_lin=lin,
    vel_ang=ang
))

node.stop()