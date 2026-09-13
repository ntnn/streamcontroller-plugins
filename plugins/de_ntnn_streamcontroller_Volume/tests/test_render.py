import pytest
from de_ntnn_streamcontroller_Volume import render


def pixels(img):
    if hasattr(img, "get_flattened_data"):
        return list(img.get_flattened_data())
    return list(img.getdata())


def test_volume_bar_size():
    img = render.volume_bar(0.5)
    assert img.size == (200, 100)


def test_volume_bar_fill_grows_with_volume():
    low = render.volume_bar(0.1)
    high = render.volume_bar(0.9)
    accent = render.ACCENT

    def filled(img):
        return sum(1 for px in pixels(img) if px == accent)

    assert filled(high) > filled(low)


def test_volume_bar_muted_uses_muted_color():
    img = render.volume_bar(0.5, muted=True)
    assert render.MUTED in pixels(img)
    assert render.ACCENT not in pixels(img)


def test_volume_bar_unknown_has_no_fill():
    img = render.volume_bar(None)
    data = pixels(img)
    assert render.ACCENT not in data
    assert render.MUTED not in data


@pytest.mark.parametrize(
    "icon",
    [
        pytest.param(render.speaker_icon, id="speaker"),
        pytest.param(render.mic_icon, id="mic"),
    ],
)
@pytest.mark.parametrize(
    "muted",
    [
        pytest.param(None, id="unknown"),
        pytest.param(False, id="unmuted"),
        pytest.param(True, id="muted"),
    ],
)
def test_icons_render(icon, muted):
    img = icon(muted=muted)
    assert img.size == (96, 96)


@pytest.mark.parametrize(
    "icon",
    [
        pytest.param(render.speaker_icon, id="speaker"),
        pytest.param(render.mic_icon, id="mic"),
    ],
)
def test_muted_icons_contain_slash_color(icon):
    assert render.MUTED in pixels(icon(muted=True))
