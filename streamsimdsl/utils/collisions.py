import math
from streamsimdsl.utils.geometry import (
    get_shape_world_points,
    check_lines_intersection,
)
from streamsimdsl.utils.affections import (
    find_node_by_id,
    find_pose_by_metadata,
)

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def polygon_edges(pts):
    n = len(pts)
    for i in range(n):
        yield pts[i], pts[(i + 1) % n]

def polygons_intersect(poly1, poly2):
    for a, b in polygon_edges(poly1):
        for c, d in polygon_edges(poly2):
            if check_lines_intersection(a, b, c, d):
                return True
    return False

def hits_bounds(poly, w, h):
    for x, y in poly:
        if x < 0 or x > w:
            return True
        if y < 0 or y > h:
            return True
    return False

def collect_collision_entities(nodes, poses):
    """
    Collect ALL entities that have a shape.
    Uses the same metadata resolution as affection logic.
    Ensures pose resolution = consistent with sensor system.
    """
    entities = []

    stack = [nodes]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue

        # It's a node-level dict with metadata
        if "class" in current and "shape" in current:
            cls = current.get("class", "").lower()
            type = current.get("type", "").lower() or None
            subtype = current.get("subtype", "").lower() or None
            name = current.get("name", "").lower()
            props = current.get("properties", {})
            collidable = current.get("collidable",
                            props.get("collidable", False))
            
            # skip non-collidable geometry
            if not collidable:
                continue
            # PHYSICAL OBJECTS ONLY
            if cls in {"composite", "actor", "actuator", "obstacle"}:
                pose = find_pose_by_metadata(poses, cls, type, subtype, name)
                if pose:
                    entities.append({
                        "name": name,
                        "shape": current["shape"],
                        "pose": pose,
                        "collidable": True,
                    })

        # Recurse deeper
        for val in current.values():
            if isinstance(val, dict):
                stack.append(val)

    return entities

def detect_collisions(nodes, poses, env_w, env_h):
    """
    Pose resolution, hierarchy traversal, and shape handling now
    follow EXACTLY the same rules as the affection system.
    """
    entities = collect_collision_entities(nodes, poses)
    world_polys = []

    # Convert shapes+poses to world polygons
    for ent in entities:
        poly = get_shape_world_points(ent["pose"], ent["shape"])
        if not poly:
            continue
        world_polys.append((ent["name"], poly, ent.get("collidable", False)))

    collisions = []

    # Wall collisions
    for name, poly, collidable in world_polys:
        if hits_bounds(poly, env_w, env_h):
            collisions.append((name, "WALL"))

    # Entity–entity
    n = len(world_polys)
    for i in range(n):
        name_i, poly_i, coll_i = world_polys[i]
        for j in range(i + 1, n):
            name_j, poly_j, coll_j = world_polys[j]
            if not coll_i or not coll_j:
                continue
            if polygons_intersect(poly_i, poly_j):
                collisions.append((name_i, name_j))

    return collisions
