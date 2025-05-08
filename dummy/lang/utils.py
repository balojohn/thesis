from os.path import dirname, join, basename

from dummy.lang import (
    get_entity_mm
)

def build_model(model_fpath):
    model_filename = basename(model_fpath)
    if model_filename.endswith('.ent'):
        mm = get_entity_mm()
    else:
        raise ValueError('Not a valid model extension.')
    model = mm.model_from_file(model_fpath)
    return model