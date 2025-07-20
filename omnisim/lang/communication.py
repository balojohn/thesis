from os.path import join

from textx import metamodel_from_file
import textx.scoping.providers as scoping_providers
import textx.scoping as scoping
from ..utils import MODEL_REPO_PATH, THIS_DIR
from ..mm_classes.datatype import type_builtins, PrimitiveDataType

from .shared_globals import SHARED_GLOBAL_REPO

def get_communication_mm(debug=False):
    mm = metamodel_from_file(
        join(THIS_DIR, 'grammar','communication.tx'),
        classes=[PrimitiveDataType],
        builtins=type_builtins,
        global_repository=SHARED_GLOBAL_REPO,
        debug=debug
    )

    mm.register_scope_providers(
        {
            "*.communication": scoping_providers.FQNGlobalRepo(
                join(MODEL_REPO_PATH, 'communication', '*.comm')
            ),
        }
    )
    return mm