import jinja2

from ..utils import TEMPLATES_PATH
from ..lang import build_model

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    trim_blocks=True,
    lstrip_blocks=True
)

vnode_tpl = jinja_env.get_template('vnode.tpl')


def build_vnode(obj, comms, dtypes) -> str:
    data_model_name = obj.dataModel.name  # e.g., "RangeData"
    data_model = next((t for t in dtypes.types if t.name == data_model_name), None)
    if data_model is None:
        raise ValueError(f"Data model '{data_model_name}' not found in dtypes.")
    context = {
        'thing': obj if obj.__class__.__name__.lower() != "thing" else None,
        'actor': obj if obj.__class__.__name__.lower() == "actor" else None,
        'comms': comms,
        'dtype': dtypes,
        'dataModel': data_model,
    }
    modelf = vnode_tpl.render(context)
    return modelf


def model_to_vcode(obj, comms, dtypes) -> str:
    vnode_str = build_vnode(obj, comms, dtypes)
    return vnode_str