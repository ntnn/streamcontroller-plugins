import json

import pytest
from de_ntnn_streamcontroller_Volume import wp


def meta_obj(entries, obj_id=40):
    return {
        "id": obj_id,
        "type": "PipeWire:Interface:Metadata",
        "props": {"metadata.name": "default"},
        "metadata": entries,
    }


def default_entry(target, name):
    key = f"default.audio.{'sink' if target == 'sink' else 'source'}"
    value = None if name is None else {"name": name}
    return {"subject": 0, "key": key, "type": "Spa:String:JSON", "value": value}


def node_obj(obj_id, name, media_class, volumes=None, mute=None):
    params = {}
    props_param = {}
    if volumes is not None:
        props_param["channelVolumes"] = volumes
    if mute is not None:
        props_param["mute"] = mute
    if props_param:
        params["Props"] = [props_param]
    return {
        "id": obj_id,
        "type": "PipeWire:Interface:Node",
        "info": {
            "props": {"node.name": name, "media.class": media_class},
            "params": params,
        },
    }


@pytest.mark.parametrize(
    ("target", "delta", "limit", "expected"),
    [
        pytest.param(
            wp.DEFAULT_SINK, 5, 100,
            ["wpctl", "set-volume", "-l", "1.00",
             "@DEFAULT_AUDIO_SINK@", "5%+"],
            id="up",
        ),
        pytest.param(
            wp.DEFAULT_SOURCE, -10, 150,
            ["wpctl", "set-volume", "-l", "1.50",
             "@DEFAULT_AUDIO_SOURCE@", "10%-"],
            id="down with limit",
        ),
    ],
)
def test_volume_argv(target, delta, limit, expected):
    assert wp.volume_argv(target, delta, limit) == expected


def test_mute_toggle_argv():
    assert wp.mute_toggle_argv(wp.DEFAULT_SINK) == [
        "wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle",
    ]


@pytest.mark.parametrize(
    ("flatpak", "expected"),
    [
        pytest.param(True, ["flatpak-spawn", "--host", "wpctl"], id="flatpak"),
        pytest.param(False, ["wpctl"], id="native"),
    ],
)
def test_host_argv(flatpak, expected):
    assert wp.host_argv(["wpctl"], flatpak=flatpak) == expected


def test_jsonstream_single_value():
    s = wp.JSONStream()
    assert s.feed('[{"id": 1}]') == [[{"id": 1}]]


def test_jsonstream_split_across_feeds():
    s = wp.JSONStream()
    assert s.feed('[{"id"') == []
    assert s.feed(": 1}]") == [[{"id": 1}]]


def test_jsonstream_multiple_values():
    s = wp.JSONStream()
    assert s.feed("[1]\n[2]") == [[1], [2]]


def test_jsonstream_invalid_json_raises():
    # Locks in the raise Monitor._run relies on to restart pw-dump.
    s = wp.JSONStream()
    with pytest.raises(json.JSONDecodeError):
        s.feed("[nope]")


def test_state_default_sink_volume():
    s = wp.State()
    changed = s.feed([
        meta_obj([default_entry("sink", "spkr")]),
        node_obj(50, "spkr", "Audio/Sink", volumes=[0.125, 0.125], mute=False),
    ])
    assert changed == {"sink"}
    state = s.get("sink")
    assert state.volume == pytest.approx(0.5)
    assert state.muted is False


def test_state_incomplete_node_not_reported():
    s = wp.State()
    s.feed([meta_obj([default_entry("sink", "spkr")])])
    assert s.get("sink") is None


def test_state_mute_update_changes_state():
    s = wp.State()
    s.feed([
        meta_obj([default_entry("source", "mic")]),
        node_obj(60, "mic", "Audio/Source", volumes=[1.0], mute=False),
    ])
    changed = s.feed([node_obj(60, "mic", "Audio/Source", mute=True)])
    assert changed == {"source"}
    assert s.get("source").muted is True


def test_state_unrelated_node_no_change():
    s = wp.State()
    s.feed([
        meta_obj([default_entry("sink", "spkr")]),
        node_obj(50, "spkr", "Audio/Sink", volumes=[1.0], mute=False),
    ])
    changed = s.feed([
        node_obj(51, "other", "Audio/Sink", volumes=[0.5], mute=True),
    ])
    assert changed == set()


def test_state_default_switch():
    s = wp.State()
    s.feed([
        meta_obj([default_entry("sink", "a")]),
        node_obj(50, "a", "Audio/Sink", volumes=[1.0], mute=False),
        node_obj(51, "b", "Audio/Sink", volumes=[0.125], mute=True),
    ])
    changed = s.feed([meta_obj([default_entry("sink", "b")])])
    assert changed == {"sink"}
    assert s.get("sink").muted is True


def test_state_node_removal():
    s = wp.State()
    s.feed([
        meta_obj([default_entry("sink", "spkr")]),
        node_obj(50, "spkr", "Audio/Sink", volumes=[1.0], mute=False),
    ])
    changed = s.feed([{"id": 50, "info": None}])
    assert changed == {"sink"}
    assert s.get("sink") is None


def test_state_metadata_key_cleared():
    s = wp.State()
    s.feed([
        meta_obj([default_entry("sink", "spkr")]),
        node_obj(50, "spkr", "Audio/Sink", volumes=[1.0], mute=False),
    ])
    changed = s.feed([meta_obj([default_entry("sink", None)])])
    assert changed == {"sink"}
    assert s.get("sink") is None


def test_state_partial_metadata_update_keeps_other_target():
    s = wp.State()
    s.feed([
        meta_obj([
            default_entry("sink", "spkr"),
            default_entry("source", "mic"),
        ]),
        node_obj(50, "spkr", "Audio/Sink", volumes=[1.0], mute=False),
        node_obj(60, "mic", "Audio/Source", volumes=[1.0], mute=False),
    ])
    changed = s.feed([meta_obj([default_entry("source", "mic2")])])
    assert changed == {"source"}
    assert s.get("sink") is not None
