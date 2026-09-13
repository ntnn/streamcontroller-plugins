# Untestable glue by design: imports StreamController for error surfacing.

"""Run wpctl for an action, surfacing failures on the key."""

from src.backend.PluginManager.ActionCore import ActionCore

from .. import wp


def run_or_show_error(action: ActionCore, argv: list[str]) -> None:
    """Run wpctl argv; log and flash the action on failure."""
    result = wp.run(argv)
    if result.returncode != 0:
        action.plugin_base.logger.error(f"wpctl failed: {result.stderr}")
        action.show_error(duration=2)
