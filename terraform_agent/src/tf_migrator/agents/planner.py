from __future__ import annotations

import json

from anthropic import Anthropic

from ..core.models import MigrationPlan, TerraformResource
from ..core.state import AgentState


class PlannerAgent:
    """Agent responsible for creating migration plans."""

    def __init__(self, client: Anthropic, mappings: dict):
        self.client = client
        self.mappings = mappings

    def plan(self, state: AgentState) -> AgentState:
        """Create a comprehensive migration plan."""
        resources_to_convert = []
        unsupported_resources = []

        resource_mappings = self.mappings.get("resource_mappings", {})

        for resource in state.parsed_terraform.resources:
            if resource.resource_type in resource_mappings:
                resources_to_convert.append(resource)
            else:
                unsupported_resources.append(resource)

        # Use Claude to assess complexity and risk
        assessment = self._assess_migration(
            state, resources_to_convert, unsupported_resources
        )

        # Order resources based on dependencies
        ordered_resources = self._order_by_dependencies(
            resources_to_convert, state.dependency_order
        )

        state.migration_plan = MigrationPlan(
            source_provider=state.source_provider,
            target_provider=state.target_provider,
            resources_to_convert=ordered_resources,
            variables_to_transform=state.parsed_terraform.variables,
            outputs_to_transform=state.parsed_terraform.outputs,
            modules_to_replace=state.parsed_terraform.modules,
            unsupported_resources=unsupported_resources,
            conversion_order=[r.address for r in ordered_resources],
            estimated_manual_effort=assessment.get("effort", "unknown"),
            risk_assessment=assessment.get("risks", {}),
        )

        return state

    def _assess_migration(
        self,
        state: AgentState,
        to_convert: list[TerraformResource],
        unsupported: list[TerraformResource],
    ) -> dict:
        """Use Claude to assess migration complexity."""
        prompt = f"""Assess this Terraform migration:

## Migration Details
- From: {state.source_provider.value}
- To: {state.target_provider.value}
- Convertible resources: {len(to_convert)}
- Unsupported resources: {len(unsupported)}

## Convertible Resource Types
{json.dumps([r.resource_type for r in to_convert[:30]], indent=2)}

## Unsupported Resource Types  
{json.dumps([r.resource_type for r in unsupported], indent=2)}

Provide a JSON assessment with:
1. "effort": estimated manual effort (low/medium/high)
2. "risks": dict of risk categories and descriptions
3. "recommendations": list of recommendations

Return only valid JSON."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            return json.loads(response.content[0].text)
        except json.JSONDecodeError:
            return {"effort": "medium", "risks": {}, "recommendations": []}

    def _order_by_dependencies(
        self,
        resources: list[TerraformResource],
        dependency_order: list[str],
    ) -> list[TerraformResource]:
        """Order resources based on dependency graph."""
        resource_map = {r.address: r for r in resources}
        ordered = []

        for address in dependency_order:
            if address in resource_map:
                ordered.append(resource_map[address])

        # Add any resources not in dependency order
        remaining = [r for r in resources if r not in ordered]
        ordered.extend(remaining)

        return ordered
