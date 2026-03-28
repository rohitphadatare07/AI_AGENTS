### 7. CLI Interface

from __future__ import annotations

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .agents.orchestrator import MigrationOrchestrator
from .core.models import CloudProvider
from .core.state import MigrationPhase

app = typer.Typer(
    name="tf-migrate",
    help="AI-powered Terraform cloud migration tool",
)
console = Console()


@app.command()
def migrate(
    source: str = typer.Argument(..., help="Path to source Terraform repository"),
    output: str = typer.Argument(..., help="Path for converted Terraform output"),
    from_provider: str = typer.Option(
        ..., "--from", "-f", help="Source cloud provider (aws, gcp, azure)"
    ),
    to_provider: str = typer.Option(
        ..., "--to", "-t", help="Target cloud provider (aws, gcp, azure)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Analyze and plan without converting"
    ),
):
    """Migrate Terraform configuration between cloud providers."""
    try:
        source_cloud = CloudProvider(from_provider.lower())
        target_cloud = CloudProvider(to_provider.lower())
    except ValueError as e:
        console.print(f"[red]Invalid provider: {e}[/red]")
        raise typer.Exit(1)

    console.print(
        f"\n[bold]Terraform Migration[/bold]: {source_cloud.value} → {target_cloud.value}\n"
    )

    orchestrator = MigrationOrchestrator(
        source_path=source,
        output_path=output,
        source_provider=source_cloud,
        target_provider=target_cloud,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Starting migration...", total=None)

        # Run the migration
        final_state = orchestrator.run()

        progress.update(task, description="Migration complete")

    # Display results
    _display_results(final_state)


def _display_results(state) -> None:
    """Display migration results."""
    console.print("\n")

    if state.phase == MigrationPhase.COMPLETED:
        console.print("[green]✓ Migration completed successfully[/green]\n")
    else:
        console.print("[red]✗ Migration failed[/red]\n")

    # Summary table
    table = Table(title="Migration Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Resources Converted", str(len(state.conversion_results)))
    table.add_row("Manual Review Items", str(len(state.manual_review_items)))
    table.add_row("Warnings", str(len(state.warnings)))
    table.add_row("Errors", str(len(state.errors)))
    table.add_row("Output Path", state.output_path)

    console.print(table)

    # Warnings
    if state.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in state.warnings[:10]:
            console.print(f"  • {warning}")

    # Manual review items
    if state.manual_review_items:
        console.print("\n[yellow]Resources Requiring Manual Review:[/yellow]")
        for item in state.manual_review_items:
            console.print(f"  • {item['resource']}")
            for reason in item.get("reasons", []):
                console.print(f"    - {reason}")

    # Errors
    if state.errors:
        console.print("\n[red]Errors:[/red]")
        for error in state.errors:
            console.print(f"  • {error}")


@app.command()
def analyze(
    source: str = typer.Argument(..., help="Path to Terraform repository"),
):
    """Analyze a Terraform repository without converting."""
    from .core.parser import TerraformParser

    parser = TerraformParser(source)
    parsed = parser.parse()

    table = Table(title="Terraform Analysis")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="magenta")

    table.add_row("Resources", str(len(parsed.resources)))
    table.add_row("Data Sources", str(len(parsed.data_sources)))
    table.add_row("Variables", str(len(parsed.variables)))
    table.add_row("Outputs", str(len(parsed.outputs)))
    table.add_row("Modules", str(len(parsed.modules)))

    console.print(table)

    # Resource breakdown
    console.print("\n[bold]Resources by Type:[/bold]")
    type_counts: dict[str, int] = {}
    for r in parsed.resources:
        type_counts[r.resource_type] = type_counts.get(r.resource_type, 0) + 1

    for rtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        console.print(f"  {rtype}: {count}")


if __name__ == "__main__":
    app()
