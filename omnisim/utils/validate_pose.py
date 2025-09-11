import math

def rotate_point(x, y, cx, cy, angle_deg):
    angle_rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    dx, dy = x - cx, y - cy
    return cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a

def get_bbox(shape, pose):
    cx, cy = pose.x, pose.y
    theta = getattr(pose, "theta", 0)

    points = []
    cls = shape.__class__.__name__

    if cls == 'Circle' or cls == 'Cylinder':
        r = shape.radius
        raw_points = [(cx-r, cy), (cx+r, cy), (cx, cy-r), (cx, cy+r)]
        points = [rotate_point(x, y, cx, cy, theta) for x, y in raw_points]

    elif cls == 'Square':
        l = shape.length
        half = l / 2
        raw_points = [
            (cx-half, cy-half), (cx+half, cy-half),
            (cx+half, cy+half), (cx-half, cy+half)
        ]
        points = [rotate_point(x, y, cx, cy, theta) for x, y in raw_points]

    elif cls == 'Rectangle':
        hw, hh = shape.width/2, shape.length/2
        raw_points = [
            (cx-hw, cy-hh), (cx+hw, cy-hh),
            (cx+hw, cy+hh), (cx-hw, cy+hh)
        ]
        points = [rotate_point(x, y, cx, cy, theta) for x, y in raw_points]

    elif cls == 'ArbitraryShape':
        raw_points = [(cx+p.x, cy+p.y) for p in shape.points]
        points = [rotate_point(x, y, cx, cy, theta) for x, y in raw_points]

    elif cls == 'ComplexShape':
        for subshape in shape.shapes:
            sub_points = get_bbox(subshape, pose)
            points.extend([(sub_points[0], sub_points[1]),
                           (sub_points[2], sub_points[3])])
    else:
        raise NotImplementedError(f"BBox not implemented for {cls}")

    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return (min(xs), min(ys), max(xs), max(ys))

def is_within_bounds(pose, shape, env_width, env_height):
    min_x, min_y, max_x, max_y = get_bbox(shape, pose)
    return (0 <= min_x <= env_width and
            0 <= max_x <= env_width and
            0 <= min_y <= env_height and
            0 <= max_y <= env_height)

def validate_entity_poses(entities, env_width, env_height, entity_type="Entity", logger=None):
    results = []
    for placement in entities:
        pose, shape, name = placement.pose, placement.ref.shape, placement.ref.name
        try:
            inside = is_within_bounds(pose, shape, env_width, env_height)
        except NotImplementedError as e:
            msg = f"[?] {entity_type} '{name}' shape check skipped: {e}"
            (logger.warning if logger else print)(msg)
            continue

        tag = f"{entity_type} '{name}' at ({pose.theta}, {pose.theta})"
        if inside:
            msg = f"[✓] {tag} is within bounds."
            (logger.info if logger else print)(msg)
        else:
            msg = f"[X] {tag} is OUTSIDE bounds ({env_width}x{env_height})"
            (logger.error if logger else print)(msg)
        results.append((name, inside))
    return results
