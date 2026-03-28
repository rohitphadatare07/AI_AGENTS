"""Resolve Terraform mapping rules."""

from typing import Dict


def resolve_mapping(mapping: Dict[str, dict], resource_type: str) -> dict:
    """Resolve a target mapping for a resource type."""
    return mapping.get(resource_type, {})
