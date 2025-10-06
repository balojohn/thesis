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

def node_pose_callback(tree, poses, pantilts, handle_offsets, log, node: dict):
    """
    Callback function to update the absolute pose of a node
    (actor, sensor, actuator, or obstacle).

    Args:
        node (dict): A dictionary containing the node's pose information.
            - 'class' (str): The class of the node (sensor/actuator/actor/composite/obstacle)
            - 'type' (str): The type of the node
            - 'name' (str): The name of the node.
            - 'id' (str): The instance id of the node.
            - 'x' (float): The x-coordinate of the node's position.
            - 'y' (float): The y-coordinate of the node's position.
            - 'theta' (float): The orientation of the node in degrees.
    """
    node_class = node["class"]  # sensor / actuator / actor / composite / obstacle
    node_type = node["type"]    # e.g. envsensor / envdevice / envactor / robot
    node_name = node["name"]    # e.g. temperature / thermostat / fire / robot / chair
    node_id = node["id"]        # instance id, e.g. te_1
    node_pose = {"x": node["x"], "y": node["y"], "theta": node["theta"]}

    if node_class in ["sensor", "actuator", "actor"]:
        poses.setdefault(f"{node_class}s", {}) \
             .setdefault(node_type, {}) \
             .setdefault(node_name, {})[node_id] = node_pose

    elif node_class == "composite":
        # Update only x, y, theta without destroying nested structure
        if node_id in poses["composites"][node_name]:
            # Get the old pose to calculate delta
            old_pose = poses["composites"][node_name][node_id]
            dx = node_pose["x"] - old_pose["x"]
            dy = node_pose["y"] - old_pose["y"]
            dtheta = node_pose["theta"] - old_pose["theta"]
            
            # Update parent pose
            poses["composites"][node_name][node_id]["x"] = node_pose["x"]
            poses["composites"][node_name][node_id]["y"] = node_pose["y"]
            poses["composites"][node_name][node_id]["theta"] = node_pose["theta"]
            
            # Start recursive update with the delta
            update_nested_children(poses["composites"][node_name][node_id], dx, dy, dtheta)
        else:
            poses["composites"][node_name][node_id] = node_pose

    elif node_class == "obstacle":
        poses["obstacles"].setdefault(node_name, {})[node_id] = node_pose

    log.info(f"Updated {node_class} {node_id} pose -> {node_pose}")

# Propagate the delta to children
def update_nested_children(data, delta_x, delta_y, delta_theta):
    """Recursively update children by applying delta from parent movement."""
    # Update actuators
    if "actuators" in data and isinstance(data["actuators"], dict):
        for act_name, act_instances in data["actuators"].items():
            if isinstance(act_instances, dict):
                for act_id, act_data in act_instances.items():
                    if isinstance(act_data, dict) and "x" in act_data:
                        act_data["x"] += delta_x
                        act_data["y"] += delta_y
                        act_data["theta"] += delta_theta
                        # Recursively update children of this actuator
                        update_nested_children(act_data, delta_x, delta_y, delta_theta)
    
    # Update sensors
    if "sensors" in data and isinstance(data["sensors"], dict):
        for sen_name, sen_instances in data["sensors"].items():
            if isinstance(sen_instances, dict):
                for sen_id, sen_data in sen_instances.items():
                    if isinstance(sen_data, dict) and "x" in sen_data:
                        sen_data["x"] += delta_x
                        sen_data["y"] += delta_y
                        sen_data["theta"] += delta_theta
    
    # Update nested composites
    if "composites" in data and isinstance(data["composites"], dict):
        for comp_name, comp_instances in data["composites"].items():
            if isinstance(comp_instances, dict):
                for comp_id, comp_data in comp_instances.items():
                    if isinstance(comp_data, dict) and "x" in comp_data:
                        comp_data["x"] += delta_x
                        comp_data["y"] += delta_y
                        comp_data["theta"] += delta_theta
                        # Recursively update children of nested composite
                        update_nested_children(comp_data, delta_x, delta_y, delta_theta)