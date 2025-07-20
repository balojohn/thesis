from glob import glob
from os.path import join

from ..lang import (
    get_datatype_mm,
)
from textx import metamodel_from_file
import textx.scoping.providers as scoping_providers
import textx.scoping as scoping

from ..utils import MODEL_REPO_PATH, THIS_DIR
from ..mm_classes.datatype import type_builtins, PrimitiveDataType

from .shared_globals import SHARED_GLOBAL_REPO

# def preload_datatypes(mm):
#     dtype_files = glob(join(MODEL_REPO_PATH, 'datatypes', '*.dtype'))
#     for dtype_file in dtype_files:
#         mm.model_from_file(dtype_file)

def get_thing_mm(debug=False):
    mm = metamodel_from_file(
        join(THIS_DIR, 'grammar', 'thing.tx'),
        classes=[PrimitiveDataType],
        builtins=type_builtins,
        global_repository=SHARED_GLOBAL_REPO,
        debug=debug,
    )
    mm.register_scope_providers(
        {
            "*.*": scoping_providers.FQNImportURI(),
            "*.dataModel": scoping_providers.FQNGlobalRepo(
                join(MODEL_REPO_PATH, 'datatypes', '*.dtype')
            ),
            "*.sensors": scoping_providers.FQNGlobalRepo(
                join(MODEL_REPO_PATH, 'things', '*.thing')
            ),
            "*.actuators": scoping_providers.FQNGlobalRepo(
                join(MODEL_REPO_PATH, 'things', '*.thing')
            )
        }
    )

    # preload_datatypes(mm)
    
    return mm