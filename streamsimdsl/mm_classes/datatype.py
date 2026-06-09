class PrimitiveDataType(object):
    """
    We are registering user PrimitiveDataType class to support
    primitive types (integer, string) in our entity models
    Thus, user doesn't need to provide integer and string
    types in the model but can reference them in attribute types nevertheless.
    """
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    def __str__(self):
        return self.name


type_builtins = {
    'int': PrimitiveDataType(None, 'int'),
    'int32': PrimitiveDataType(None, 'int32'),
    'int64': PrimitiveDataType(None, 'int64'),
    'uint': PrimitiveDataType(None, 'uint'),
    'uint8': PrimitiveDataType(None, 'uint8'),
    'uint32': PrimitiveDataType(None, 'uint32'),
    'uint64': PrimitiveDataType(None, 'uint64'),
    'float': PrimitiveDataType(None, 'float'),
    'float32': PrimitiveDataType(None, 'float32'),
    'float64': PrimitiveDataType(None, 'float64'),
    'str': PrimitiveDataType(None, 'str'),
    'bool': PrimitiveDataType(None, 'bool'),
    'Transformation': PrimitiveDataType(None, 'Transformation')
}
