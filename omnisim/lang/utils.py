from os.path import join, basename
from ..utils.utils import MODEL_REPO_PATH, GENFILES_REPO_PATH

from ..lang import (
    get_actor_mm,
    get_communication_mm,
    get_datatype_mm,
    get_entity_mm,
    get_env_mm,
    get_thing_mm
)

from glob import glob
def preload_models(mm, pattern):
    files = glob(pattern)
    for f in files:
        mm.model_from_file(f)

def preload_dtype_models():
    mm = get_datatype_mm()
    preload_models(mm, join(GENFILES_REPO_PATH, 'datatypes', '*.dtype'))
    return mm

def preload_thing_models():
    mm = get_thing_mm()
    preload_models(mm, join(MODEL_REPO_PATH, 'things', '*.thing'))
    return mm

def preload_actor_models():
    mm = get_actor_mm()
    preload_models(mm, join(MODEL_REPO_PATH, 'actors', '*.actor'))
    return mm

def build_model(model_fpath):
    model_filename = basename(model_fpath)
    if model_filename.endswith('.comm'):
        # preload_dtype_models()
        mm = get_communication_mm()
    
    elif model_filename.endswith('.dtype'):
        mm = get_datatype_mm()
    
    elif model_filename.endswith('.ent'):
        mm = get_entity_mm()
    
    elif model_filename.endswith('.env'):
        # preload datatypes and things so comm references can resolve
        preload_dtype_models()
        preload_thing_models()
        preload_actor_models()    
        mm = get_env_mm()
        preload_models(mm, join(MODEL_REPO_PATH, 'environment', '*.env'))
    
    elif model_filename.endswith('.actor'):
        # preload_dtype_models()
        mm = get_actor_mm()
    
    elif model_filename.endswith('.thing'):
        # preload_dtype_models()
        mm = get_thing_mm()
    
    else:
        raise ValueError('Not a valid model extension.')
    
    model = mm.model_from_file(model_fpath)
    return model