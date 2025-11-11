"""
Flow CLI Entry Point

Simple interactive CLI for Flow-Claude development sessions.
Just type `flow` to start an interactive session.
"""

import asyncio
import click
from flow_claude.cli_controller import SimpleCLI


@click.command()
@click.option('--model', type=click.Choice(['sonnet', 'opus', 'haiku']), default='sonnet',
              help='Claude model to use (default: sonnet)')
@click.option('--max-parallel', type=int, default=3,
              help='Maximum number of parallel workers (default: 3)')
@click.option('--verbose', is_flag=True,
              help='Enable verbose output')
@click.option('--debug', is_flag=True,
              help='Enable debug mode')
def main(model, max_parallel, verbose, debug):
    """
    Flow-Claude Interactive CLI

    Launch an interactive development session where you can:
    - Enter development requests
    - See real-time execution progress
    - Press 'q' to quit, ESC to add requirements
    """
    cli = SimpleCLI(
        model=model,
        max_parallel=max_parallel,
        verbose=verbose,
        debug=debug
    )

    try:
        # Run async event loop
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        print("\n\nExiting...")


if __name__ == '__main__':
    main()
