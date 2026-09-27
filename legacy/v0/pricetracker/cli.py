import typer
import asyncio
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from pricetracker.core.runner import JobRunner

app = typer.Typer()
logging.basicConfig(level=logging.INFO)

@app.command()
def run(
    site: Optional[str] = typer.Option(None, help="Filter by site name"),
    product: Optional[str] = typer.Option(None, help="Filter by product name"),
    config: str = typer.Option("config.yaml", help="Path to config file")
):
    """
    Run the price tracker job.
    """
    runner = JobRunner(config_path=config)
    asyncio.run(runner.run(site_name=site, product_name=product))

@app.command()
def history():
    """
    Show recent price history (placeholder).
    """
    # TODO: Implement history view
    typer.echo("History feature coming soon.")

if __name__ == "__main__":
    app()
