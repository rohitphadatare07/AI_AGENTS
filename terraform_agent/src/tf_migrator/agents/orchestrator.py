from __future__ import annotations

import os
from pathlib import Path

from anthropic import Anthropic
from langgraph.graph import END, StateGraph

from ..core.models import CloudProvider
from ..core.state import AgentState, MigrationPhase
from ..mappings.loader import MappingLoader
from .analyzer import AnalyzerAgent
from .converter import ConverterAgent
from .planner import PlannerAgent
from .validator import ValidatorAgent


class MigrationOrchestrator:
    """Main orchestrator for Terraform migration using LangGraph."""

    def __init__(
        self,
        source_path: str,
        output_path: str,
        source_provider: CloudProvider,
        target_provider: CloudProvider,
    ):
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.mapping_loader = MappingLoader()

        self.initial_state = AgentState(
            source_path=source_path,
            output_path=output_path,
            source_provider=source_provider,
            target_provider=target_provider,
        )

        # Initialize agents
        self.analyzer = AnalyzerAgent(self.client)
        self.planner = PlannerAgent(
            self.client,
            self.mapping_loader.load(source_provider, target_provider),
        )
        self.converter = ConverterAgent(
            self.client,
            self.mapping_loader.load(source_provider, target_provider),
        )
        self.validator = ValidatorAgent(self.client)

        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("convert", self._convert_node)
        workflow.add_node("validate", self._validate_node)
        workflow.add_node("write_output", self._write_output_node)
        workflow.add_node("handle_error", self._handle_error_node)

        # Set entry point
        workflow.set_entry_point("analyze")

        # Add edges
        workflow.add_edge("analyze", "plan")
        workflow.add_edge("plan", "convert")

        # Conditional edges from convert
        workflow.add_conditional_edges(
            "convert",
            self._should_continue_converting,
            {
                "continue": "convert",
                "validate": "validate",
                "error": "handle_error",
            },
        )

        # Conditional edges from validate
        workflow.add_conditional_edges(
            "validate",
            self._check_validation_result,
            {
                "success": "write_output",
                "retry": "convert",
                "error": "handle_error",
            },
        )

        workflow.add_edge("write_output", END)
        workflow.add_edge("handle_error", END)

        return workflow.compile()

    def _analyze_node(self, state: AgentState) -> AgentState:
        """Parse and analyze the source Terraform configuration."""
        state.phase = MigrationPhase.ANALYZING
        state.add_message("system", "Starting analysis of source Terraform...")

        try:
            state = self.analyzer.analyze(state)
            state.add_message(
                "system",
                f"Analysis complete. Found {len(state.parsed_terraform.resources)} "
                f"resources, {len(state.parsed_terraform.variables)} variables.",
            )
        except Exception as e:
            state.errors.append(f"Analysis failed: {e}")
            state.phase = MigrationPhase.FAILED

        return state

    def _plan_node(self, state: AgentState) -> AgentState:
        """Create a migration plan."""
        state.phase = MigrationPhase.PLANNING
        state.add_message("system", "Creating migration plan...")

        try:
            state = self.planner.plan(state)
            plan = state.migration_plan

            state.add_message(
                "system",
                f"Migration plan created:\n"
                f"  - Resources to convert: {len(plan.resources_to_convert)}\n"
                f"  - Unsupported resources: {len(plan.unsupported_resources)}\n"
                f"  - Estimated manual effort: {plan.estimated_manual_effort}",
            )
        except Exception as e:
            state.errors.append(f"Planning failed: {e}")
            state.phase = MigrationPhase.FAILED

        return state

    def _convert_node(self, state: AgentState) -> AgentState:
        """Convert the current resource."""
        state.phase = MigrationPhase.CONVERTING
        resource = state.get_current_resource()

        if resource is None:
            return state

        state.add_message(
            "system",
            f"Converting {resource.address} ({state.current_resource_index + 1}/"
            f"{len(state.migration_plan.resources_to_convert)})",
        )

        try:
            state = self.converter.convert_resource(state, resource)
            state.advance_resource()
        except Exception as e:
            state.errors.append(f"Conversion failed for {resource.address}: {e}")

        return state

    def _validate_node(self, state: AgentState) -> AgentState:
        """Validate the converted Terraform configuration."""
        state.phase = MigrationPhase.VALIDATING
        state.add_message("system", "Validating converted Terraform...")
        state.validation_attempts += 1

        try:
            state = self.validator.validate(state)

            if state.validation_errors:
                state.add_message(
                    "system",
                    f"Validation found {len(state.validation_errors)} errors. "
                    f"Attempt {state.validation_attempts}/{state.max_validation_attempts}",
                )
            else:
                state.add_message("system", "Validation successful!")
        except Exception as e:
            state.errors.append(f"Validation failed: {e}")

        return state

    def _write_output_node(self, state: AgentState) -> AgentState:
        """Write converted Terraform files to output directory."""
        state.phase = MigrationPhase.COMPLETED
        output_path = Path(state.output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        for filename, content in state.converted_files.items():
            file_path = output_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        # Write migration report
        report = self._generate_report(state)
        (output_path / "MIGRATION_REPORT.md").write_text(report)

        state.add_message(
            "system",
            f"Migration complete. Files written to {output_path}",
        )

        return state

    def _handle_error_node(self, state: AgentState) -> AgentState:
        """Handle migration errors."""
        state.phase = MigrationPhase.FAILED
        state.add_message(
            "system",
            f"Migration failed with errors:\n" + "\n".join(state.errors),
        )
        return state

    def _should_continue_converting(self, state: AgentState) -> str:
        """Decide whether to continue converting or move to validation."""
        if state.errors:
            return "error"
        if state.get_current_resource() is not None:
            return "continue"
        return "validate"

    def _check_validation_result(self, state: AgentState) -> str:
        """Check validation results and decide next step."""
        if not state.validation_errors:
            return "success"
        if state.validation_attempts >= state.max_validation_attempts:
            return "error"
        # Reset for retry - converter will use validation errors for context
        state.current_resource_index = 0
        return "retry"

    def _generate_report(self, state: AgentState) -> str:
        """Generate a migration report."""
        lines = [
            "# Terraform Migration Report",
            "",
            f"**Source Provider:** {state.source_provider.value}",
            f"**Target Provider:** {state.target_provider.value}",
            f"**Source Path:** {state.source_path}",
            f"**Output Path:** {state.output_path}",
            "",
            "## Summary",
            "",
            f"- Total resources converted: {len(state.conversion_results)}",
            f"- Resources requiring manual review: {len(state.manual_review_items)}",
            f"- Warnings: {len(state.warnings)}",
            "",
        ]

        if state.manual_review_items:
            lines.extend([
                "## Manual Review Required",
                "",
            ])
            for item in state.manual_review_items:
                lines.append(f"### {item['resource']}")
                lines.append("")
                for reason in item.get("reasons", []):
                    lines.append(f"- {reason}")
                lines.append("")

        if state.warnings:
            lines.extend([
                "## Warnings",
                "",
            ])
            for warning in state.warnings:
                lines.append(f"- {warning}")
            lines.append("")

        return "\n".join(lines)

    def run(self) -> AgentState:
        """Execute the migration workflow."""
        return self.graph.invoke(self.initial_state)
