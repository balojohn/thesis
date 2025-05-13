from os.path import dirname, join, basename

from textx import metamodel_from_file, get_children_of_type
import textx.scoping.providers as scoping_providers

from dummy.utils import MODEL_REPO_PATH, THIS_DIR
from dummy.mm_classes.datatype import type_builtins, PrimitiveDataType


def get_datatype_mm(debug=False):
    mm = metamodel_from_file(
        join(THIS_DIR, 'grammar','datatype.tx'),
        global_repository=True,
        classes=[PrimitiveDataType],
        builtins=type_builtins,
        debug=debug
    )
    return mm