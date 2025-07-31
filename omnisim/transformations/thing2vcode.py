import jinja2

from ..utils import TEMPLATES_PATH
from ..lang import build_model

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    trim_blocks=True,
    lstrip_blocks=True
)

vthing_tpl = jinja_env.get_template('vthing.tpl')


def build_vthing(thing, communication):
    context = {
        'thing': thing,
        'communication': communication
    }
    modelf = vthing_tpl.render(context)
    return modelf


def thing_to_vcode(thing, communication) -> str:
    vthing_str = build_vthing(thing, communication)
    return vthing_str