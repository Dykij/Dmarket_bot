from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Log, Static
from textual.containers import Vertical
import os
import time

class DashboardApp(App):
    """A TUI Dashboard for OpenClaw."""
    
    CSS = """
    #status {
        background: $primary;
        color: white;
        text-align: center;
        padding: 1;
        height: 3;
    }

    Log {
        height: 100%;
        border: solid green;
    }
    """

    BINDINGS = [("q", "quit", "Quit"), ("r", "reload", "Reload")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("OpenClaw Operational Dashboard - STATUS: ACTIVE\n[Benjamin Protocol: Engaged]", id="status")
            yield Log(id="log_view", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.log_view = self.query_one(Log)
        # Check logs every second
        self.set_interval(1, self.update_logs)
        self.last_pos = 0
        self.log_file = "logs/openclaw.log" # Assuming this path relative to workspace root

    def update_logs(self) -> None:
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    f.seek(self.last_pos)
                    lines = f.readlines()
                    if lines:
                        for line in lines:
                             self.log_view.write(line.strip())
                        self.last_pos = f.tell()
            except Exception as e:
                self.log_view.write(f"[red]Error reading log: {e}[/]")
        else:
             # Just a heartbeat if no log
             self.log_view.write(f"[{time.strftime('%H:%M:%S')}] [green]System operational.[/] Waiting for log file creation...")

if __name__ == "__main__":
    app = DashboardApp()
    app.run()
