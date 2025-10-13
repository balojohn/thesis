from os.path import dirname, join
import math
import random
import numpy as np

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

# 1. Build a homogeneous 2D transformation matrix
def make_tf_matrix(x, y, theta):
    """Return a 3x3 homogeneous transformation matrix for pose (x, y, theta)."""
    th = math.radians(theta)
    c, s = math.cos(th), math.sin(th)
    return np.array([
        [c, -s, x],
        [s,  c, y],
        [0,  0, 1]
    ], dtype=float)

# 2. Apply a transformation to a pose dict ---
def apply_transformation(parent_pose, rel_pose):
    """Compose parent and relative pose into absolute coordinates."""
    Tp = make_tf_matrix(parent_pose["x"], parent_pose["y"], parent_pose["theta"])
    Tr = make_tf_matrix(rel_pose["x"], rel_pose["y"], rel_pose["theta"])
    T_abs = Tp @ Tr
    x, y = T_abs[0, 2], T_abs[1, 2]
    theta = math.degrees(math.atan2(T_abs[1, 0], T_abs[0, 0]))
    return {"x": x, "y": y, "theta": theta}

def node_pose_callback(nodes, poses, log, node: dict, parent_pose=None):
    """
    Update or register a node's absolute pose into the correct hierarchy slot.
    Works with hierarchical 'nodes' and 'poses' structures (same traversal style as print_tf_tree).
    """
    node_class = node.get("class", "").lower()
    node_type = node.get("type", "").lower() or None
    node_subtype = node.get("subtype", "").lower() or None
    node_name = node.get("name", "").lower()
    node_pose = {"x": node["x"], "y": node["y"], "theta": node["theta"]}

    # Compose with parent transformation if provided
    if parent_pose is not None:
        node_pose = apply_transformation(parent_pose, node_pose)

    # --- SENSORS / ACTUATORS / ACTORS ---
    if node_class in ["sensor", "actuator", "actor"]:
        category = f"{node_class}s"
        poses.setdefault(category, {})

        if node_type:
            poses[category].setdefault(node_type, {})
            if node_subtype and node_subtype != node_type:
                poses[category][node_type].setdefault(node_subtype, {})
                poses[category][node_type][node_subtype][node_name] = node_pose
                log.debug(f"Updated {node_class} {node_type}/{node_subtype}/{node_name} -> {node_pose}")
            else:
                poses[category][node_type][node_name] = node_pose
                log.debug(f"Updated {node_class} {node_type}/{node_name} -> {node_pose}")
        else:
            poses[category][node_name] = node_pose
            log.debug(f"Updated {node_class} {node_name} -> {node_pose}")

    # --- COMPOSITES ---
    elif node_class == "composite":
        ctype = node_type or node_name
        poses.setdefault("composites", {}).setdefault(ctype, {})
        entry = poses["composites"][ctype].setdefault(node_name, {})

        # update this composite's own absolute pose
        entry.update({
            "x": float(node_pose["x"]),
            "y": float(node_pose["y"]),
            "theta": float(node_pose["theta"])
        })
        entry.setdefault("sensors", {})
        entry.setdefault("actuators", {})
        entry.setdefault("composites", {})

        log.debug(f"Updated composite {ctype}/{node_name} -> {node_pose}")

        # Find and update the corresponding entry in poses
        pose_entry = poses["composites"].get(ctype, {}).get(node_name)
        if pose_entry and isinstance(pose_entry, dict):
            update_nested_children(pose_entry, node_pose, log)
        else:
            log.warning(f"No matching pose entry for composite {node_name} found in poses")

    elif node_class == "obstacle":
        poses.setdefault("obstacles", {}).setdefault(node_name, node_pose)
        log.debug(f"Updated obstacle {node_name} -> {node_pose}")

    else:
        log.warning(f"Unknown node class '{node_class}' for {node_name}")

    log.info(f"[PoseUpdate] {node_class} {node_name}: {node_pose}")


def update_nested_children(pose_entry, parent_pose, log):
    """
    Recursively update all children of a composite, including nested sensors and actuators.
    Works even for multi-level structures like reader→camera→cam_1.
    """
    if not isinstance(pose_entry, dict):
        return

    for section in ("actuators", "sensors", "composites"):
        section_data = pose_entry.get(section, {})
        if not isinstance(section_data, dict):
            continue

        def recurse(d, parent_pose):
            for k, v in d.items():
                if not isinstance(v, dict):
                    continue

                # Case 1: Pose dict
                if all(c in v for c in ("x", "y", "theta")):
                    rel_pose = {
                        "x": float(v["x"]),
                        "y": float(v["y"]),
                        "theta": float(v["theta"])
                    }
                    abs_pose = apply_transformation(parent_pose, rel_pose)
                    v.update(abs_pose)
                    log.info(f"[PoseUpdate] child {k}: {abs_pose}")

                    # Dive deeper if this node hosts children
                    for subsec in ("actuators", "sensors", "composites"):
                        if subsec in v:
                            recurse(v[subsec], abs_pose)
                else:
                    # Not a pose dict → continue exploring deeper
                    recurse(v, parent_pose)

        recurse(section_data, parent_pose)
