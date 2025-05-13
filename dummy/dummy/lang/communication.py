from os.path import dirname, join, basename

from textx import metamodel_from_file, get_children_of_type
import textx.scoping.providers as scoping_providers

from dummy.utils import MODEL_REPO_PATH, THIS_DIR
from dummy.mm_classes.datatype import type_builtins, PrimitiveDataType


def get_communication_mm(debug=False):
    mm = metamodel_from_file(
        join(THIS_DIR, 'grammar','communication.tx'),
        classes=[PrimitiveDataType],
        builtins=type_builtins,
        # global_repository=True,
        # debug=debug
    )

    # mm.register_scope_providers(
    #     {
    #         "types": scoping_providers.FQNGlobalRepo(
    #             join(MODEL_REPO_PATH, 'datatypes', '*.dtype')
    #         ),
    #     }
    # )
    return mm