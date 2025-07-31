from os.path import join

from textx import metamodel_from_file
import textx.scoping.providers as scoping_providers

from ..utils import MODEL_REPO_PATH, THIS_DIR
from ..mm_classes.datatype import type_builtins, PrimitiveDataType

from .shared_globals import SHARED_GLOBAL_REPO

def get_actor_mm(debug=False):
    mm = metamodel_from_file(
        join(THIS_DIR, 'grammar', 'actor.tx'),
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
            # "*.communication": scoping_providers.FQNGlobalRepo(
            #     join(MODEL_REPO_PATH, 'communication','*.comm')
            # ),
        }
    )
    
    return mm