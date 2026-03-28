from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import (
    CloudProvider,
    ConversionResult,
    MigrationPlan,
    ParsedTerraform,
    TerraformResource,
)


class MigrationPhase(str, Enum):
    INITIALIZED = "initialized"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    CONVERTING = "converting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentState:
    """State object passed between LangGraph nodes."""

    # Input configuration
    source_path: str
    output_path: str
    source_provider: CloudProvider
    target_provider: CloudProvider

    # Current phase
    phase: MigrationPhase = MigrationPhase.INITIALIZED

    # Parsed data
    parsed_terraform: ParsedTerraform | None = None
    dependency_order: list[str] = field(default_factory=list)

    # Planning
    migration_plan: MigrationPlan | None = None

    # Conversion progress
    current_resource_index: int = 0
    conversion_results: list[ConversionResult] = field(default_factory=list)
    converted_files: dict[str, str] = field(default_factory=dict)

    # Validation
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    validation_attempts: int = 0
    max_validation_attempts: int = 3

    # Tracking
    messages: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Resources requiring manual review
    manual_review_items: list[dict[str, Any]] = field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def get_current_resource(self) -> TerraformResource | None:
        if not self.migration_plan:
            return None
        if self.current_resource_index >= len(
            self.migration_plan.resources_to_convert
        ):
            return None
        return self.migration_plan.resources_to_convert[
            self.current_resource_index
        ]

    def advance_resource(self) -> None:
        self.current_resource_index += 1
