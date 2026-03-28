"""Terraform execution helpers."""

class TerraformTool:
    def init(self, working_dir: str) -> bool:
        return True

    def plan(self, working_dir: str) -> str:
        return "plan"
