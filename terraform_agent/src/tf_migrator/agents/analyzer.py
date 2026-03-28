from __future__ import annotations

from anthropic import Anthropic

from ..core.parser import TerraformParser
from ..core.state import AgentState


class AnalyzerAgent:
    """Agent responsible for parsing and analyzing Terraform configurations."""

    def __init__(self, client: Anthropic):
        self.client = client

    def analyze(self, state: AgentState) -> AgentState:
        """Parse Terraform files and build dependency graph."""
        parser = TerraformParser(state.source_path)
        state.parsed_terraform = parser.parse()
        state.dependency_order = parser.get_conversion_order()

        # Use Claude to analyze complex patterns and relationships
        analysis_prompt = self._build_analysis_prompt(state)
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": analysis_prompt}],
        )

        # Parse Claude's analysis for additional insights
        analysis_text = response.content[0].text
        state = self._process_analysis(state, analysis_text)

        return state

    def _build_analysis_prompt(self, state: AgentState) -> str:
        """Build prompt for Claude to analyze the Terraform configuration."""
        resources_summary = []
        for r in state.parsed_terraform.resources[:50]:  # Limit for context
            resources_summary.append(
                f"- {r.resource_type}.{r.name} (category: {r.category.value})"
            )

        return f"""Analyze this Terraform configuration for migration from 
{state.source_provider.value} to {state.target_provider.value}.

## Resources Found
{chr(10).join(resources_summary)}

## Variables
{len(state.parsed_terraform.variables)} variables defined

## Modules
{len(state.parsed_terraform.modules)} module calls

## Analysis Tasks
1. Identify any complex patterns that need special handling
2. Flag resources that may have no direct equivalent
3. Note any security-sensitive configurations
4. Identify cross-resource dependencies that affect conversion order
5. Suggest any additional resources that will need to be created

Provide your analysis in a structured format with clear sections."""

    def _process_analysis(self, state: AgentState, analysis: str) -> AgentState:
        """Process Claude's analysis and update state."""
        # Extract warnings and notes from analysis
        if "no direct equivalent" in analysis.lower():
            state.warnings.append(
                "Some resources may not have direct equivalents in target provider"
            )

        if "security" in analysis.lower():
            state.warnings.append(
                "Security-sensitive configurations detected - review carefully"
            )

        return state
