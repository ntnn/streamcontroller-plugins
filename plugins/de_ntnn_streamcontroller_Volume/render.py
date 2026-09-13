"""PIL rendering for volume bar and speaker/mic icons.

Pure PIL; no StreamController imports so it stays unit-testable.
"""

from PIL import Image, ImageDraw

Color = tuple[int, int, int, int]

BG: Color = (0, 0, 0, 255)
FG: Color = (255, 255, 255, 255)
ACCENT: Color = (66, 133, 244, 255)
MUTED: Color = (219, 68, 55, 255)
UNKNOWN: Color = (128, 128, 128, 255)


def volume_bar(volume: float | None, *, muted: bool = False,
               size: tuple[int, int] = (200, 100)) -> Image.Image:
    """Horizontal bar filled to volume (0..1+).

    Red when muted, gray outline when volume is None.
    """
    w, h = size
    img = Image.new("RGBA", size, BG)
    d = ImageDraw.Draw(img)

    margin = w // 10
    bar_h = h // 4
    top = (h - bar_h) // 2
    left, right = margin, w - margin
    radius = bar_h // 2

    outline = UNKNOWN if volume is None else FG
    d.rounded_rectangle([left, top, right, top + bar_h],
                        radius=radius, outline=outline, width=2)
    if volume is not None and volume > 0:
        fill = MUTED if muted else ACCENT
        fill_right = left + max(radius * 2, round((right - left) * min(volume, 1.0)))
        d.rounded_rectangle([left, top, fill_right, top + bar_h],
                            radius=radius, fill=fill)
    return img


def speaker_icon(*, muted: bool | None,
                 size: tuple[int, int] = (96, 96)) -> Image.Image:
    """Speaker icon; slashed red when muted, gray when muted is None."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w, h = size
    color = _state_color(muted=muted)
    lw = max(2, w // 24)

    # Speaker body: rect + triangle cone.
    d.polygon([
        (w * 0.15, h * 0.38), (w * 0.32, h * 0.38),
        (w * 0.52, h * 0.20), (w * 0.52, h * 0.80),
        (w * 0.32, h * 0.62), (w * 0.15, h * 0.62),
    ], fill=color)
    if muted:
        _slash(d, size, lw)
    else:
        d.arc([w * 0.55, h * 0.30, w * 0.75, h * 0.70],
              start=-60, end=60, fill=color, width=lw)
        d.arc([w * 0.60, h * 0.18, w * 0.92, h * 0.82],
              start=-60, end=60, fill=color, width=lw)
    return img


def mic_icon(*, muted: bool | None,
             size: tuple[int, int] = (96, 96)) -> Image.Image:
    """Microphone icon; slashed red when muted, gray when muted is None."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w, h = size
    color = _state_color(muted=muted)
    lw = max(2, w // 24)

    # Capsule + cradle arc + stand.
    d.rounded_rectangle([w * 0.40, h * 0.12, w * 0.60, h * 0.55],
                        radius=w * 0.10, fill=color)
    d.arc([w * 0.28, h * 0.30, w * 0.72, h * 0.68],
          start=0, end=180, fill=color, width=lw)
    d.line([w * 0.50, h * 0.68, w * 0.50, h * 0.80], fill=color, width=lw)
    d.line([w * 0.36, h * 0.82, w * 0.64, h * 0.82], fill=color, width=lw)
    if muted:
        _slash(d, size, lw)
    return img


def _state_color(*, muted: bool | None) -> Color:
    if muted is None:
        return UNKNOWN
    return MUTED if muted else FG


def _slash(d: ImageDraw.ImageDraw, size: tuple[int, int], lw: int) -> None:
    w, h = size
    d.line([w * 0.15, h * 0.15, w * 0.85, h * 0.85], fill=MUTED, width=lw * 2)
