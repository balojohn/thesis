from os.path import join

from textx import metamodel_from_file
# import textx.scoping.providers as scoping_providers

from ..utils import THIS_DIR
from ..mm_classes.datatype import type_builtins, PrimitiveDataType
import textx.scoping as scoping

from .shared_globals import SHARED_GLOBAL_REPO

def get_datatype_mm(debug=False):
    mm = metamodel_from_file(
        join(THIS_DIR, 'grammar','datatype.tx'),
        global_repository=SHARED_GLOBAL_REPO,
        classes=[PrimitiveDataType],
        builtins=type_builtins,
        debug=debug
    )
    return mm