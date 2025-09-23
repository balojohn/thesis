from os.path import dirname, join
import math
import random

THIS_DIR = dirname((dirname(__file__)))
MODEL_REPO_PATH = join(THIS_DIR, 'models')
GENFILES_REPO_PATH = join(THIS_DIR, 'generated_files')
TEMPLATES_PATH = join(THIS_DIR, 'templates')

def apply_dispersion(x: float, type_name: str, **params) -> float:
    if type_name == "Constant":
        return x + params.get("value", 0.0)
    elif type_name == "Linear":
        start = params.get("startingPoint", 0.0)
        step = params.get("step", 1.0)
        return start + step * x
    elif type_name == "Quadratic":
        a = params.get("a", 0.0)
        b = params.get("b", 0.0)
        c = params.get("c", 0.0)
        return a * x**2 + b * x + c
    elif type_name == "Exponential":
        base = params.get("base", math.e)
        y_int = params.get("yIntercept", 0.0)
        return y_int + base ** x
    elif type_name == "Logarithmic":
        base = params.get("base", math.e)
        alpha = params.get("alpha", 1.0)
        return alpha * math.log(x + 1, base)
    else:
        raise ValueError(f"Unknown dispersion type: {type_name}")

def calc_distance(p1, p2):
    """
    Calculate the Euclidean distance between two points.

    Args:
        p1 (tuple): The first point as a tuple of (x, y) coordinates.
        p2 (tuple): The second point as a tuple of (x, y) coordinates.

    Returns:
        float: The Euclidean distance between the two points.
    """
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def check_distance(from_pose, to_pose):
        """
        Calculate the distance between a given point and a reference point, and return the distance 
        along with associated properties.

        Args:
            xy (list or tuple): The coordinates (x, y) of the point to check.
            aff (str): The identifier for the reference point.

        Returns:
            dict: A dictionary containing:
                - 'distance' (float): The calculated distance between the given point and the 
                    reference point.
                - 'properties' (dict): The properties associated with the reference point.
        """
        p1 = [from_pose.x, from_pose.y]
        p2 = [to_pose.x, to_pose.y]
        d = calc_distance(p1, p2)
        return {'distance': d}

def node_pose_callback(self, category: str, node: dict):
    """
    Callback function to update the absolute pose of a node
    (actor, sensor, actuator, or obstacle).

    Args:
        category (str): One of "actors", "sensors", "actuators", or "obstacles".
        node (dict): A dictionary containing the node's pose information.
            - 'name' (str): The name of the node.
            - 'x' (float): The x-coordinate of the node's position.
            - 'y' (float): The y-coordinate of the node's position.
            - 'theta' (float): The orientation of the node in radians.
    """
    node_name = node["name"]

    # Initialize if missing
    if node_name not in self.poses[category]:
        self.poses[category][node_name] = {"x": 0.0, "y": 0.0, "theta": 0.0}

    # Update pose
    self.poses[category][node_name]["x"] = node["x"]
    self.poses[category][node_name]["y"] = node["y"]
    self.poses[category][node_name]["theta"] = node["theta"]

    self.log.info(
        "Updated %s %s pose -> %s",
        category[:-1],  # singular form (actor/sensor/actuator/obstacle)
        node_name,
        self.poses[category][node_name],
    )

def composite_pose_callback(self, node: dict):
    """
    Callback function to handle updates to the pose of a composite thing.
    This updates the absolute positions and orientations of the composite
    and all its associated devices (sensors, actuators, nested composites).
    It also handles pan-tilt units inside composites.

    Args:
        node (dict): A dictionary containing the composite's pose info:
            - 'name' (str): The name of the composite.
            - 'x' (float): The x-coordinate of the composite's position.
            - 'y' (float): The y-coordinate of the composite's position.
            - 'theta' (float): The orientation (theta) of the composite.
    """
    comp_name = node["name"]

    # Initialize entry if missing
    if comp_name not in self.poses["composites"]:
        self.poses["composites"][comp_name] = {"x": 0.0, "y": 0.0, "theta": 0.0}
    else:
        # Skip if no change
        if (node["x"] == self.poses["composites"][comp_name]["x"] and
            node["y"] == self.poses["composites"][comp_name]["y"] and
            node["theta"] == self.poses["composites"][comp_name]["theta"]):
            return

    # Update composite pose
    self.poses["composites"][comp_name]["x"] = node["x"]
    self.poses["composites"][comp_name]["y"] = node["y"]
    self.poses["composites"][comp_name]["theta"] = node["theta"]

    if comp_name not in self.tree:
        return # no devices on this composite

    for d in self.tree[comp_name]:
        if d in self.poses["sensors"]:
            cat = "sensors"
        elif d in self.poses["actuators"]:
            cat = "actuators"
        elif d in self.poses["composites"]:
            cat = "composites"
        else:
            continue
        # Update absolute position
        self.poses[cat][d]["x"] = self.poses["composites"][comp_name]["x"]
        self.poses[cat][d]["y"] = self.poses["composites"][comp_name]["y"]

        # Update orientation if not pan-tilt
        offset = self.mount_offsets.get(d, {"dtheta": 0.0})
        if self.poses["composites"][d]["theta"] is not None and d not in self.pantilts:
            self.poses["composites"][d]["theta"] = (
                self.poses["composites"][comp_name]["theta"] +
                offset["dtheta"]
            )

        # Handle pan-tilts
        if d in self.pantilts:
            if d not in self.tree:
                continue  # no devices on this pan-tilt
            pt_devices = self.tree[d]
            for device in pt_devices:
                self.poses["composites"][device]["x"] = self.poses["composites"][comp_name]["x"]
                self.poses["composites"][device]["y"] = self.poses["composites"][comp_name]["y"]
            pan_now = self.pantilts[d]["pan"]
            self.update_pan_tilt(d, pan_now)

def update_pan_tilt(self, node: dict, pan: float):
    """
    Update the pan-tilt mechanism's absolute theta value and notify the UI.
    This uses the robot's pose as the base and applies the pan-tilt's mounting offset
    plus the current pan value. Devices mounted on the pan-tilt inherit the updated pose.

    Args:
        node (dict): A dictionary describing the pan-tilt node:
            - 'name' (str): The name of the pan-tilt mechanism.
        pan (float): The pan value to add to the pan-tilt's mount orientation.
    """
    pt_name = node["name"]

    # Find the host robot (the parent of this pan-tilt in self.tree)
    robot_name = None
    for parent, children in self.tree.items():
        if pt_name in children:
            robot_name = parent
            break
    if robot_name is None:
        self.log.warning(f"No host robot found for pan-tilt {pt_name}")
        return

    base_pose = self.poses["composites"][robot_name]

    # Pan-tilt absolute orientation = robot theta + its mount offset + pan
    mount_offset = self.mount_offsets.get(pt_name, {"dtheta": 0.0})
    abs_pt_theta = base_pose["theta"] + mount_offset["dtheta"] + pan

    self.poses["actuators"][pt_name]["x"] = base_pose["x"] + mount_offset["dx"]
    self.poses["actuators"][pt_name]["y"] = base_pose["y"] + mount_offset["dy"]
    self.poses["actuators"][pt_name]["theta"] = abs_pt_theta
    
    self.log.info(f"Updated pan-tilt {pt_name}: {self.poses['actuators'][pt_name]}")

    # Update devices mounted on this pan-tilt
    if pt_name in self.tree:
        for dev in self.tree[pt_name]:
            # detect category
            category = None
            for cat in ["sensors", "actuators", "composites"]:
                if dev in self.poses[cat]:
                    category = cat
                    break
            if category is None:
                continue
            
            dev_offset = self.mount_offsets.get(dev, {"dx": 0.0, "dy": 0.0, "dtheta": 0.0})
            self.poses["sensors"][dev]["x"] = self.poses["actuators"][pt_name]["x"] + dev_offset["dx"]
            self.poses["sensors"][dev]["y"] = self.poses["actuators"][pt_name]["y"] + dev_offset["dy"]
            self.poses["sensors"][dev]["theta"] = abs_pt_theta + dev_offset["dtheta"]

            self.log.info(f"Updated {dev} pose -> {self.poses[category][dev]}")
