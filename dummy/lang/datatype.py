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
    'int'   : PrimitiveDataType(None, 'int'),
    'float' : PrimitiveDataType(None, 'float'),
    'str'   : PrimitiveDataType(None, 'str')
}