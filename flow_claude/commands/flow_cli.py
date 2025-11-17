"""
Flow CLI Entry Point

Interactive Textual UI for Flow-Claude development sessions.
Just type `flow` to start an interactive session.
"""

import sys
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
def main(model, max_parallel, verbose, debug):
    """
    Flow-Claude Interactive CLI

    Launch an interactive development session where you can:
    - Enter development requests
    - See real-time execution progress
    - Press 'q' to quit, ESC to interrupt, H for help
    """
    try:
        from flow_claude.ui import FlowCLI
        from flow_claude.setup_ui import run_setup_ui
        from flow_claude.cli import setup_instruction_files

        # Run setup UI first (flow branch + CLAUDE.md)
        # Note: CLAUDE.md generation happens inside the UI with progress display
        try:
            setup_results = run_setup_ui()
            # Print summary of what was set up
            if setup_results.get("flow_branch_created"):
                base_branch = setup_results.get('base_branch')
                print(f"\n  ✓ Created 'flow' branch from '{base_branch}'")
            if setup_results.get("claude_md_generated"):
                print("  ✓ CLAUDE.md created and committed to flow branch")

            # Setup instruction files after flow branch is ready
            created_files = setup_instruction_files(debug=debug)
            if created_files:
                print(f"  ✓ Instruction files created in .flow-claude/")

            if setup_results.get("flow_branch_created") or setup_results.get("claude_md_generated") or created_files:
                print()  # Add spacing before main UI only if setup happened
        except Exception as e:
            # If setup UI fails, continue with main UI anyway
            print(f"\n  Warning: Setup UI failed: {e}\n")
            if debug:
                import traceback
                traceback.print_exc()

        # Launch main FlowCLI app
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


if __name__ == '__main__':
    main()
