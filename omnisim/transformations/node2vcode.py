import jinja2

from ..utils.utils import TEMPLATES_PATH
from ..lang import build_model
from omnisim.utils.utils import apply_transformation

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    trim_blocks=True,
    lstrip_blocks=True
)
jinja_env.globals["apply_transformation"] = apply_transformation


# ---------- Things / Actors ----------
node_tpl = jinja_env.get_template('node.tpl')
def build_node(obj, comms, dtypes) -> str:
    # Skip data model requirement for composites (like Robot)
    if getattr(obj, "__class__", None).__name__ == "CompositeThing":
        data_model = None
    else:
        data_model_name = f"{getattr(obj, 'subtype', getattr(obj, 'type', obj.__class__.__name__))}Data"
        data_model = next((t for t in dtypes.types if t.name == data_model_name), None)
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