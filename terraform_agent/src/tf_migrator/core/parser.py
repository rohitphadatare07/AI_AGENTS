from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import hcl2
import networkx as nx

from .models import (
    CloudProvider,
    ParsedTerraform,
    ResourceCategory,
    TerraformModule,
    TerraformOutput,
    TerraformResource,
    TerraformVariable,
)

# Resource type to category mapping
CATEGORY_PATTERNS: dict[str, list[str]] = {
    ResourceCategory.COMPUTE: [
        "instance", "vm", "server", "ec2", "compute_instance"
    ],
    ResourceCategory.STORAGE: [
        "bucket", "s3", "gcs", "blob", "storage", "disk", "volume"
    ],
    ResourceCategory.NETWORK: [
        "vpc", "network", "subnet", "firewall", "security_group",
        "route", "gateway", "lb", "load_balancer"
    ],
    ResourceCategory.DATABASE: [
        "rds", "sql", "database", "db", "dynamo", "spanner", "firestore"
    ],
    ResourceCategory.IAM: [
        "iam", "role", "policy", "user", "group", "service_account"
    ],
    ResourceCategory.CONTAINER: [
        "ecs", "eks", "gke", "aks", "kubernetes", "k8s", "container"
    ],
    ResourceCategory.SERVERLESS: [
        "lambda", "function", "cloud_function", "cloud_run"
    ],
    ResourceCategory.MONITORING: [
        "cloudwatch", "monitoring", "alert", "log", "metric"
    ],
}

PROVIDER_PREFIXES: dict[str, CloudProvider] = {
    "aws_": CloudProvider.AWS,
    "google_": CloudProvider.GCP,
    "azurerm_": CloudProvider.AZURE,
}


def detect_provider(resource_type: str) -> CloudProvider:
    """Detect cloud provider from resource type prefix."""
    for prefix, provider in PROVIDER_PREFIXES.items():
        if resource_type.startswith(prefix):
            return provider
    raise ValueError(f"Unknown provider for resource type: {resource_type}")


def categorize_resource(resource_type: str) -> ResourceCategory:
    """Categorize a resource based on its type."""
    resource_lower = resource_type.lower()
    for category, patterns in CATEGORY_PATTERNS.items():
        if any(pattern in resource_lower for pattern in patterns):
            return category
    return ResourceCategory.OTHER


def extract_dependencies(attributes: dict[str, Any]) -> list[str]:
    """Extract resource dependencies from attribute values."""
    dependencies = set()
    ref_pattern = re.compile(
        r"(?:^|\W)((?:data|local|module|var|"
        r"aws_|google_|azurerm_)[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*)"
    )

    def walk_values(obj: Any) -> None:
        if isinstance(obj, str):
            for match in ref_pattern.finditer(obj):
                ref = match.group(1)
                if not ref.startswith(("var.", "local.")):
                    parts = ref.split(".")
                    if len(parts) >= 2:
                        dependencies.add(f"{parts[0]}.{parts[1]}")
        elif isinstance(obj, dict):
            for v in obj.values():
                walk_values(v)
        elif isinstance(obj, list):
            for item in obj:
                walk_values(item)

    walk_values(attributes)

    if "depends_on" in attributes:
        deps = attributes["depends_on"]
        if isinstance(deps, list):
            dependencies.update(deps)

    return list(dependencies)


class TerraformParser:
    """Parses Terraform files and builds dependency graphs."""

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path)
        self._parsed: ParsedTerraform | None = None

    def parse(self) -> ParsedTerraform:
        """Parse all Terraform files in the repository."""
        resources: list[TerraformResource] = []
        variables: list[TerraformVariable] = []
        outputs: list[TerraformOutput] = []
        modules: list[TerraformModule] = []
        data_sources: list[TerraformResource] = []
        all_locals: dict[str, Any] = {}
        all_providers: dict[str, dict[str, Any]] = {}
        terraform_settings: dict[str, Any] = {}

        tf_files = list(self.repo_path.rglob("*.tf"))

        for tf_file in tf_files:
            if ".terraform" in str(tf_file):
                continue

            with open(tf_file) as f:
                content = f.read()

            try:
                parsed = hcl2.loads(content)
            except Exception as e:
                print(f"Warning: Failed to parse {tf_file}: {e}")
                continue

            # Parse resources
            for resource_block in parsed.get("resource", []):
                for resource_type, instances in resource_block.items():
                    for name, attrs in instances.items():
                        provider = detect_provider(resource_type)
                        resources.append(
                            TerraformResource(
                                resource_type=resource_type,
                                name=name,
                                attributes=attrs,
                                file_path=str(tf_file.relative_to(self.repo_path)),
                                line_number=0,
                                provider=provider,
                                category=categorize_resource(resource_type),
                                dependencies=extract_dependencies(attrs),
                                raw_hcl=self._extract_block_hcl(
                                    content, "resource", resource_type, name
                                ),
                            )
                        )

            # Parse data sources
            for data_block in parsed.get("data", []):
                for data_type, instances in data_block.items():
                    for name, attrs in instances.items():
                        try:
                            provider = detect_provider(data_type)
                        except ValueError:
                            continue
                        data_sources.append(
                            TerraformResource(
                                resource_type=f"data.{data_type}",
                                name=name,
                                attributes=attrs,
                                file_path=str(tf_file.relative_to(self.repo_path)),
                                line_number=0,
                                provider=provider,
                                category=categorize_resource(data_type),
                                dependencies=extract_dependencies(attrs),
                            )
                        )

            # Parse variables
            for var_block in parsed.get("variable", []):
                for var_name, var_attrs in var_block.items():
                    variables.append(
                        TerraformVariable(
                            name=var_name,
                            var_type=var_attrs.get("type"),
                            default=var_attrs.get("default"),
                            description=var_attrs.get("description", ""),
                            file_path=str(tf_file.relative_to(self.repo_path)),
                            sensitive=var_attrs.get("sensitive", False),
                            validation_rules=var_attrs.get("validation", []),
                        )
                    )

            # Parse outputs
            for output_block in parsed.get("output", []):
                for output_name, output_attrs in output_block.items():
                    outputs.append(
                        TerraformOutput(
                            name=output_name,
                            value=str(output_attrs.get("value", "")),
                            description=output_attrs.get("description", ""),
                            file_path=str(tf_file.relative_to(self.repo_path)),
                            sensitive=output_attrs.get("sensitive", False),
                            depends_on=output_attrs.get("depends_on", []),
                        )
                    )

            # Parse modules
            for module_block in parsed.get("module", []):
                for module_name, module_attrs in module_block.items():
                    modules.append(
                        TerraformModule(
                            name=module_name,
                            source=module_attrs.get("source", ""),
                            version=module_attrs.get("version"),
                            inputs={
                                k: v
                                for k, v in module_attrs.items()
                                if k not in ("source", "version", "providers")
                            },
                            file_path=str(tf_file.relative_to(self.repo_path)),
                            providers=module_attrs.get("providers", {}),
                        )
                    )

            # Parse locals
            for local_block in parsed.get("locals", []):
                all_locals.update(local_block)

            # Parse providers
            for provider_block in parsed.get("provider", []):
                all_providers.update(provider_block)

            # Parse terraform block
            for tf_block in parsed.get("terraform", []):
                terraform_settings.update(tf_block)

        self._parsed = ParsedTerraform(
            resources=resources,
            variables=variables,
            outputs=outputs,
            modules=modules,
            locals=all_locals,
            providers=all_providers,
            terraform_settings=terraform_settings,
            data_sources=data_sources,
        )

        return self._parsed

    def _extract_block_hcl(
        self, content: str, block_type: str, resource_type: str, name: str
    ) -> str:
        """Extract the raw HCL for a specific block."""
        pattern = rf'{block_type}\s+"{resource_type}"\s+"{name}"\s*\{{'
        match = re.search(pattern, content)
        if not match:
            return ""

        start = match.start()
        brace_count = 0
        end = start

        for i, char in enumerate(content[start:], start):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break

        return content[start:end]

    def build_dependency_graph(self) -> nx.DiGraph:
        """Build a directed graph of resource dependencies."""
        if not self._parsed:
            self.parse()

        graph = nx.DiGraph()

        for resource in self._parsed.resources:
            graph.add_node(
                resource.address,
                resource=resource,
                category=resource.category,
            )

        for resource in self._parsed.resources:
            for dep in resource.dependencies:
                if graph.has_node(dep):
                    graph.add_edge(dep, resource.address)

        return graph

    def get_conversion_order(self) -> list[str]:
        """Get resources in topological order for conversion."""
        graph = self.build_dependency_graph()
        try:
            return list(nx.topological_sort(graph))
        except nx.NetworkXUnfeasible:
            # Cycle detected, fall back to simple ordering
            return [r.address for r in self._parsed.resources]
