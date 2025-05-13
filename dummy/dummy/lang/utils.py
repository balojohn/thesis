from os.path import dirname, join, basename
from textx import metamodel_from_file
import textx.scoping.providers as scoping_providers

from dummy.utils import MODEL_REPO_PATH

from dummy.lang import (
    get_entity_mm,
    get_datatype_mm,
    get_communication_mm
)

def build_model(model_fpath):
    model_filename = basename(model_fpath)
    if model_filename.endswith('.ent'):
        mm = get_entity_mm()
    elif model_filename.endswith('.dtype'):
        mm = get_datatype_mm()
    elif model_filename.endswith('.comm'):
        mm = get_communication_mm()
    else:
        raise ValueError('Not a valid model extension.')
    model = mm.model_from_file(model_fpath)
    return model