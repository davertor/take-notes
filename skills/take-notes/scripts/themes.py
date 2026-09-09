#!/usr/bin/env -S uv run --script
"""The themes the gallery and the notes are painted and set in.

A theme is a palette plus a type stack. One closed set, curated by hand; `auto`
is the pair the templates shipped with — Paper in light, Graphite in dark,
chosen by the browser.

    uv run themes.py                 # the theme in force, and the list
    uv run themes.py --set petrol    # write it to ~/take-notes/config.json

**A note carries values, never the catalogue.** `palette_css` resolves one theme
into a single `:root` block, and that is all a rendered note contains — so
adding a theme later can never leave a note on disk stale, because no note ever
claimed to know what themes exist. Every theme shares one structure (the same
token names), which is what lets a note accept a different one at read time:
`payload()` is the value set the gallery hands a note through its link, and the
note applies it without ever learning a name. The gallery is the one file that
carries the whole catalogue (`catalogue_css`), and it is rebuilt on demand.

Read-modify-write like tags.py: every other key in the config is carried
through untouched.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# notes.py is imported inside the functions that touch the config, not at module
# scope: the palette itself has no dependencies, which is what lets render.py —
# the one script that deliberately imports nothing from the rest — pull in css()
# without dragging the note parser along with it.


AUTO = "auto"

# The pair `auto` switches between. Kept as names rather than inlined so the
# relationship survives a rename of either theme.
AUTO_LIGHT = "paper"
AUTO_DARK = "graphite"

# Type stacks a theme can be set in: display face, reading face, label face.
# Single quotes on purpose — these values also travel in an HTML attribute, and
# a double-quoted family name would close it and drop the whole stack.
#
# `families` is what the theme needs from Google Fonts. A note links only its
# own; a theme injected at read time falls back to the generic stack unless the
# gallery hands over its link too, which it does.
STACKS: dict[str, dict[str, str]] = {
    "offprint": {
        "display": "Fraunces, 'Iowan Old Style', Georgia, serif",
        "body": "Newsreader, 'Iowan Old Style', Georgia, serif",
        "ui": "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
        # How the display face is set, not just which one it is. `weight` is the
        # heaviest cut the family actually has — asking for 900 from a family
        # that stops at 700 is what gives you faux bold. `axes` is
        # face-specific: SOFT and WONK exist on Fraunces and nowhere else.
        "weight": "700", "axes": '"SOFT" 40, "WONK" 1', "tracking": "-.02em",
        "label-case": "uppercase", "label-tracking": "1",
        "families": "family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,700;0,9..144,900;1,9..144,500"
                    "&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400"
                    "&family=JetBrains+Mono:wght@400;500",
    },
    "grotesk": {
        "display": "'Space Grotesk', system-ui, sans-serif",
        "body": "'Space Grotesk', system-ui, sans-serif",
        "ui": "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
        # Space Grotesk stops at 700 — the guide's masthead is lighter here by
        # necessity, and saying so beats rendering a synthesised 900.
        "weight": "700", "axes": "normal", "tracking": "-.03em",
        "label-case": "uppercase", "label-tracking": "1",
        "families": "family=Space+Grotesk:wght@400;500;700"
                    "&family=JetBrains+Mono:wght@400;500",
    },
    "didone": {
        "display": "'Bodoni Moda', Didot, 'Bodoni 72', Georgia, serif",
        "body": "Jost, Futura, 'Century Gothic', system-ui, sans-serif",
        "ui": "Jost, Futura, 'Century Gothic', system-ui, sans-serif",
        # A didone wants air, not the tight tracking a Fraunces headline takes.
        "weight": "700", "axes": "normal", "tracking": "0",
        "label-case": "uppercase", "label-tracking": "1",
        "families": "family=Bodoni+Moda:ital,opsz,wght@0,6..96,400;0,6..96,700;0,6..96,900;1,6..96,400"
                    "&family=Jost:wght@400;500;700",
    },
    "hand": {
        "display": "Caveat, 'Bradley Hand', cursive",
        "body": "'Patrick Hand', 'Comic Sans MS', cursive",
        "ui": "Caveat, 'Bradley Hand', cursive",
        # Handwriting has no small-caps register: tracked-out capitals in a
        # script face read as a ransom note, so this stack keeps labels cased
        # as written and drops the letter-spacing.
        "weight": "700", "axes": "normal", "tracking": "0",
        "label-case": "none", "label-tracking": "0",
        "families": "family=Caveat:wght@400;500;700&family=Patrick+Hand",
    },
    "futura": {
        # Wes Anderson sets everything in Futura; the uniformity is half the effect.
        "display": "Jost, Futura, 'Century Gothic', 'Avenir Next', system-ui, sans-serif",
        "body": "Jost, Futura, 'Century Gothic', 'Avenir Next', system-ui, sans-serif",
        "ui": "Jost, Futura, 'Century Gothic', 'Avenir Next', system-ui, sans-serif",
        "weight": "900", "axes": "normal", "tracking": "-.01em",
        "label-case": "uppercase", "label-tracking": "1",
        "families": "family=Jost:wght@400;500;700;900",
    },
}

FONT_TOKENS = ("font-display", "font-body", "font-ui")
# Set from the stack too, but named for the role rather than the face.
TYPE_TOKENS = {
    "display-weight": "weight", "display-axes": "axes", "display-tracking": "tracking",
    # Labels: the mono-caps register is the offprint's voice, but a script face
    # has no capitals worth tracking out. `label-tracking` is a multiplier on
    # each rule's own value, so a stack can mute the whole register with 0
    # without flattening the sizes the templates tuned by hand.
    "label-case": "label-case", "label-tracking": "label-tracking",
}

# The paper's own pattern — printed on the stock, so it sits *behind* the text
# and scrolls with it. (The grain is separate: a fixed overlay above everything,
# and a theme turns it off with `grain: 0` rather than with a texture.)
#
# The pitch matches the body leading, so lines never drift against a paragraph.
# They are deliberately *not* registered to the baseline: that would need every
# margin in the sheet to become a multiple of the pitch, retuning the house
# rhythm for one theme. So the rule is drawn at 55% — it reads as printed stock
# rather than as a line the text failed to sit on. `--rule` stays full strength
# for borders, which need to be seen.
TEXTURES = {
    "none": "none",
    "lines": "repeating-linear-gradient(to bottom, transparent 0 calc(var(--ruled) - 1px),"
             " color-mix(in srgb, var(--rule) 55%, transparent)"
             " calc(var(--ruled) - 1px) var(--ruled))",
    "grid": "repeating-linear-gradient(to bottom, transparent 0 calc(var(--ruled) - 1px),"
            " var(--rule) calc(var(--ruled) - 1px) var(--ruled)),"
            " repeating-linear-gradient(to right, transparent 0 calc(var(--ruled) - 1px),"
            " color-mix(in srgb, var(--rule) 55%, transparent)"
             " calc(var(--ruled) - 1px) var(--ruled))",
}
# Shape: what a theme can say about corners and rules beyond colour.
SHAPE_TOKENS = ("radius", "border")

# Every theme carries the same tokens. `desk` is the surround past the sheet,
# `band` a solid block (a masthead, a footer) with `on-band` the text that sits
# on it, and `mark` a high-chroma highlight that only ever carries `ink`. The
# note templates use none of the last three today; emitting them everywhere
# keeps one code path, and an unused custom property costs nothing.
#
# `ink`, `ink-70`, `ink-45` and `pen` are all WCAG AA (>= 4.5) against their own
# `paper`; `on-band` against `band` and `ink` against `mark` likewise; `mark`
# clears 3:1 against `band` for display text. _selftest asserts all of it. Do
# not lighten them — `field`'s pen is the tightest at 4.58, and it is a darker
# brick than the guide it came from because that orange only ever sat in
# display sizes.
THEMES: dict[str, dict[str, str]] = {
    "paper": {
        "paper": "#f7f3ea", "surface": "#f1ebdf", "raised": "#e8e1d1", "rule": "#d8d0be",
        "ink": "#191511", "ink-70": "#57503f", "ink-45": "#6e6653", "pen": "#ab2f19",
        "desk": "#e6ddc8", "band": "#191511", "on-band": "#f7f3ea", "mark": "#f2c4b5",
        "grain": ".04", "scheme": "light", "stack": "offprint",
        "radius": "0", "border": "1px", "texture": "none",
    },
    "field": {
        "paper": "#f1eadc", "surface": "#ebe2d0", "raised": "#dfd4c0", "rule": "#a99e88",
        "ink": "#152b2a", "ink-70": "#3e5350", "ink-45": "#596661", "pen": "#b8421c",
        "desk": "#d6c9b0", "band": "#07594e", "on-band": "#fffdf7", "mark": "#d9ff68",
        "grain": ".04", "scheme": "light", "stack": "offprint",
        "radius": "0", "border": "1px", "texture": "none",
    },
    "graphite": {
        "paper": "#17150f", "surface": "#1e1b15", "raised": "#262218", "rule": "#38332a",
        "ink": "#efe8d8", "ink-70": "#b3aa94", "ink-45": "#8d8471", "pen": "#f0765a",
        "desk": "#0d0c08", "band": "#efe8d8", "on-band": "#17150f", "mark": "#8a3b25",
        "grain": ".07", "scheme": "dark", "stack": "offprint",
        "radius": "0", "border": "1px", "texture": "none",
    },
    # The ones that do not pretend to be a sheet of paper, each in its own type.
    "acid": {
        "paper": "#0e1400", "surface": "#141c04", "raised": "#1c2708", "rule": "#2f3f14",
        "ink": "#e9ffc4", "ink-70": "#a9c47f", "ink-45": "#889f63", "pen": "#b6ff2b",
        "desk": "#070a00", "band": "#e9ffc4", "on-band": "#0e1400", "mark": "#39520a",
        "grain": "0", "scheme": "dark", "stack": "grotesk",
        "radius": "0", "border": "2px", "texture": "none",
    },
    "barbie": {
        "paper": "#fff0f6", "surface": "#fbe4ee", "raised": "#f6d7e5", "rule": "#eab8d0",
        "ink": "#2d0716", "ink-70": "#7a2748", "ink-45": "#8d3a5c", "pen": "#cf0f6b",
        "desk": "#f5cede", "band": "#cf0f6b", "on-band": "#fff0f6", "mark": "#ffd84d",
        "grain": ".03", "scheme": "light", "stack": "didone",
        "radius": "10px", "border": "1px", "texture": "none",
    },
    "blueprint": {
        "paper": "#0e1a26", "surface": "#132231", "raised": "#1a2c3d", "rule": "#2b4055",
        "ink": "#dfeaf5", "ink-70": "#a6bcd0", "ink-45": "#8aa2b8", "pen": "#5fc9f0",
        "desk": "#080f17", "band": "#dfeaf5", "on-band": "#0e1a26", "mark": "#1d4e6b",
        "grain": ".05", "scheme": "dark", "stack": "offprint",
        "radius": "0", "border": "1px", "texture": "none",
    },
    "bureau": {
        "paper": "#fbfbfa", "surface": "#f2f2f0", "raised": "#e9e9e6", "rule": "#d4d4d0",
        "ink": "#101010", "ink-70": "#4a4a4a", "ink-45": "#5e5e5e", "pen": "#c8102e",
        "desk": "#e4e4e0", "band": "#101010", "on-band": "#fbfbfa", "mark": "#ffd400",
        "grain": "0", "scheme": "light", "stack": "grotesk",
        "radius": "0", "border": "1px", "texture": "none",
    },
    "notebook": {
        "paper": "#fdfcf8", "surface": "#f6f4ed", "raised": "#eeebe1", "rule": "#b9cbe0",
        "ink": "#1b2a4a", "ink-70": "#45536e", "ink-45": "#606c85", "pen": "#c0362c",
        "desk": "#e8e5da", "band": "#1b2a4a", "on-band": "#fdfcf8", "mark": "#ffe97f",
        "grain": ".03", "scheme": "light", "stack": "hand",
        "radius": "0", "border": "1px", "texture": "lines",
    },
    "petrol": {
        "paper": "#f6e3c5", "surface": "#efd9b6", "raised": "#e6cca4", "rule": "#cfb98c",
        "ink": "#29201a", "ink-70": "#57493a", "ink-45": "#75634d", "pen": "#1f6f6b",
        "desk": "#e3c9a0", "band": "#1f6f6b", "on-band": "#f6e3c5", "mark": "#f5c070",
        "grain": ".05", "scheme": "light", "stack": "futura",
        "radius": "2px", "border": "1px", "texture": "none",
    },
}

# Ordered for the menu: light first, then dark, each group as listed above.
NAMES = (AUTO, *THEMES)

COLOUR_TOKENS = (
    "paper", "surface", "raised", "rule", "ink", "ink-70", "ink-45", "pen", "desk",
    "band", "on-band", "mark",
)
# The four that carry text or a mark, and so have to clear AA against `paper`.
CONTRAST_TOKENS = ("ink", "ink-70", "ink-45", "pen")
# (foreground, background, floor) pairs a template may rely on beyond that.
CONTRAST_PAIRS = (
    ("on-band", "band", 4.5),
    ("ink", "mark", 4.5),
    ("mark", "band", 3.0),
    # The poster chip: `paper` on `pen`. It shipped as a literal #fff, which
    # was 2.25:1 on the darkest theme — the one pair nothing was checking.
    ("paper", "pen", 4.5),
)
# The two muted tiers have to be tellable apart, or a theme has two tiers of
# text pretending to be three. The hand-tuned set spans 1.26 to 1.60, so this is
# a floor against collapse, not a target: `petrol` shipped at 1.03, which is one
# colour written twice. Aim for `paper`'s 1.41 when picking new values.
TIER_SEPARATION = 1.2


def _declarations(name: str, indent: str = "  ", scheme: str | None = None) -> str:
    theme = THEMES[name]
    stack = STACKS[theme["stack"]]
    lines = [] if scheme == "" else [f"{indent}color-scheme: {scheme or theme['scheme']};"]
    lines += [f"{indent}--{token}: {theme[token]};" for token in COLOUR_TOKENS]
    lines.append(f"{indent}--grain: {theme['grain']};")
    lines += [f"{indent}--{t}: {stack[t.removeprefix('font-')]};" for t in FONT_TOKENS]
    lines += [f"{indent}--{token}: {stack[key]};" for token, key in TYPE_TOKENS.items()]
    lines += [f"{indent}--{token}: {theme[token]};" for token in SHAPE_TOKENS]
    lines.append(f"{indent}--texture: {TEXTURES[theme['texture']]};")
    return "\n".join(lines)


def resolve(name: str) -> str:
    """A theme name to render with; `auto` and anything unknown stay `auto`."""
    return name if name in THEMES else AUTO


def palette_css(name: str = AUTO) -> str:
    """One theme resolved to values — everything a rendered note carries.

    No catalogue and no theme names: a note holds the colours and faces it was
    rendered with, so a theme added years later cannot leave it stale. `auto` is
    the one case that needs two blocks, because "follow the system" cannot be
    resolved to a single set of values.
    """
    name = resolve(name)
    if name != AUTO:
        return f"/* {name} */\n:root {{\n{_declarations(name)}\n}}"
    return (
        "/* auto — the pair the archive shipped with, chosen by the browser. */\n"
        ":root {\n" + _declarations(AUTO_LIGHT, scheme="light dark") + "\n}\n"
        "@media (prefers-color-scheme: dark) {\n"
        "  :root {\n" + _declarations(AUTO_DARK, "    ", scheme="") + "\n  }\n}"
    )


def fonts_url(name: str = AUTO) -> str:
    """The Google Fonts URL for the faces this theme actually uses."""
    name = resolve(name)
    stacks = (
        {THEMES[AUTO_LIGHT]["stack"], THEMES[AUTO_DARK]["stack"]}
        if name == AUTO else {THEMES[name]["stack"]}
    )
    families = "&".join(sorted({STACKS[s]["families"] for s in stacks}))
    return f"https://fonts.googleapis.com/css2?{families}&display=swap"


def payload(name: str) -> dict[str, str]:
    """The value set the gallery hands a note so it can be read in this theme.

    Values only — the note applies them to the same token names it already uses
    and never learns that a theme called `name` exists. `fonts` rides along so
    an injected theme arrives in its own faces rather than falling back.
    """
    name = resolve(name)
    if name == AUTO:
        return {}
    theme = THEMES[name]
    stack = STACKS[theme["stack"]]
    values = {f"--{token}": theme[token] for token in COLOUR_TOKENS}
    values["--grain"] = theme["grain"]
    values.update({f"--{t}": stack[t.removeprefix("font-")] for t in FONT_TOKENS})
    values.update({f"--{t}": stack[k] for t, k in TYPE_TOKENS.items()})
    values.update({f"--{t}": theme[t] for t in SHAPE_TOKENS})
    values["--texture"] = TEXTURES[theme["texture"]]
    return {"scheme": theme["scheme"], "fonts": fonts_url(name), "vars": values}


def catalogue_css() -> str:
    """Every theme, as `data-theme` blocks — the gallery's own stylesheet.

    Only the gallery carries this. It is a derived file, rebuilt whenever it is
    opened, so a theme added later reaches it for free; a *note* gets
    `palette_css` instead and never holds a catalogue that could go stale.

    `auto` is the *absence* of the attribute rather than a value of its own, so
    the media query and the explicit themes select mutually exclusive elements
    and never race on specificity. The explicit blocks come last and outrank the
    bare `:root` they override.
    """
    blocks = [
        "/* auto — the pair the archive shipped with, chosen by the browser. */",
        ":root {\n" + _declarations(AUTO_LIGHT, scheme="light dark") + "\n}",
        # No color-scheme here: `light dark` above already lets the browser
        # follow the system, and this block runs only when it has.
        "@media (prefers-color-scheme: dark) {\n"
        "  :root:not([data-theme]) {\n" + _declarations(AUTO_DARK, "    ", scheme="") + "\n  }\n}",
        "",
        "/* A chosen theme, from the gallery's menu or from config.json. */",
    ]
    blocks += [
        f'html[data-theme="{name}"] {{\n' + _declarations(name) + "\n}"
        for name in THEMES
    ]
    return "\n".join(blocks)


def configured_theme(config: dict | None = None) -> str:
    """`theme` from the config; `auto` for anything unrecognised.

    Tolerant like the rest of the config surface: a name that was renamed away,
    or a typo, falls back to the shipped pair rather than failing a build.
    """
    if config is None:
        from notes import read_config
        config = read_config()
    value = config.get("theme")
    return value if value in NAMES else AUTO


def attr(name: str) -> str:
    """The `data-theme` attribute for <html> — empty for `auto`."""
    return f' data-theme="{name}"' if name in THEMES else ""


def apply(config: dict, name: str) -> dict:
    """A copy of `config` with the theme set — never mutated in place."""
    return {**config, "theme": name}


def write(config: dict, path: Path | None = None) -> None:
    """Write the config back, pretty-printed so it stays hand-editable."""
    if path is None:
        from notes import CONFIG_FILE
    target = path or CONFIG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _luminance(hex_colour: str) -> float:
    """WCAG relative luminance of a #rrggbb string."""
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two #rrggbb strings."""
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _selftest() -> int:
    for name, theme in THEMES.items():
        assert set(COLOUR_TOKENS) <= set(theme), f"{name} is missing a colour token"
        for token in COLOUR_TOKENS:
            value = theme[token]
            assert len(value) == 7 and value.startswith("#"), f"{name}/{token} is not #rrggbb"
            int(value[1:], 16)
        assert theme["scheme"] in ("light", "dark"), name

    # The accessibility floor the templates' own comment promises.
    for name, theme in THEMES.items():
        for token in CONTRAST_TOKENS:
            ratio = contrast(theme[token], theme["paper"])
            assert ratio >= 4.5, f"{name}/{token} is {ratio:.2f}:1 against paper, below AA"
        tiers = contrast(theme["ink-70"], theme["ink-45"])
        assert tiers >= TIER_SEPARATION, (
            f"{name}: ink-70 and ink-45 are {tiers:.2f}:1 apart — that is one tier, not two"
        )
        for fg, bg, floor in CONTRAST_PAIRS:
            ratio = contrast(theme[fg], theme[bg])
            assert ratio >= floor, f"{name}: {fg} on {bg} is {ratio:.2f}:1, below {floor}"

    sheet = catalogue_css()
    assert "{{" not in sheet, "the templates' token guard would reject this"
    for name in THEMES:
        assert f'html[data-theme="{name}"]' in sheet, name
    assert ":root:not([data-theme])" in sheet, "auto's dark half must not match a chosen theme"
    assert "color-scheme: light dark;" in sheet, "auto follows the system"
    # Declarations only — the `@media (prefers-color-scheme: dark)` line carries
    # the same substring and is not one.
    assert sheet.count("\n  color-scheme:") == len(THEMES) + 1, (
        "one per explicit theme, plus auto's — the media-query half inherits it"
    )

    # A note carries values, never the catalogue: that is what keeps a note
    # written today from going stale when a theme is added tomorrow.
    one = palette_css("barbie")
    assert one.count(":root {") == 1 and "@media" not in one
    assert "--paper: #fff0f6;" in one and "--font-display: 'Bodoni Moda'" in one
    for other in THEMES:
        assert f'data-theme="{other}"' not in one, "no theme names reach a note"
    for other, theme in THEMES.items():
        if other != "barbie":
            assert theme["paper"] not in one, f"{other}'s values leaked into a barbie note"
    assert len(one) < len(catalogue_css()) / 3, "a note is far smaller than the catalogue"

    auto_css = palette_css(AUTO)
    assert auto_css.count(":root {") == 2 and "prefers-color-scheme: dark" in auto_css, (
        "auto is the one theme that cannot resolve to a single set of values"
    )
    assert palette_css("nonsense") == auto_css, "an unknown name degrades to auto"

    # A face is set, not just chosen: the weight a theme asks for has to be one
    # its family actually has, or the browser synthesises a fake bold.
    for name, theme in THEMES.items():
        stack = STACKS[theme["stack"]]
        # A single-weight family (Patrick Hand) carries no wght axis at all and
        # is 400 by definition; only the ones that declare an axis list cuts.
        weights = set()
        for chunk in stack["families"].split("family=")[1:]:
            if "wght@" not in chunk:
                weights.add("400")
                continue
            spec = chunk.split("wght@")[1].split("&")[0]
            weights |= {w.split(",")[-1] for w in spec.split(";")}
        assert stack["weight"] in weights, (
            f"{name}: display weight {stack['weight']} is not among the loaded {sorted(weights)}"
        )
        assert theme["texture"] in TEXTURES, name
        # a ruled stock needs a rule colour light enough to be a printed line,
        # not a border: it sits under running text
        if theme["texture"] != "none":
            assert contrast(theme["ink"], theme["rule"]) >= 4.5, (
                f"{name}: ink is not readable over its own ruled paper"
            )
        for token in SHAPE_TOKENS:
            assert theme[token], (name, token)

    # Type travels with the palette, and a note links only the faces it uses.
    assert "Space+Grotesk" in fonts_url("acid") and "Fraunces" not in fonts_url("acid")
    assert "Fraunces" in fonts_url(AUTO), "auto needs both halves of the pair"
    for name in THEMES:
        assert fonts_url(name).startswith("https://fonts.googleapis.com/css2?")
        for token in FONT_TOKENS:
            assert f"--{token}:" in palette_css(name), (name, token)

    # The injected value set: values only, and enough of them to repaint.
    load = payload("petrol")
    assert set(load) == {"scheme", "fonts", "vars"}
    assert load["vars"]["--paper"] == THEMES["petrol"]["paper"]
    assert set(load["vars"]) == {
        f"--{t}" for t in (
            *COLOUR_TOKENS, "grain", *FONT_TOKENS, *TYPE_TOKENS, *SHAPE_TOKENS, "texture"
        )
    }, "a payload carries everything a theme can say — colour, type and shape"
    assert "petrol" not in json.dumps(load["vars"]), "a payload names no theme"
    assert payload(AUTO) == {}, "auto has nothing to inject: the note follows the system"

    # Every theme resolves to a complete, self-sufficient block — no token left
    # to inherit from a stylesheet a note does not have.
    expected = {f"--{t}" for t in (*COLOUR_TOKENS, "grain", *FONT_TOKENS,
                                   *TYPE_TOKENS, *SHAPE_TOKENS, "texture")}
    for name in THEMES:
        sheet = palette_css(name)
        declared = {line.split(":")[0].strip() for line in sheet.splitlines() if "--" in line}
        assert expected <= declared, f"{name} is missing {sorted(expected - declared)}"
        assert "color-scheme:" in sheet, name

    # The payload survives the trip the gallery actually sends it on: JSON,
    # base64, into a URL fragment, and back out through the note's own regex.
    hash_chars = re.compile(r"^[A-Za-z0-9+/=]+$")
    for name in THEMES:
        packed = base64.b64encode(
            json.dumps(payload(name), separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        assert hash_chars.match(packed), (
            f"{name}: the packed payload has characters the note's #t= regex rejects"
        )
        back = json.loads(base64.b64decode(packed))
        assert back == payload(name), f"{name} does not survive the round trip"
        assert set(back) == {"scheme", "fonts", "vars"}, (
            "the three keys the note's inline script reads: t.scheme, t.fonts, t.vars"
        )

    assert attr(AUTO) == "", "auto is the absence of the attribute"
    assert attr("barbie") == ' data-theme="barbie"'
    assert attr("nonsense") == "", "an unknown name never reaches the markup"

    # Config: tolerant on the way in, non-destructive on the way out.
    assert configured_theme({}) == AUTO
    assert configured_theme({"theme": "bureau"}) == "bureau"
    assert configured_theme({"theme": "dracula"}) == AUTO, "the set is closed"
    assert configured_theme({"theme": 7}) == AUTO

    from notes import read_config

    path = Path("/tmp/take-notes/config-theme-selftest.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"language": "es", "tags": ["Unknown", "AI"]}\n', encoding="utf-8")
    write(apply(read_config(path), "blueprint"), path)
    config = read_config(path)
    assert config["theme"] == "blueprint"
    assert config["language"] == "es", "the language key survives a theme edit"
    assert config["tags"] == ["Unknown", "AI"], "so does the vocabulary"
    path.unlink(missing_ok=True)

    print("selftest: ok")
    return 0


def main() -> int:
    from notes import CONFIG_FILE, read_config

    ap = argparse.ArgumentParser(
        prog="themes",
        description=f"Show or set the colour theme in {CONFIG_FILE}.",
    )
    ap.add_argument("--set", metavar="NAME", help=f"Set the theme ({', '.join(NAMES)})")
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    if args.set is not None:
        name = args.set.strip().casefold()
        if name not in NAMES:
            print(f"themes: unknown theme {args.set!r} — pick one of {', '.join(NAMES)}",
                  file=sys.stderr)
            return 1
        write(apply(read_config(), name))

    current = configured_theme()
    for name in NAMES:
        mark = "*" if name == current else " "
        note = f"  {THEMES[name]['scheme']}" if name in THEMES else "  follows the system"
        print(f"{mark} {name}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
