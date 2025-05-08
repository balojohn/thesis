from os.path import dirname, join

from textx import metamodel_from_file, get_children_of_type
import textx.scoping.providers as scoping_providers

from dummy.lang.datatype import type_builtins, PrimitiveDataType

MODEL_REPO_PATH = join(dirname(__file__), '..', 'models')

def get_entity_mm():
    mm = metamodel_from_file(
        join(dirname(__file__), 'grammar', 'entity.tx'),
        classes=[PrimitiveDataType],
        builtins=type_builtins,
        # global_repository=True,
        # debug=False,
    )
    mm.register_scope_providers(
        {
            "*.*": scoping_providers.FQNImportURI(), # What does this do???
            "*.entities": scoping_providers.FQNGlobalRepo(
                join(MODEL_REPO_PATH, 'entities','*.ent')
            ),
        }
    )
    return mm