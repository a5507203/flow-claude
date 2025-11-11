"""
Flow CLI Entry Point

Simple interactive CLI for Flow-Claude development sessions.
Just type `flow` to start an interactive session.
"""

import asyncio
import sys
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
@click.option('--textual', is_flag=True,
              help='Use Textual TUI instead of plain terminal')
def main(model, max_parallel, verbose, debug, textual):
    """
    Flow-Claude Interactive CLI

    Launch an interactive development session where you can:
    - Enter development requests
    - See real-time execution progress
    - Press 'q' to quit, ESC to add requirements
    """
    if textual:
        # Use Textual TUI
        try:
            from flow_claude.textual_cli import FlowCLI
            app = FlowCLI(
                model=model,
                max_parallel=max_parallel,
                verbose=verbose,
                debug=debug
            )
            try:
                app.run()
            except KeyboardInterrupt:
                print("\n\nExiting...")
        except ImportError as e:
            print(f"ERROR: Textual UI not available: {e}", file=sys.stderr)
            print("Install textual with: pip install textual", file=sys.stderr)
            sys.exit(1)
    else:
        # Use plain terminal CLI
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
