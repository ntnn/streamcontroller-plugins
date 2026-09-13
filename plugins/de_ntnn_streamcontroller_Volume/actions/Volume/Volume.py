from GtkHelper.ComboRow import SimpleComboRowItem
from GtkHelper.GenerativeUI.ComboRow import ComboRow
from GtkHelper.GenerativeUI.SpinRow import SpinRow
from src.backend.DeckManagement.InputIdentifier import Input
from src.backend.PluginManager.ActionCore import ActionCore
from src.backend.PluginManager.EventAssigner import EventAssigner

from ... import render, wp
from ..wpctl import run_or_show_error


class Volume(ActionCore):
    """Adjust volume and toggle mute of the default sink or source."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Stable per-instance callbacks so disconnect matches connect.
        # Plain defs, not functools.partial: EventHolder reads callback.__name__.
        self._event_cbs = {
            target: self._make_event_cb(target)
            for target in wp.TARGETS
        }

        self.add_event_assigner(EventAssigner(
            id="volume_up",
            ui_label="Volume up",
            default_events=[Input.Dial.Events.TURN_CW],
            callback=self._on_volume_up,
        ))
        self.add_event_assigner(EventAssigner(
            id="volume_down",
            ui_label="Volume down",
            default_events=[Input.Dial.Events.TURN_CCW],
            callback=self._on_volume_down,
        ))
        self.add_event_assigner(EventAssigner(
            id="toggle_mute",
            ui_label="Toggle mute",
            default_events=[Input.Key.Events.DOWN, Input.Dial.Events.DOWN],
            callback=self._on_toggle_mute,
        ))

    def on_ready(self):
        for target in wp.TARGETS:
            self.plugin_base.connect_to_event(
                callback=self._event_cbs[target],
                event_id=self.plugin_base.event_id(target),
            )
        self._draw()

    def on_remove(self):
        self._disconnect()

    def on_removed_from_cache(self):
        self._disconnect()

    def get_config_rows(self):
        ComboRow(
            action_core=self,
            var_name="target",
            default_value="sink",
            items=[
                SimpleComboRowItem("sink", "Output (sink)"),
                SimpleComboRowItem("source", "Microphone (source)"),
            ],
            title="Target",
            on_change=lambda *_: self._draw(),
        )
        SpinRow(
            action_core=self,
            var_name="step",
            default_value=5,
            min=1,
            max=25,
            step=1,
            digits=0,
            title="Step (%)",
        )
        SpinRow(
            action_core=self,
            var_name="limit",
            default_value=100,
            min=10,
            max=150,
            step=5,
            digits=0,
            title="Volume limit (%)",
        )
        return self.get_generative_ui_widgets()

    def _target(self) -> str:
        return self.get_settings().get("target", "sink")

    def _disconnect(self):
        for target in wp.TARGETS:
            self.plugin_base.disconnect_from_event(
                event_id=self.plugin_base.event_id(target),
                callback=self._event_cbs[target],
            )

    def _make_event_cb(self, target: str):
        def on_target_event(event_id, state):
            if target == self._target():
                self._draw(state)
        return on_target_event

    def _on_volume_up(self, data):
        self._adjust(+1)

    def _on_volume_down(self, data):
        self._adjust(-1)

    def _adjust(self, direction: int):
        settings = self.get_settings()
        step = settings.get("step", 5)
        limit = settings.get("limit", 100)
        run_or_show_error(self, wp.volume_argv(
            wp.TARGETS[self._target()], direction * step, limit))

    def _on_toggle_mute(self, data):
        run_or_show_error(self, wp.mute_toggle_argv(wp.TARGETS[self._target()]))

    def _draw(self, state: wp.NodeState | None = None):
        if self.get_is_multi_action():
            return
        if state is None:
            state = self.plugin_base.states.get(self._target())
        volume = None if state is None else state.volume
        muted = False if state is None else state.muted

        if isinstance(self.input_ident, Input.Dial):
            self.set_media(image=render.volume_bar(volume, muted=muted))
        else:
            icon = render.mic_icon if self._target() == "source" else render.speaker_icon
            self.set_media(image=icon(muted=None if state is None else muted))
        label = "?" if volume is None else f"{round(volume * 100)}%"
        self.set_bottom_label(label)
