"""Shared base for mute-toggle actions on a default node."""

from src.backend.DeckManagement.InputIdentifier import Input
from src.backend.PluginManager.ActionCore import ActionCore
from src.backend.PluginManager.EventAssigner import EventAssigner

from .. import render, wp
from .wpctl import run_or_show_error


# Subclass per target: StreamController requires one ActionCore class
# per registered action.
class MuteBase(ActionCore):
    """Mute toggle for the default node of TARGET."""

    TARGET: str  # "sink" or "source"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_event_assigner(EventAssigner(
            id="toggle_mute",
            ui_label="Toggle mute",
            default_events=[Input.Key.Events.DOWN, Input.Dial.Events.DOWN],
            callback=self._on_toggle_mute,
        ))

    def on_ready(self):
        self.plugin_base.connect_to_event(
            callback=self._on_state_changed,
            event_id=self.plugin_base.event_id(self.TARGET),
        )
        self._draw()

    def on_remove(self):
        self._disconnect()

    def on_removed_from_cache(self):
        self._disconnect()

    def _disconnect(self):
        self.plugin_base.disconnect_from_event(
            event_id=self.plugin_base.event_id(self.TARGET),
            callback=self._on_state_changed,
        )

    def _on_state_changed(self, event_id: str, state: wp.NodeState | None):
        self._draw(state)

    def _on_toggle_mute(self, data):
        run_or_show_error(self, wp.mute_toggle_argv(wp.TARGETS[self.TARGET]))

    def _draw(self, state: wp.NodeState | None = None):
        if self.get_is_multi_action():
            return
        if state is None:
            state = self.plugin_base.states.get(self.TARGET)
        muted = None if state is None else state.muted
        icon = render.mic_icon if self.TARGET == "source" else render.speaker_icon
        self.set_media(image=icon(muted=muted))
