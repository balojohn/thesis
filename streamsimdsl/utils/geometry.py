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
    For top-level nodes: update directly in poses dict.
    For nested children: let recurse() handle them via parent composite updates.
    """
    node_class = node.get("class", "").lower()
    node_type = node.get("type", "").lower() or None
    node_subtype = node.get("subtype", "").lower() or None
    node_name = node.get("name", "").lower()
    node_pose = {"x": node["x"], "y": node["y"], "theta": node["theta"]}

    # Leaf node (sensor, actuator, actor)
    if node_class in ["sensor", "actuator", "actor"]:
        category = node_class + "s"
        
        # Try to update at top-level first
        try:
            if node_type:
                if node_subtype and node_subtype != node_type:
                    poses[category][node_type][node_subtype][node_name].update(node_pose)
                else:
                    poses[category][node_type][node_name].update(node_pose)
                log.debug(f"Updated leaf {node_class} {node_name} (top-level)")
            else:
                poses[category][node_name].update(node_pose)
                log.debug(f"Updated leaf {node_class} {node_name} (top-level)")
            return
        except (KeyError, TypeError):
            # Not found at top-level - search in nested composites
            def find_and_update(struct):
                if not isinstance(struct, dict):
                    return False
                
                # Search in composites
                for comp_type, comp_group in struct.get("composites", {}).items():
                    if isinstance(comp_group, dict):
                        for comp_name, comp_entry in comp_group.items():
                            if isinstance(comp_entry, dict):
                                # Look for sensors/actuators in this composite
                                for cat in ["sensors", "actuators", "actors"]:
                                    cat_dict = comp_entry.get(cat, {})
                                    if isinstance(cat_dict, dict):
                                        # Try type -> subtype -> name
                                        if node_type and node_type in cat_dict:
                                            tdict = cat_dict[node_type]
                                            if isinstance(tdict, dict):
                                                if node_subtype and node_subtype in tdict:
                                                    sdict = tdict[node_subtype]
                                                    if node_name in sdict:
                                                        # sdict[node_name].update(node_pose)
                                                        return True
                                                if node_name in tdict:
                                                    # tdict[node_name].update(node_pose)
                                                    return True
                                # Recurse into nested composites
                                if find_and_update(comp_entry):
                                    return True
                return False
            
            if find_and_update(poses):
                log.debug(f"Updated nested {node_class} {node_name}")
            else:
                log.debug(f"Could not find {node_class} {node_name}")
            return

    # Composite nodes
    if node_class == "composite":
        ctype = node_type or node_name
        found_entry = None

        # Search for existing composite
        def search_composite(struct):
            nonlocal found_entry
            if not isinstance(struct, dict) or found_entry is not None:
                return
            comps = struct.get("composites", {})
            for t, group in comps.items():
                for n, entry in group.items():
                    if t == ctype and n == node_name:
                        found_entry = entry
                        return
                    search_composite(entry)

        for t, group in poses.get("composites", {}).items():
            for n, entry in group.items():
                if t == ctype and n == node_name:
                    found_entry = entry
                    break
                search_composite(entry)
            if found_entry:
                break

        if found_entry is None:
            poses.setdefault("composites", {}).setdefault(ctype, {})
            found_entry = poses["composites"][ctype].setdefault(node_name, {})

        entry = found_entry

        # Preserve children
        prev_sensors = entry.get("sensors", {})
        prev_actuators = entry.get("actuators", {})
        prev_composites = entry.get("composites", {})

        # Update composite's absolute pose
        entry["x"] = float(node_pose["x"])
        entry["y"] = float(node_pose["y"])
        entry["theta"] = float(node_pose["theta"])

        # Restore children
        entry["sensors"] = prev_sensors
        entry["actuators"] = prev_actuators
        entry["composites"] = prev_composites

        log.debug(f"Updated composite {ctype}/{node_name}")

        # Recursively update all children using their stored rel_pose
        for entity in ("actuators", "sensors", "composites"):
            entity_data = entry.get(entity, {})
            if isinstance(entity_data, dict):
                recurse(entity_data, node_pose, log)

        log.debug(f"[Composite] Recursed into children of {node_name}")


def recurse(d, parent_pose, log):
    """
    Recursively update children using stored relative poses.
    Transforms rel_pose to abs_pose for all nested children.
    """
    if not isinstance(d, dict):
        return

    for k, v in d.items():
        if k in ("shape", "properties", "rel_pose"):
            continue
        if not isinstance(v, dict):
            continue

        # Case 1: this node has a relative pose - compute absolute
        if "rel_pose" in v and isinstance(v["rel_pose"], dict):
            rel_pose = v["rel_pose"]
            abs_pose = apply_transformation(parent_pose, rel_pose)
            v["x"] = abs_pose["x"]
            v["y"] = abs_pose["y"]
            v["theta"] = abs_pose["theta"]

            node_name = v.get('name', k)
            log.debug(f"[PoseUpdate] {node_name}: abs_x={abs_pose['x']}, abs_y={abs_pose['y']}, abs_theta={abs_pose['theta']}")

            # This abs_pose becomes the new parent for its children
            next_pose = abs_pose
        else:
            # No rel_pose - intermediate dict (type/subtype layer)
            # Keep using same parent_pose for traversal
            next_pose = parent_pose

        # Case 2: Always recurse into sub-dicts
        # for subk, subv in v.items():
        #     if isinstance(subv, dict):
        recurse(v, next_pose, log)

def get_shape_world_points(pose, shape):
    """Return world-space polygon matching the visualized geometry exactly."""
    if not isinstance(shape, dict):
        return []

    x, y = pose.get("x", 0.0), pose.get("y", 0.0)
    th = math.radians(pose.get("theta", 0.0))
    cos_t, sin_t = math.cos(th), math.sin(th)

    stype = shape.get("type", "").lower()

    # ---- LOCAL GEOMETRY EXACTLY AS VISUALIZER EXPECTS ----

    if stype == "rectangle":
        w = shape.get("width", 1.0)
        l = shape.get("length", 1.0)
        hw, hl = w / 2.0, l / 2.0
        # same orientation as draw_entity()
        local = [(-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)]

    elif stype == "square":
        s = shape.get("length", 1.0) / 2.0
        local = [(-s, -s), (s, -s), (s, s), (-s, s)]

    elif stype == "circle":
        r = shape.get("radius", 1.0)
        # Approximate with 16 points instead of 8
        local = [(r * math.cos(a), r * math.sin(a))
                 for a in [i * 2*math.pi/16 for i in range(16)]]

    elif stype == "arbitraryshape":
        local = [(p["x"], p["y"]) for p in shape.get("points", [])]

    else:
        return []

    # ---- APPLY WORLD TRANSFORM ONCE ----

    world = []
    for lx, ly in local:
        wx = x + (lx * cos_t - ly * sin_t)
        wy = y + (lx * sin_t + ly * cos_t)
        world.append((wx, wy))

    return world
