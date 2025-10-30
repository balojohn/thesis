import math
import numpy as np
from commlib.msg import PubSubMessage

class PoseMessage(PubSubMessage):
    """2D pose message."""
    x: float
    y: float
    theta: float

class VelocityMessage(PubSubMessage):
    vel_lin: float
    vel_ang: float

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

def shape_to_dict(shape):
    if shape is None:
        return None
    if isinstance(shape, dict):
        return shape
    sdict = {"type": shape.__class__.__name__}
    for attr in ("width", "length", "height", "size", "radius"):
        if hasattr(shape, attr):
            sdict[attr] = getattr(shape, attr)
    return sdict

# def find_center(shape):
#     if not shape:
#         return (0.0, 0.0)
#     stype = shape.get("type", "").lower()
#     if stype == "rectangle":
#         w = shape.get("width", 0.0)
#         l = shape.get("length", shape.get("height", 0.0))
#         return w / 2.0, l / 2.0
#     elif stype == "square":
#         s = shape.get("size", shape.get("length", 0.0))
#         return s / 2.0, s / 2.0
#     elif stype == "circle":
#         r = shape.get("radius", 0.0)
#         return r, r
#     return (0.0, 0.0)

# Homogeneous 2D transformation matrix
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
def apply_transformation(parent_pose, rel_pose, parent_shape=None, child_shape=None):
    """
    Compose absolute pose = parent_pose ⊕ rel_pose.
    Proper 2D homogeneous composition (local offsets, single rotation).
    """
    parent_shape = shape_to_dict(parent_shape)
    child_shape = shape_to_dict(child_shape)

    # p_halfx, p_halfy = find_center(parent_shape)
    # c_halfx, c_halfy = find_center(child_shape)

    # Build tf matrices
    Tp = make_tf_matrix(parent_pose["x"], parent_pose["y"], parent_pose["theta"])
    Tr_rel = make_tf_matrix(rel_pose["x"], rel_pose["y"], rel_pose["theta"])

    # Compose in local frame: Parent → Offset → Relative
    T_abs = Tp @ Tr_rel # @ T_offset

    # Extract pose
    x, y = float(T_abs[0, 2]), float(T_abs[1, 2])
    sin_theta, cos_theta = T_abs[1, 0], T_abs[0, 0]
    theta = math.degrees(math.atan2(sin_theta, cos_theta))

    # Normalize
    if theta >= 180.0:
        theta -= 360.0
    if theta < -180.0:
        theta += 360.0

    return {"x": x, "y": y, "theta": theta}

def node_pose_callback(nodes, poses, log, node: dict, parent_pose=None):
    """
    Update or register a node's absolute pose into the correct hierarchy slot.
    Handles both top-level nodes and nested children within composites.
    """
    node_class = node.get("class", "").lower()
    node_type = node.get("type", "").lower() or None
    node_subtype = node.get("subtype", "").lower() or None
    node_name = node.get("name", "").lower()
    node_pose = {"x": node["x"], "y": node["y"], "theta": node["theta"]}

    # If this is a leaf node (sensor/actuator/actor) with a parent, 
    # compute absolute pose from relative
    if parent_pose is not None:
        if node_class in ["sensor", "actuator", "actor"]:
            node_pose = apply_transformation(parent_pose, node_pose)
    
    # For leaf nodes (sensor, actuator, actor): store in parent's nested structure
    if node_class in ["sensor", "actuator", "actor"]:
        # Don't store in top-level categories—only recurse will update leaf nodes
        # The poses dict structure is already set up by HomeNode with rel_pose
        # Just update the x, y, theta if the entry exists
        category = f"{node_class}s"
        
        # Try to find and update in top-level (for standalone sensors/actuators)
        try:
            if node_type:
                if node_subtype and node_subtype != node_type:
                    poses[category][node_type][node_subtype][node_name].update(node_pose)
                else:
                    poses[category][node_type][node_name].update(node_pose)
            else:
                poses[category][node_name].update(node_pose)
            log.debug(f"Updated leaf {node_class} {node_name} -> {node_pose}")
        except (KeyError, TypeError):
            # If not found in top-level, it's probably nested in a composite
            # The parent's recurse() call will handle updating it
            pass
    
    # For composites: register/update and recurse into children
    elif node_class == "composite":
        ctype = node_type or node_name
        found_entry = None

        # Search recursively for existing composite
        def search_composite(node_dict):
            nonlocal found_entry
            if not isinstance(node_dict, dict) or found_entry is not None:
                return
            comps = node_dict.get("composites", {})
            for t, comps_of_type in comps.items():
                for n, entry in comps_of_type.items():
                    if t == ctype and n == node_name:
                        found_entry = entry
                        return
                    search_composite(entry)

        # Start recursive search from top-level composites
        for t, comps_of_type in poses.get("composites", {}).items():
            for n, entry in comps_of_type.items():
                if t == ctype and n == node_name:
                    found_entry = entry
                    break
                search_composite(entry)
            if found_entry:
                break

        # If not found, create at top-level
        if found_entry is None:
            poses.setdefault("composites", {}).setdefault(ctype, {})
            found_entry = poses["composites"][ctype].setdefault(node_name, {})

        entry = found_entry

        # Preserve children before overwriting
        prev_sensors = entry.get("sensors", {})
        prev_actuators = entry.get("actuators", {})
        prev_composites = entry.get("composites", {})

        # Update composite's absolute pose
        entry["x"] = float(node_pose["x"])
        entry["y"] = float(node_pose["y"])
        entry["theta"] = float(node_pose["theta"])

        # Restore children dicts
        if "sensors" not in entry:
            entry["sensors"] = prev_sensors
        if "actuators" not in entry:
            entry["actuators"] = prev_actuators
        if "composites" not in entry:
            entry["composites"] = prev_composites

        log.debug(f"Updated composite {ctype}/{node_name} -> {node_pose}")

        # Recursively update all children
        for entity in ("actuators", "sensors", "composites"):
            entity_data = entry.get(entity, {})
            if isinstance(entity_data, dict):
                recurse(entity_data, node_pose, log)

        log.info(f"[PoseUpdate] {node_class} {node_name}: {node_pose}")

def recurse(d, parent_pose, log):
    """
    Recursively update children using stored relative poses.
    Modifies children in-place with computed absolute poses.
    """
    for k, v in d.items():
        if not isinstance(v, dict):
            continue

        # Compute or retrieve relative pose
        if "rel_pose" in v:
            rel_pose = v["rel_pose"]
        elif all(c in v for c in ("x", "y", "theta")):
            # Compute rel_pose from stored absolute values
            rel_pose = {
                "x": float(v["x"]) - float(parent_pose["x"]),
                "y": float(v["y"]) - float(parent_pose["y"]),
                "theta": float(v["theta"]) - float(parent_pose["theta"])
            }
            v["rel_pose"] = rel_pose
            log.debug(f"[PoseInit] {k} computed rel_pose: {rel_pose}")
        else:
            rel_pose = {"x": 0.0, "y": 0.0, "theta": 0.0}
            v["rel_pose"] = rel_pose

        # Compute and update absolute pose
        abs_pose = apply_transformation(parent_pose, rel_pose)
        v["x"] = float(abs_pose["x"])
        v["y"] = float(abs_pose["y"])
        v["theta"] = float(abs_pose["theta"])
        log.debug(f"[PoseUpdate] {k}: {abs_pose}")

        # Recurse into nested children
        for subsec in ("actuators", "sensors", "composites"):
            if subsec in v and isinstance(v[subsec], dict):
                recurse(v[subsec], abs_pose, log)

def get_shape_world_points(pose, shape):
    """Return list of world-space (x, y) points for the given pose+shape dict."""
    if not isinstance(shape, dict):
        return []

    x, y, theta = pose.get("x", 0.0), pose.get("y", 0.0), math.radians(pose.get("theta", 0.0))
    stype = shape.get("type", "").lower()

    pts = []
    if stype == "rectangle":
        w, l = shape.get("width", 1.0), shape.get("length", 1.0)
        hw, hl = w / 2.0, l / 2.0
        local = [(-hl, -hw), (-hl, hw), (hl, hw), (hl, -hw)]
    elif stype == "square":
        length = shape.get("length", 1.0)
        h = length / 2.0
        local = [(-h, -h), (-h, h), (h, h), (h, -h)]
    elif stype == "circle":
        r = shape.get("radius", 1.0)
        # approximate as octagon for intersection test
        local = [
            (r * math.cos(a), r * math.sin(a))
            for a in [i * math.pi / 4 for i in range(8)]
        ]
    elif stype == "arbitraryshape":
        local = [(p["x"], p["y"]) for p in shape.get("points", [])]
    else:
        return []

    for lx, ly in local:
        wx = x + lx * math.cos(theta) - ly * math.sin(theta)
        wy = y + lx * math.sin(theta) + ly * math.cos(theta)
        pts.append((wx, wy))
    return pts
