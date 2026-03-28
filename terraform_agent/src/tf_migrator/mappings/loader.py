"""Load mapping definitions for Terraform migration."""

import yaml


def load_mapping(path: str) -> dict:
    """Load a YAML mapping file."""
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)
