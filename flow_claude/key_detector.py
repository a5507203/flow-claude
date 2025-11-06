"""
Platform-Specific ESC Key Detection

Provides cross-platform ESC key detection in background thread:
- Windows: msvcrt.kbhit() and msvcrt.getch()
- Unix/Linux/Mac: termios + select
"""

import sys
import threading
from typing import Optional


def start_esc_listener(interrupt_flag: threading.Event, stop_flag: threading.Event) -> threading.Thread:
    """
    Start background thread to listen for ESC key presses.

    Args:
        interrupt_flag: Event to set when ESC is pressed
        stop_flag: Event to check for shutdown signal

    Returns:
        Thread object running the listener
    """
    if sys.platform == 'win32':
        listener_fn = _windows_esc_listener
    else:
        listener_fn = _unix_esc_listener

    thread = threading.Thread(
        target=listener_fn,
        args=(interrupt_flag, stop_flag),
        daemon=True,
        name='ESC-Listener'
    )
    thread.start()
    return thread


def _windows_esc_listener(interrupt_flag: threading.Event, stop_flag: threading.Event):
    """
    Windows ESC detection using msvcrt.

    Monitors keyboard input in background without blocking.
    Sets interrupt_flag when ESC (0x1b) is detected.
    """
    try:
        import msvcrt
    except ImportError:
        print("Warning: msvcrt not available on this platform")
        return

    while not stop_flag.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'\x1b':  # ESC key
                interrupt_flag.set()

        # Small sleep to avoid busy loop
        stop_flag.wait(0.1)


def _unix_esc_listener(interrupt_flag: threading.Event, stop_flag: threading.Event):
    """
    Unix/Linux/Mac ESC detection using termios and select.

    Sets terminal to raw mode temporarily to read single characters.
    Restores terminal settings when done.
    """
    try:
        import termios
        import tty
        import select
    except ImportError:
        print("Warning: termios/tty/select not available on this platform")
        return

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        # Set terminal to raw mode (read single chars without Enter)
        tty.setraw(fd)

        while not stop_flag.is_set():
            # Check if input available (non-blocking with 0.1s timeout)
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)

            if ready:
                ch = sys.stdin.read(1)
                if ch == '\x1b':  # ESC key
                    interrupt_flag.set()

    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
