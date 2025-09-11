from os.path import join

from textx import metamodel_from_file

from ..utils.utils import THIS_DIR
from ..mm_classes.datatype import type_builtins, PrimitiveDataType

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