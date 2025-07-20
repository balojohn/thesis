class Endpoint:
    def __init__(self, parent):
        self.parent = parent

class Publisher:
    def __init__(self, parent, uri, msg, namespace):
        super().__init__(parent)
        self.uri = uri
        self.msg = msg

class Subscriber:
    def __init__(self, parent, uri, msg, namespace):
        super().__init__(parent)
        self.uri = uri
        self.msg = msg