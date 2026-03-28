"""Graph modeling for Terraform resources."""

class ResourceGraph:
    def __init__(self):
        self.nodes = []

    def add_node(self, node):
        self.nodes.append(node)
