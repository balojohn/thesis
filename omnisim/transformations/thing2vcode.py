import jinja2

from ..utils import TEMPLATES_PATH
from ..lang import build_model

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    trim_blocks=True,
    lstrip_blocks=True
)

vthing_tpl = jinja_env.get_template('vthing.tpl')


def build_vthing(thing, comms, dtypes) -> str:
    context = {
        'thing': thing,
        'comms': comms,
        'dtype': dtypes
    }
    modelf = vthing_tpl.render(context)
    return modelf


def thing_to_vcode(thing, comms, dtypes) -> str:
    vthing_str = build_vthing(thing, comms, dtypes)
    return vthing_str