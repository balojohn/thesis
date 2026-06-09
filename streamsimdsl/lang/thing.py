from os.path import join

from textx import metamodel_from_file
import textx.scoping.providers as scoping_providers

from ..utils.utils import MODEL_REPO_PATH, THIS_DIR, GENFILES_REPO_PATH
from ..mm_classes.datatype import type_builtins, PrimitiveDataType

from .shared_globals import SHARED_GLOBAL_REPO

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
            "*.sensors": scoping_providers.FQNGlobalRepo(
                join(MODEL_REPO_PATH, 'things', '*.thing')
            ),
            "*.actuators": scoping_providers.FQNGlobalRepo(
                join(MODEL_REPO_PATH, 'things', '*.thing')
            ),
        }
    )
    
    return mm