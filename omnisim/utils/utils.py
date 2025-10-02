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

def check_lines_orientation(p, q, r):
    """
    Determines the orientation of the triplet (p, q, r).

    Parameters:
    p (tuple): The first point as a tuple (x, y).
    q (tuple): The second point as a tuple (x, y).
    r (tuple): The third point as a tuple (x, y).

    Returns:
    int: Returns 1 if the orientation is clockwise, 
            2 if the orientation is counterclockwise, 
            and 0 if the points are collinear.
    """
    val = (float(q[1] - p[1]) * (r[0] - q[0])) - \
        (float(q[0] - p[0]) * (r[1] - q[1]))
    if val > 0:
        # Clockwise orientation
        return 1
    if val < 0:
        # Counterclockwise orientation
        return 2
    # Colinear orientation
    return 0

def check_lines_on_segment(p, q, r):
    """
    Check if point q lies on the line segment defined by points p and r.

    Args:
        p (tuple): A tuple representing the coordinates of the first endpoint of the segment 
            (x1, y1).
        q (tuple): A tuple representing the coordinates of the point to check (x2, y2).
        r (tuple): A tuple representing the coordinates of the second endpoint of the segment 
            (x3, y3).

    Returns:
        bool: True if point q lies on the line segment defined by points p and r, 
            False otherwise.
    """
    if ( (q[0] <= max(p[0], r[0])) and (q[0] >= min(p[0], r[0])) and
            (q[1] <= max(p[1], r[1])) and (q[1] >= min(p[1], r[1]))):
        return True
    return False


def check_lines_intersection(p1, q1, p2, q2):
    """
    Check if two lines (or segments) intersect.

    This function determines if the line segment 'p1q1' and 'p2q2' intersect.
    It uses the orientation method to check for general and special cases of intersection.

    Parameters:
    p1 (tuple): The first point of the first line segment.
    q1 (tuple): The second point of the first line segment.
    p2 (tuple): The first point of the second line segment.
    q2 (tuple): The second point of the second line segment.

    Returns:
    bool: True if the line segments intersect, False otherwise.
    """
    # Find the 4 orientations required for
    # the general and special cases
    o1 = check_lines_orientation(p1, q1, p2)
    o2 = check_lines_orientation(p1, q1, q2)
    o3 = check_lines_orientation(p2, q2, p1)
    o4 = check_lines_orientation(p2, q2, q1)
    # General case
    if ((o1 != o2) and (o3 != o4)):
        return True
    # Special Cases
    # p1 , q1 and p2 are colinear and p2 lies on segment p1q1
    if ((o1 == 0) and check_lines_on_segment(p1, p2, q1)):
        return True
    # p1 , q1 and q2 are colinear and q2 lies on segment p1q1
    if ((o2 == 0) and check_lines_on_segment(p1, q2, q1)):
        return True
    # p2 , q2 and p1 are colinear and p1 lies on segment p2q2
    if ((o3 == 0) and check_lines_on_segment(p2, p1, q2)):
        return True
    # p2 , q2 and q1 are colinear and q1 lies on segment p2q2
    if ((o4 == 0) and check_lines_on_segment(p2, q1, q2)):
        return True
    # If none of the cases
    return False

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

def node_pose_callback(poses, log, node: dict):
    """
    Callback function to update the absolute pose of a node
    (actor, sensor, actuator, or obstacle).

    Args:
        # category (str): One of "actors", "sensors", "actuators", or "obstacles".
        node (dict): A dictionary containing the node's pose information.
            - 'name' (str): The name of the node.
            - 'x' (float): The x-coordinate of the node's position.
            - 'y' (float): The y-coordinate of the node's position.
            - 'theta' (float): The orientation of the node in radians.
    """
    node_class = node["class"]  # sensor / actuator / actor / composite / obstacle
    node_type = node["type"]    # e.g. envsensor / envdevice / envactor / robot
    node_name = node["name"]    # e.g. temperature / thermostat / fire / robot / chair
    node_id = node["id"]        # instance id, e.g. te_1

    pose_data = {"x": node["x"], "y": node["y"], "theta": node["theta"]}

    if node_class in ["sensor", "actuator", "actor"]:
        poses.setdefault(f"{node_class}s", {}) \
             .setdefault(node_type, {}) \
             .setdefault(node_name, {})[node_id] = pose_data

    elif node_class == "composite":
        poses["composites"][node_id] = pose_data

    elif node_class == "obstacle":
        poses["obstacles"].setdefault(node_name, {})[node_id] = pose_data

    log.info(f"Updated {node_class} {node_id} pose -> {pose_data}")

def composite_pose_callback(tree, poses, pantilts, mount_offsets, log, node: dict):
    comp_name = node["name"]

    # Initialize entry if missing
    if comp_name not in poses["composites"]:
        poses["composites"][comp_name] = {"x": 0.0, "y": 0.0, "theta": 0.0}
    else:
        # Skip if no change
        if (node["x"] == poses["composites"][comp_name]["x"] and
            node["y"] == poses["composites"][comp_name]["y"] and
            node["theta"] == poses["composites"][comp_name]["theta"]):
            return

    # Update composite itself
    poses["composites"][comp_name].update(
        {
            "x": node["x"],
            "y": node["y"],
            "theta": node["theta"]
        }
    )

    base_pose = poses["composites"][comp_name]

    if comp_name not in tree:
        return  # no devices on this composite

    # Update children
    for d in tree[comp_name]:
        # pan-tilts handled separately
        if d in pantilts:
            pan_now = pantilts[d]["pan"]
            update_pan_tilt({"name": d}, pan_now)
            continue

        # category detection
        if d in poses["sensors"]:
            cat = "sensors"
        elif d in poses["actuators"]:
            cat = "actuators"
        elif d in poses["composites"]:
            cat = "composites"
        else:
            continue

        offset = mount_offsets.get(d, {"dx": 0.0, "dy": 0.0, "dtheta": 0.0})
        poses[cat][d]["x"] = base_pose["x"] + offset["dx"]
        poses[cat][d]["y"] = base_pose["y"] + offset["dy"]
        poses[cat][d]["theta"] = base_pose["theta"] + offset["dtheta"]

        log.info(f"Updated {cat[:-1]} {d} pose -> {poses[cat][d]}")


def update_pan_tilt(tree, poses, mount_offsets, log, node: dict, pan: float):
    pt_name = node["name"]

    # Find the host robot (the parent of this pan-tilt in tree)
    robot_name = None
    for parent, children in tree.items():
        if pt_name in children:
            robot_name = parent
            break
    if robot_name is None:
        log.warning(f"No host robot found for pan-tilt {pt_name}")
        return

    base_pose = poses["composites"][robot_name]

    # Pan-tilt absolute orientation = robot theta + its mount offset + pan
    mount_offset = mount_offsets.get(pt_name, {"dx": 0.0, "dy": 0.0, "dtheta": 0.0})
    abs_pt_theta = base_pose["theta"] + mount_offset["dtheta"] + pan

    poses["actuators"][pt_name]["x"] = base_pose["x"] + mount_offset["dx"]
    poses["actuators"][pt_name]["y"] = base_pose["y"] + mount_offset["dy"]
    poses["actuators"][pt_name]["theta"] = abs_pt_theta

    log.info(f"Updated pan-tilt {pt_name}: {poses['actuators'][pt_name]}")

    # Update devices mounted on this pan-tilt
    if pt_name in tree:
        for dev in tree[pt_name]:
            # detect category
            category = None
            for cat in ["sensors", "actuators", "composites"]:
                if dev in poses[cat]:
                    category = cat
                    break
            if category is None:
                continue

            dev_offset = mount_offsets.get(dev, {"dx": 0.0, "dy": 0.0, "dtheta": 0.0})
            poses[category][dev]["x"] = poses["actuators"][pt_name]["x"] + dev_offset["dx"]
            poses[category][dev]["y"] = poses["actuators"][pt_name]["y"] + dev_offset["dy"]
            poses[category][dev]["theta"] = abs_pt_theta + dev_offset["dtheta"]

            log.info(f"Updated {dev} pose -> {poses[category][dev]}")
