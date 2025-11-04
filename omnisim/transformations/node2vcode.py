import jinja2

from ..utils.utils import TEMPLATES_PATH
from ..lang import build_model
from omnisim.utils.geometry import apply_transformation

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    trim_blocks=True,
    lstrip_blocks=True
)
jinja_env.globals["apply_transformation"] = apply_transformation

# Helper
def get_parents(obj, level=0):
    """
    Recursively attach .parent references for all nested components.
    Works for composites, sensors, actuators, and actors.
    Prints hierarchy with accurate indentation.
    """
    # === Handle Sensors ===
    if getattr(obj, "sensors", None):
        for s in obj.sensors:
            s.ref.parent = obj
            ref_name = getattr(s.ref, "name", "unnamed")
            # print(f"{indent}  ├─ Sensor child: {ref_name} ← parent={obj_name}")
            get_parents(s.ref, level + 1)

    # === Handle Actuators ===
    if getattr(obj, "actuators", None):
        for a in obj.actuators:
            a.ref.parent = obj
            ref_name = getattr(a.ref, "name", "unnamed")
            # print(f"{indent}  ├─ Actuator child: {ref_name} ← parent={obj_name}")
            get_parents(a.ref, level + 1)

    # === Handle Composites ===
    if getattr(obj, "composites", None):
        for c in obj.composites:
            c.ref.parent = obj
            ref_name = getattr(c.ref, "name", "unnamed")
            # print(f"{indent}  ├─ Composite child: {ref_name} ← parent={obj_name}")
            # Deeper indentation for nested composites
            get_parents(c.ref, level + 1)

    # === Handle Actors ===
    if getattr(obj, "actors", None):
        for act in obj.actors:
            act.ref.parent = obj
            ref_name = getattr(act.ref, "name", "unnamed")
            # print(f"{indent}  ├─ Actor child: {ref_name} ← parent={obj_name}")
            get_parents(act.ref, level + 1)

    # === Confirm parent link ===
    if hasattr(obj, "parent") and obj.parent:
        parent_name = getattr(obj.parent, "name", getattr(obj.parent, "type", "ROOT"))
        # print(f"{indent}    ↳ Confirmed parent of {obj_name}: {parent_name}")


# ---------- Things / Actors ----------
node_tpl = jinja_env.get_template('node.tpl')
def build_node(obj, comms, dtypes) -> str:
    # Attach parent links recursively before rendering
    print(f"\n[build_node] Linking parents for: {getattr(obj, 'name', obj.type)}")
    get_parents(obj)

    if getattr(obj, "__class__", None).__name__ == "CompositeThing":
        data_model = None
    else:
        name_part = (
            getattr(obj, "subtype", None)
            if getattr(obj, "subtype", None)
            else getattr(obj, "type", None)
            or obj.__class__.__name__
        )
        data_model_name = f"{name_part}Data"
        data_model = next(
            (t for t in dtypes.types if t.name.lower() == data_model_name.lower()),
            None
        )
        if data_model is None:
            raise ValueError(f"Data model '{data_model_name}' not found in dtypes.")

    context = {
        'obj': obj,
        'comms': comms,
        'dtype': dtypes,
    }
    modelf = node_tpl.render(context)
    return modelf

def model_to_vcode(obj, comms, dtypes) -> str:
    return build_node(obj, comms, dtypes)

# # ---------- Composites (Robots & others) ----------
# composite_tpl = jinja_env.get_template("composites.tpl")
# def build_composite(composite, comms, dtypes):
#     context = {
#         "composite": composite,
#         "comms": comms,
#         "dtype": dtypes
#     }
#     return composite_tpl.render(context)
# 
# def composite_to_vcode(robot, comms, dtypes) -> str:
#     composite_str = build_composite(robot, comms, dtypes)
#     return composite_str

# ---------- Environment ----------
envnode_tpl = jinja_env.get_template("environment.tpl")
def build_envnode(env, comms, dtypes) -> str:
    """
    Generate code for an Environment using environment_node.tpl
    environment: parsed Environment instance (has .name, .things, .actors, ...)
    comms: parsed communications model
    dtypes: parsed datatypes model
    """
    placements = []
    if getattr(env, "things", None):
        placements.extend(env.things)
    if getattr(env, "actors", None):
        placements.extend(env.actors)
    
    offsets = {}
    for p in placements:
        if hasattr(p, "transformation") and p.transformation is not None:
            offsets[p.ref.name] = {
                "dx": p.transformation.x,
                "dy": p.transformation.y,
                "dtheta": p.transformation.theta,
            }
        else:
            offsets[p.ref.name] = {"dx": 0.0, "dy": 0.0, "dtheta": 0.0}
    context = {
        "environment": env,
        "comms": comms,
        "dtype": dtypes,
        "placements": placements,
        "offsets": offsets
    }
    envf = envnode_tpl.render(context)
    return envf

def env_to_vcode(env, comms, dtypes) -> str:
    return build_envnode(env, comms, dtypes)