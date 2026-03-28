from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CloudProvider(str, Enum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class ResourceCategory(str, Enum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    IAM = "iam"
    CONTAINER = "container"
    SERVERLESS = "serverless"
    MONITORING = "monitoring"
    OTHER = "other"


@dataclass
class TerraformResource:
    """Represents a single Terraform resource."""

    resource_type: str
    name: str
    attributes: dict[str, Any]
    file_path: str
    line_number: int
    provider: CloudProvider
    category: ResourceCategory = ResourceCategory.OTHER
    dependencies: list[str] = field(default_factory=list)
    raw_hcl: str = ""

    @property
    def address(self) -> str:
        return f"{self.resource_type}.{self.name}"


@dataclass
class TerraformVariable:
    """Represents a Terraform variable."""

    name: str
    var_type: str | None
    default: Any
    description: str
    file_path: str
    sensitive: bool = False
    validation_rules: list[dict] = field(default_factory=list)


@dataclass
class TerraformOutput:
    """Represents a Terraform output."""

    name: str
    value: str
    description: str
    file_path: str
    sensitive: bool = False
    depends_on: list[str] = field(default_factory=list)


@dataclass
class TerraformModule:
    """Represents a Terraform module call."""

    name: str
    source: str
    version: str | None
    inputs: dict[str, Any]
    file_path: str
    providers: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedTerraform:
    """Complete parsed Terraform configuration."""

    resources: list[TerraformResource]
    variables: list[TerraformVariable]
    outputs: list[TerraformOutput]
    modules: list[TerraformModule]
    locals: dict[str, Any]
    providers: dict[str, dict[str, Any]]
    terraform_settings: dict[str, Any]
    data_sources: list[TerraformResource]


@dataclass
class ConversionResult:
    """Result of converting a single resource."""

    original: TerraformResource
    converted_hcl: str
    target_type: str
    warnings: list[str] = field(default_factory=list)
    manual_review_needed: bool = False
    review_reasons: list[str] = field(default_factory=list)


@dataclass
class MigrationPlan:
    """Complete migration plan for a Terraform repository."""

    source_provider: CloudProvider
    target_provider: CloudProvider
    resources_to_convert: list[TerraformResource]
    variables_to_transform: list[TerraformVariable]
    outputs_to_transform: list[TerraformOutput]
    modules_to_replace: list[TerraformModule]
    unsupported_resources: list[TerraformResource]
    conversion_order: list[str]  # Resource addresses in dependency order
    estimated_manual_effort: str
    risk_assessment: dict[str, Any]
