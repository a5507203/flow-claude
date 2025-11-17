"""CSS styling and keybindings for Flow-Claude UI."""

from textual.binding import Binding


# CSS styling for FlowCLI app
APP_CSS = """
#main-log {
    height: 1fr;
    background: $surface;
    border: solid $panel;
}

#input-container {
    dock: bottom;
    height: auto;
    background: $surface;
    padding: 0;
}

#input-hint {
    width: 100%;
    height: 1;
    color: $text-muted;
    background: $panel;
    padding: 0 1;
    text-style: italic;
}

#main-input {
    min-height: 3;
    max-height: 20;
    height: auto;
    background: $surface;
    border: solid $panel;
    margin-top: 0;
}

#suggestions {
    width: 100%;
    height: auto;
    max-height: 3;
    color: $accent;
    background: $panel;
    padding: 0 1;
    display: none;
}

#suggestions.visible {
    display: block;
}

#button-row {
    height: auto;
    width: 100%;
    padding: 0 1;
    background: $surface;
}

#submit-button {
    width: 20;
    margin-right: 1;
}
"""


# Keybindings for FlowCLI app
APP_BINDINGS = [
    Binding("ctrl+c", "quit", "Quit", show=True),
    Binding("escape", "interrupt", "Interrupt", show=True),
]
