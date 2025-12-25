"""
Command Line Interface for Multi-Agent Oracle.

Usage:
    oracle resolve "Did Bitcoin reach $100k?" --criteria "BTC >= $100,000"
    oracle serve --port 8090
"""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="oracle",
    help="1024 Multi-Agent Deep Research Oracle CLI",
    add_completion=False,
)

console = Console()


@app.command()
def resolve(
    question: str = typer.Argument(..., help="The question to resolve"),
    criteria: str = typer.Option(..., "--criteria", "-c", help="Resolution criteria"),
    agents: int = typer.Option(3, "--agents", "-a", help="Number of agents to use"),
    market_id: int = typer.Option(0, "--market-id", "-m", help="Market ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    save_to: str | None = typer.Option(None, "--save", help="Save result to file"),
):
    """
    Resolve a prediction market question using multi-agent research.

    Example:
        oracle resolve "Did SpaceX land Starship?" -c "Successful landing"
    """
    asyncio.run(_resolve_async(question, criteria, agents, market_id, output_json, save_to))


async def _resolve_async(
    question: str,
    criteria: str,
    agents: int,
    market_id: int,
    output_json: bool,
    save_to: str | None,
):
    """Async resolution handler."""
    from oracle.core import MultiAgentOracle, OracleConfig

    console.print()
    console.print(
        Panel.fit(
            f"[bold blue]Question:[/bold blue] {question}\n"
            f"[bold blue]Criteria:[/bold blue] {criteria}\n"
            f"[bold blue]Agents:[/bold blue] {agents}",
            title="🔮 Multi-Agent Oracle",
        )
    )
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing oracle...", total=None)

        try:
            oracle = MultiAgentOracle(config=OracleConfig(num_agents=agents))

            progress.update(task, description="Running agent research...")

            result = await oracle.resolve(
                question=question,
                resolution_criteria=criteria,
                market_id=market_id,
            )

            await oracle.close()

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1) from None

    console.print()

    # Output as JSON
    if output_json:
        import json

        json_output = {
            "request_id": result.request_id,
            "outcome": result.consensus.outcome.value,
            "confidence": result.consensus.confidence,
            "agreement_ratio": result.consensus.agreement_ratio,
            "source_count": len(result.merged_sources),
            "ipfs_cid": result.ipfs_cid,
            "consensus_reached": result.consensus.reached,
        }
        console.print_json(data=json_output)

        if save_to:
            with open(save_to, "w") as f:
                json.dump(json_output, f, indent=2)
            console.print(f"\n[green]Saved to {save_to}[/green]")

        return

    # Display result
    outcome_color = {
        "YES": "green",
        "NO": "red",
        "UNDETERMINED": "yellow",
    }.get(result.consensus.outcome.value, "white")

    consensus_status = "✅ Consensus Reached" if result.consensus.reached else "⚠️ No Consensus"

    console.print(
        Panel.fit(
            f"[bold {outcome_color}]{consensus_status}[/bold {outcome_color}]",
        )
    )

    # Results table
    table = Table(show_header=False, box=None)
    table.add_column("Label", style="bold")
    table.add_column("Value")

    table.add_row(
        "Outcome", f"[bold {outcome_color}]{result.consensus.outcome.value}[/bold {outcome_color}]"
    )
    table.add_row("Confidence", f"{result.consensus.confidence:.1%}")
    table.add_row(
        "Agreement",
        f"{result.consensus.agreement_ratio:.0%} ({len([r for r in result.agent_results if r.outcome == result.consensus.outcome])}/{len(result.agent_results)} agents)",
    )
    table.add_row("Total Sources", str(len(result.merged_sources)))
    if result.ipfs_cid:
        table.add_row("IPFS Hash", result.ipfs_cid)

    console.print(table)
    console.print()

    # Agent results
    console.print("[bold]Agent Results:[/bold]")
    for agent_result in result.agent_results:
        agent_outcome_color = {
            "YES": "green",
            "NO": "red",
            "UNDETERMINED": "yellow",
        }.get(agent_result.outcome.value, "white")

        status = "✓" if agent_result.error is None else "✗"
        console.print(
            f"  {status} {agent_result.agent_id}: "
            f"[{agent_outcome_color}]{agent_result.outcome.value}[/{agent_outcome_color}] "
            f"({agent_result.confidence:.0%}, {len(agent_result.sources)} sources)"
        )

    console.print()

    # Top sources
    if result.merged_sources:
        console.print("[bold]Top Sources:[/bold]")
        for i, source in enumerate(result.merged_sources[:10], 1):
            cited_count = len(source.cited_by)
            console.print(f"  {i}. {source.title[:60]}...")
            console.print(f"     [dim]{source.url}[/dim]")
            console.print(
                f"     [dim]Category: {source.category.value}, Cited by: {cited_count} agents[/dim]"
            )

    console.print()

    if save_to:
        import json

        with open(save_to, "w") as f:
            json.dump(result.model_dump(), f, indent=2, default=str)
        console.print(f"[green]Full result saved to {save_to}[/green]")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8090, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """
    Start the Oracle API server.

    Example:
        oracle serve --port 8090
    """
    import uvicorn

    from oracle.api.server import create_app

    console.print()
    console.print(
        Panel.fit(
            f"[bold blue]Host:[/bold blue] {host}\n"
            f"[bold blue]Port:[/bold blue] {port}\n"
            f"[bold blue]Docs:[/bold blue] http://{host}:{port}/docs",
            title="🚀 Starting Oracle API Server",
        )
    )
    console.print()

    if reload:
        uvicorn.run(
            "oracle.api.server:create_app",
            host=host,
            port=port,
            reload=True,
            factory=True,
        )
    else:
        app = create_app()
        uvicorn.run(app, host=host, port=port)


@app.command()
def config():
    """
    Show current configuration.
    """
    import os

    table = Table(title="Oracle Configuration")
    table.add_column("Setting", style="bold")
    table.add_column("Value")
    table.add_column("Source")

    config_items = [
        ("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""), "env"),
        ("WEB3_STORAGE_TOKEN", os.getenv("WEB3_STORAGE_TOKEN", ""), "env"),
        (
            "SOLANA_RPC_URL",
            os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"),
            "env",
        ),
        ("MIN_AGENTS", os.getenv("MIN_AGENTS", "3"), "env"),
        ("CONSENSUS_THRESHOLD", os.getenv("CONSENSUS_THRESHOLD", "0.67"), "env"),
    ]

    for name, value, source in config_items:
        display_value = "***" if "KEY" in name or "TOKEN" in name else value
        status = "✓" if value else "✗"
        table.add_row(f"{status} {name}", display_value or "[dim]not set[/dim]", source)

    console.print(table)


@app.command()
def version():
    """
    Show version information.
    """
    from oracle import __version__

    console.print(f"[bold]1024 Multi-Agent Deep Research Oracle[/bold] v{__version__}")
    console.print("[dim]Powered by Google Gemini Deep Research API[/dim]")


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
