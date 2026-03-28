from __future__ import annotations

import json
import re
from typing import Any

from anthropic import Anthropic

from ..core.models import ConversionResult, TerraformResource
from ..core.state import AgentState


class ConverterAgent:
    """Agent responsible for converting individual resources."""

    CONVERSION_TOOLS = [
        {
            "name": "convert_resource",
            "description": "Convert a Terraform resource from source to target provider",
            "input_schema": {
                "type": "object",
                "properties": {
                    "target_resource_type": {
                        "type": "string",
                        "description": "The target provider's resource type",
                    },
                    "converted_hcl": {
                        "type": "string",
                        "description": "The converted HCL code",
                    },
                    "additional_resources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional HCL for required supporting resources",
                    },
                    "warnings": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Warnings about the conversion",
                    },
                    "requires_manual_review": {
                        "type": "boolean",
                        "description": "Whether manual review is needed",
                    },
                    "review_reasons": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Reasons for manual review",
                    },
                },
                "required": ["target_resource_type", "converted_hcl"],
            },
        },
        {
            "name": "lookup_mapping",
            "description": "Look up the mapping configuration for a resource type",
            "input_schema": {
                "type": "object",
                "properties": {
                    "source_resource_type": {
                        "type": "string",
                        "description": "The source resource type to look up",
                    },
                },
                "required": ["source_resource_type"],
            },
        },
    ]

    def __init__(self, client: Anthropic, mappings: dict):
        self.client = client
        self.mappings = mappings

    def convert_resource(
        self, state: AgentState, resource: TerraformResource
    ) -> AgentState:
        """Convert a single resource using Claude with tools."""
        mapping = self.mappings.get("resource_mappings", {}).get(
            resource.resource_type, {}
        )

        system_prompt = self._build_system_prompt(state)
        user_prompt = self._build_conversion_prompt(resource, mapping, state)

        messages = [{"role": "user", "content": user_prompt}]

        # Agentic loop with tool use
        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                tools=self.CONVERSION_TOOLS,
                messages=messages,
            )

            # Check for tool use
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._handle_tool_call(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # Process final response
                for block in response.content:
                    if block.type == "tool_use" and block.name == "convert_resource":
                        state = self._process_conversion(state, resource, block.input)
                        return state

                # Fallback: extract HCL from text response
                state = self._extract_conversion_from_text(
                    state, resource, response.content[0].text
                )
                return state

    def _build_system_prompt(self, state: AgentState) -> str:
        """Build system prompt for conversion."""
        return f"""You are an expert Terraform engineer specializing in cloud migrations.

You are converting Terraform configurations from {state.source_provider.value} to {state.target_provider.value}.

## Guidelines
1. Preserve the logical intent of each resource
2. Use idiomatic patterns for the target provider
3. Maintain all functionality where possible
4. Create additional resources when the target provider requires them
5. Flag anything that cannot be automatically converted
6. Use consistent naming conventions
7. Preserve comments and documentation

## Output Requirements
- Generate valid HCL syntax
- Include all required arguments
- Add appropriate tags/labels
- Configure security settings appropriately

Use the convert_resource tool to provide your conversion."""

    def _build_conversion_prompt(
        self,
        resource: TerraformResource,
        mapping: dict,
        state: AgentState,
    ) -> str:
        """Build prompt for converting a specific resource."""
        # Include validation errors if this is a retry
        error_context = ""
        if state.validation_errors:
            relevant_errors = [
                e for e in state.validation_errors
                if resource.address in str(e)
            ]
            if relevant_errors:
                error_context = f"""
## Previous Validation Errors
The previous conversion attempt had these errors that need to be fixed:
{json.dumps(relevant_errors, indent=2)}
"""

        return f"""Convert this {state.source_provider.value} resource to {state.target_provider.value}:

## Source Resource
```hcl
{resource.raw_hcl or self._reconstruct_hcl(resource)}
