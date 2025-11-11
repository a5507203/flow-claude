"""
Flow CLI Entry Point

Simple interactive CLI for Flow-Claude development sessions.
Just type `flow` to start an interactive session.
"""

import asyncio
import click


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
              help='Use Textual UI instead of SimpleCLI')
def main(model, max_parallel, verbose, debug, textual):
    """
    Flow-Claude Interactive CLI

    Launch an interactive development session where you can:
    - Enter development requests
    - See real-time execution progress
    - Press 'q' to quit, ESC to interrupt
    """
    if textual:
        # Use Textual UI
        from flow_claude.textual_cli import FlowCLI
        app = FlowCLI(
            model=model,
            max_parallel=max_parallel,
            verbose=verbose,
            debug=debug
        )
        app.run()
    else:
        # Use SimpleCLI (default)
        from flow_claude.cli_controller import SimpleCLI
        cli = SimpleCLI(
            model=model,
            max_parallel=max_parallel,
            verbose=verbose,
            debug=debug
        )
        try:
            asyncio.run(cli.run())
        except KeyboardInterrupt:
            print("\n\nExiting...")


if __name__ == '__main__':
    main()
