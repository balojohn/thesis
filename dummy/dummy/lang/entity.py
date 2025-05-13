from os.path import dirname, join

from textx import metamodel_from_file, get_children_of_type
import textx.scoping.providers as scoping_providers

from dummy.utils import MODEL_REPO_PATH, THIS_DIR
from dummy.mm_classes.datatype import type_builtins, PrimitiveDataType

def get_entity_mm(debug=False):
    mm = metamodel_from_file(
        join(THIS_DIR, 'grammar', 'entity.tx'),
        classes=[PrimitiveDataType],
        builtins=type_builtins,
        # global_repository=True,
        # debug=debug,
    )
    # mm.register_scope_providers(
    #     {
    #         "*.*": scoping_providers.FQNImportURI(), # What does this do???
    #         "*.entities": scoping_providers.FQNGlobalRepo(
    #             join(MODEL_REPO_PATH, 'entities', '*.ent')
    #         ),
    #         "*.communication": scoping_providers.FQNGlobalRepo(
    #             join(MODEL_REPO_PATH, 'communication', '*.comm')
    #         ),
    #     }
    # )
    return mm