#!/usr/bin/env python3
"""Create plan branch with metadata commit."""
import argparse
import asyncio
import json
import subprocess
import sys


def validate_task_detail_length(tasks: list) -> None:
    """Validate that each task_detail has at least 25 words.

    Args:
        tasks: List of task definitions

    Raises:
        ValueError: If any task_detail has fewer than 25 words
    """
    for task in tasks:
        task_detail = task.get('task_detail', '')
        word_count = len(task_detail.split())
        if word_count < 25:
            raise ValueError(
                f"Task {task.get('id', 'unknown')}: task_detail must be at least 25 words, "
                f"but got {word_count} words. Please provide more detailed task description "
                f"including: specific implementation steps, expected behavior, edge cases to handle, "
                f"integration points with other components, and acceptance criteria."
            )


async def create_plan_branch(
    session_name: str,
    user_request: str,
    tasks: list,
    **kwargs
) -> dict:
    """Create plan branch with structured metadata commit.

    Args:
        session_name: Unique session name
        user_request: Original user request
        tasks: List of task definitions
        **kwargs: Optional fields:
            - design_doc: Complete design documentation (architecture, patterns, structure)
            - tech_stack: Technology stack

    Returns:
        Dict with success status
    """
    try:
        branch_name = f"plan/{session_name}"

        # Create branch from flow (without switching)
        subprocess.run(
            ['git', 'branch', branch_name, 'flow'],
            check=True,
            capture_output=True,
            timeout=10
        )

        # Switch to the new branch temporarily for commit
        subprocess.run(
            ['git', 'checkout', branch_name],
            check=True,
            capture_output=True,
            timeout=10
        )

        # Build commit message
        commit_lines = [
            "Initialize execution plan v1",
            "",
            "## Session Information",
            f"Session name: {session_name}",
            f"User Request: {user_request}",
            "Plan Version: v1",
            ""
        ]

        # Add optional sections
        if kwargs.get('design_doc'):
            commit_lines.extend([
                "## Design Doc",
                kwargs['design_doc'],
                ""
            ])

        if kwargs.get('technology_stack'):
            commit_lines.extend([
                "## Technology Stack",
                kwargs['technology_stack'],
                ""
            ])

        # Add tasks
        commit_lines.append("## Tasks")
        for task in tasks:
            depends_on = task.get('depends_on', [])

            commit_lines.extend([
                f"### Task {task['id']}",
                f"ID: {task['id']}",
                f"Task Detail: {task['task_detail']}",
                f"Depends on: {', '.join(depends_on) if depends_on else 'None'}",
                ""
            ])

        commit_message = '\n'.join(commit_lines)

        # Create empty commit
        subprocess.run(
            ['git', 'commit', '--allow-empty', '-m', commit_message],
            check=True,
            capture_output=True,
            timeout=10
        )

        # Switch back to flow branch
        subprocess.run(
            ['git', 'checkout', 'flow'],
            check=True,
            capture_output=True,
            timeout=10
        )

        return {
            "success": True,
            "branch": branch_name,
            "session_name": session_name
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git command failed: {e.stderr.decode() if e.stderr else str(e)}",
            "success": False
        }
    except Exception as e:
        return {
            "error": f"Failed to create plan branch: {str(e)}",
            "success": False
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Create plan branch with metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Create a plan with task dependencies (DAG)
  # Note: Each task_detail must be at least 25 words
  python -m flow_claude.scripts.create_plan_branch \\
    --session-name="build-conference-website" \\
    --user-request="Build a conference website" \\
    --design-doc="Project Structure: index.html (main page), css/ (styles), js/ (scripts). Design: Modern single-page layout with sticky navigation, hero section, schedule grid, speaker cards. Mobile-first responsive design with breakpoints at 768px and 1024px. Components organized by section (nav, hero, schedule, speakers, footer). Follow BEM naming convention for CSS classes." \\
    --tech-stack="HTML5, CSS3, JavaScript ES6" \\
    --tasks='[{"id":"001","task_detail":"Create semantic HTML structure in index.html with proper document outline and accessibility features. Include DOCTYPE declaration, meta tags for viewport and charset, and link tags for stylesheets. Structure the page with header containing navigation with logo and menu items for Home, Schedule, Speakers, and Register sections. Create main content area with hero section containing conference title, date, location, and call-to-action button. Add schedule section with grid layout placeholder for session cards. Include speakers section with flex container for speaker profile cards. Add footer with copyright, social links, and contact information. Use semantic HTML5 elements including nav, main, section, article, aside, and footer. Ensure all images have alt attributes and form inputs have associated labels for screen reader compatibility.","depends_on":[]},{"id":"002","task_detail":"Implement responsive CSS styling in css/styles.css using mobile-first approach with CSS custom properties for theming. Define color palette variables for primary, secondary, accent, background, and text colors. Set up typography with system font stack and modular scale for headings. Create base styles resetting margins, padding, and box-sizing. Style navigation with flexbox layout, sticky positioning, and hamburger menu for mobile viewports under 768px. Design hero section with background gradient, centered content, and animated call-to-action button with hover effects. Build schedule grid using CSS Grid with auto-fit columns and gap spacing. Style speaker cards with box shadow, border radius, and image object-fit cover. Add responsive breakpoints at 768px for tablet and 1024px for desktop layouts. Include smooth scroll behavior and focus visible states for accessibility.","depends_on":["001"]},{"id":"003","task_detail":"Implement JavaScript functionality in js/main.js for interactive features and dynamic behavior. Create mobile navigation toggle function that adds and removes active class on menu button click, with aria-expanded attribute updates for accessibility. Implement smooth scroll behavior for anchor links with offset calculation to account for sticky header height. Add intersection observer for scroll-triggered animations on section elements with fade-in and slide-up effects. Create countdown timer function displaying days, hours, minutes, and seconds until conference date with automatic updates every second. Implement form validation for registration form with real-time feedback on email format, required fields, and password strength. Add lazy loading for speaker images using intersection observer pattern. Include error handling with try-catch blocks and console logging for debugging. Ensure all event listeners are properly cleaned up on page unload.","depends_on":["001"]},{"id":"004","task_detail":"Perform comprehensive cross-browser and responsive testing of the conference website across multiple devices and browsers. Test on Chrome, Firefox, Safari, and Edge browsers on both Windows and macOS platforms. Verify responsive breakpoints at 320px mobile, 768px tablet, and 1024px desktop viewports using browser developer tools device simulation. Check navigation menu functionality including hamburger toggle on mobile and hover states on desktop. Validate form submission behavior with valid and invalid input combinations. Test smooth scroll anchor links and verify offset calculations for sticky header. Verify countdown timer accuracy and display formatting. Check image lazy loading triggers correctly on scroll. Run Lighthouse audit for performance, accessibility, best practices, and SEO scores targeting minimum 90 in each category. Document any bugs found with screenshots and reproduction steps.","depends_on":["002","003"]}]'

Output:
  JSON with success status and plan branch information
        '''
    )
    parser.add_argument(
        '--session-name',
        type=str,
        required=True,
        metavar='NAME',
        help='Meaningful session name describing the work (e.g., "build-user-authentication", "add-responsive-nav"). Use lowercase with hyphens.'
    )
    parser.add_argument(
        '--user-request',
        type=str,
        required=True,
        metavar='TEXT',
        help='Original user request describing what needs to be built'
    )
    parser.add_argument(
        '--tasks',
        type=str,
        required=True,
        metavar='JSON',
        help='JSON array of task objects. Each task must have: id, task_detail, depends_on (upstream task IDs)'
    )
    parser.add_argument(
        '--design-doc',
        type=str,
        required=True,
        default='',
        metavar='TEXT',
        help='Complete design documentation (can be long, like CLAUDE.md). Should include: architecture overview, how features integrate with existing codebase, project structure, design patterns, architectural decisions, interface contracts. This is worker\'s primary reference document.'
    )
    parser.add_argument(
        '--tech-stack',
        type=str,
        required=True,
        default='',
        metavar='TEXT',
        help='Technology stack: languages, frameworks, libraries, tools (e.g., "Python 3.10, Flask 2.3, SQLAlchemy")'
    )
    args = parser.parse_args()

    # Parse JSON fields
    try:
        tasks = json.loads(args.tasks)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        return 1

    # Validate task_detail length (minimum 25 words)
    try:
        validate_task_detail_length(tasks)
    except ValueError as e:
        print(json.dumps({"success": False, "error": str(e)}))
        return 1

    # Run async function
    result = asyncio.run(create_plan_branch(
        session_name=args.session_name,
        user_request=args.user_request,
        tasks=tasks,
        design_doc=args.design_doc,
        technology_stack=args.tech_stack
    ))

    print(json.dumps(result, indent=2))
    return 0 if result.get('success') else 1


if __name__ == '__main__':
    sys.exit(main())
