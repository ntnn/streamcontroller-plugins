"""Volume plugin: wpctl volume/mute actions with pw-dump-driven state."""

from src.backend.DeckManagement.InputIdentifier import Input
from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport
from src.backend.PluginManager.EventHolder import EventHolder
from src.backend.PluginManager.PluginBase import PluginBase

from . import wp
from .actions.MuteMic.MuteMic import MuteMic
from .actions.MuteSink.MuteSink import MuteSink
from .actions.Volume.Volume import Volume

EVENT_SUFFIXES = {"sink": "SinkChanged", "source": "SourceChanged"}


class VolumePlugin(PluginBase):
    """Registers actions and events, tracks node state via wp.Monitor."""

    def __init__(self):
        super().__init__()

        # Last known state per target, for redraws without waiting on events.
        self.states: dict[str, wp.NodeState | None] = {
            "sink": None,
            "source": None,
        }

        self.add_action_holder(ActionHolder(
            plugin_base=self,
            action_core=Volume,
            action_id_suffix="Volume",
            action_name="Volume",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.SUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNSUPPORTED,
            },
        ))
        self.add_action_holder(ActionHolder(
            plugin_base=self,
            action_core=MuteMic,
            action_id_suffix="MuteMic",
            action_name="Mute Microphone",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.SUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNSUPPORTED,
            },
        ))
        self.add_action_holder(ActionHolder(
            plugin_base=self,
            action_core=MuteSink,
            action_id_suffix="MuteSink",
            action_name="Mute Output",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.SUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNSUPPORTED,
            },
        ))

        for suffix in EVENT_SUFFIXES.values():
            self.add_event_holder(EventHolder(
                plugin_base=self,
                event_id_suffix=suffix,
            ))

        self.register()

        self.monitor = wp.Monitor(on_change=self._on_change, logger=self.logger)
        self.monitor.start()

    def event_id(self, target: str) -> str:
        """Full event id for target's change event."""
        return f"{self.get_plugin_id()}::{EVENT_SUFFIXES[target]}"

    def _on_change(self, target: str, state: wp.NodeState | None):
        self.states[target] = state
        self.event_holders[self.event_id(target)].trigger_event(state)
