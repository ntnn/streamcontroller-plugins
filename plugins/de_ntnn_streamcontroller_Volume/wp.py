"""wpctl control and pw-dump -m monitoring for default audio nodes.

Pure stdlib; no StreamController imports so it stays unit-testable.
"""

import json
import logging
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SINK = "@DEFAULT_AUDIO_SINK@"
DEFAULT_SOURCE = "@DEFAULT_AUDIO_SOURCE@"

TARGETS = {"sink": DEFAULT_SINK, "source": DEFAULT_SOURCE}

_METADATA_KEYS = {
    "default.audio.sink": "sink",
    "default.audio.source": "source",
}
_MEDIA_CLASSES = {
    "Audio/Sink": "sink",
    "Audio/Source": "source",
}

# Seconds between pw-dump -m restarts after it exits.
RESTART_DELAY = 5.0


def is_flatpak() -> bool:
    """Whether running inside a flatpak sandbox."""
    return Path("/.flatpak-info").is_file()


def host_argv(argv: list[str], *, flatpak: bool | None = None) -> list[str]:
    """Prefix argv with flatpak-spawn --host when sandboxed."""
    if flatpak is None:
        flatpak = is_flatpak()
    if flatpak:
        return ["flatpak-spawn", "--host", *argv]
    return argv


def volume_argv(target: str, delta_pct: float, limit_pct: float) -> list[str]:
    """Build wpctl argv adjusting target volume by delta_pct, capped at limit_pct."""
    suffix = "+" if delta_pct >= 0 else "-"
    return [
        "wpctl", "set-volume",
        "-l", f"{limit_pct / 100:.2f}",
        target,
        f"{abs(delta_pct):g}%{suffix}",
    ]


def mute_toggle_argv(target: str) -> list[str]:
    """Build wpctl argv toggling target mute."""
    return ["wpctl", "set-mute", target, "toggle"]


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run argv on the host, capturing output."""
    return subprocess.run(
        host_argv(argv),
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        # Sandbox cwd does not exist on host for flatpak-spawn --host.
        cwd=Path.home(),
    )


@dataclass(frozen=True)
class NodeState:
    """Volume and mute of one audio node."""

    volume: float  # 0..1+ cubic scale, matches wpctl display
    muted: bool


class JSONStream:
    """Incremental splitter for concatenated JSON values (pw-dump -m output).

    Tracks bracket depth outside strings so each char is scanned once.
    """

    def __init__(self) -> None:
        self._buf: list[str] = []
        self._depth = 0
        self._in_string = False
        self._escape = False
        self._started = False

    def feed(self, text: str) -> list[object]:
        """Consume text; returns complete top-level JSON values parsed so far."""
        values: list[object] = []
        for ch in text:
            if self._started:
                self._buf.append(ch)
            if self._in_string:
                if self._escape:
                    self._escape = False
                elif ch == "\\":
                    self._escape = True
                elif ch == '"':
                    self._in_string = False
                continue
            if ch == '"':
                self._in_string = True
            elif ch in "[{":
                if not self._started:
                    self._started = True
                    self._buf.append(ch)
                self._depth += 1
            elif ch in "]}":
                self._depth -= 1
                if self._depth == 0 and self._started:
                    values.append(json.loads("".join(self._buf)))
                    self._buf = []
                    self._started = False
        return values


@dataclass(slots=True)
class _Node:
    """Partial audio node accumulated from pw-dump updates."""

    kind: str | None = None
    name: str | None = None
    volume: float | None = None
    muted: bool | None = None


class State:
    """Default sink/source names and node volume/mute from pw-dump arrays."""

    def __init__(self) -> None:
        self._defaults: dict[str, str] = {}
        self._nodes: dict[int, _Node] = {}
        self._default_meta_id: int | None = None

    def feed(self, objects: list[object]) -> set[str]:
        """Merge objects; returns targets ("sink"/"source") whose state changed."""
        before = {t: self.get(t) for t in TARGETS}
        for obj in objects:
            if isinstance(obj, dict):
                self._merge(obj)
        return {t for t in TARGETS if self.get(t) != before[t]}

    def get(self, target: str) -> NodeState | None:
        """State of the default node for target, None while unknown."""
        name = self._defaults.get(target)
        if name is None:
            return None
        for node in self._nodes.values():
            if (node.name == name and node.kind == target
                    and node.volume is not None and node.muted is not None):
                return NodeState(node.volume, node.muted)
        return None

    def _merge(self, obj: dict) -> None:
        obj_id = obj.get("id")
        if obj_id is None:
            return
        info = obj.get("info")
        if "info" in obj and info is None:
            self._nodes.pop(obj_id, None)
            if obj_id == self._default_meta_id:
                self._default_meta_id = None
            return

        if (obj.get("type") == "PipeWire:Interface:Metadata"
                and obj.get("props", {}).get("metadata.name") == "default"):
            self._default_meta_id = obj_id
        if obj_id == self._default_meta_id:
            self._merge_metadata(obj.get("metadata") or [])
            return

        if obj.get("type") == "PipeWire:Interface:Node" or obj_id in self._nodes:
            self._merge_node(obj_id, info or {})

    def _merge_metadata(self, entries: list) -> None:
        for entry in entries:
            target = _METADATA_KEYS.get(entry.get("key"))
            if target is None:
                continue
            value = entry.get("value")
            if isinstance(value, dict) and "name" in value:
                self._defaults[target] = value["name"]
            else:
                self._defaults.pop(target, None)

    def _merge_node(self, obj_id: int, info: dict) -> None:
        props = info.get("props") or {}
        kind = _MEDIA_CLASSES.get(props.get("media.class"))
        if kind is None and obj_id not in self._nodes:
            return
        node = self._nodes.setdefault(obj_id, _Node())
        if kind is not None:
            node.kind = kind
        if "node.name" in props:
            node.name = props["node.name"]
        for param in (info.get("params") or {}).get("Props", []):
            if "channelVolumes" in param:
                raw = max(param["channelVolumes"], default=0.0)
                node.volume = raw ** (1 / 3)
            if "mute" in param:
                node.muted = param["mute"]


class Monitor:
    """Watches pw-dump -m in a thread.

    Calls on_change(target, NodeState | None) on default sink/source changes.
    """

    def __init__(
        self,
        on_change: Callable[[str, "NodeState | None"], None],
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._on_change = on_change
        self._logger = logger
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen[str] | None = None
        # Guards _proc against stop() racing _watch's Popen setup.
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the monitor thread. Restart after stop() is unsupported."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="wp-monitor")
        self._thread.start()

    def stop(self) -> None:
        """Stop the monitor thread and terminate pw-dump."""
        self._stop.set()
        with self._lock:
            if self._proc is not None:
                self._proc.terminate()

    def _log(self, msg: str) -> None:
        if self._logger is not None:
            self._logger.warning(msg)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._watch()
            except OSError as e:
                self._log(f"pw-dump failed: {e}")
            except json.JSONDecodeError as e:
                # Restart resyncs from a fresh initial dump.
                self._log(f"pw-dump output unparsable: {e}")
            if self._stop.wait(RESTART_DELAY):
                return
            self._log("pw-dump exited, restarting")

    def _watch(self) -> None:
        # Fresh state per subprocess: initial dump resyncs everything.
        state = State()
        stream = JSONStream()
        proc = subprocess.Popen(
            host_argv(["pw-dump", "-m"]),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            # Sandbox cwd does not exist on host for flatpak-spawn --host.
            cwd=Path.home(),
        )
        with self._lock:
            self._proc = proc
            if self._stop.is_set():
                # stop() ran before _proc was set; its terminate was missed.
                proc.terminate()
        assert proc.stdout is not None  # stdout=PIPE guarantees a pipe
        try:
            # readline instead of iteration: iteration read-ahead
            # blocks on pipes until its buffer fills.
            for line in iter(proc.stdout.readline, ""):
                for value in stream.feed(line):
                    if not isinstance(value, list):
                        continue
                    for target in state.feed(value):
                        self._on_change(target, state.get(target))
        finally:
            proc.kill()
            proc.wait()
            with self._lock:
                self._proc = None
