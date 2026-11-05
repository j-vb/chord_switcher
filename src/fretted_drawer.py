"""Draws chord charts for fretted instruments in any tuning: banjo, tenor banjo and ukuleles.

Voicings are worked out from the tuning: every movable shape on the neck whose notes
are all chord tones, within a hand's reach, with fingers assigned like a player
would, plus the open chords near the nut. The open-G banjo also keeps the
hand-picked voicings from banjo_voicings.

The chord figures players slide up and down the neck come first, each in its own
colour: the banjo's F, A and D shapes (and their minor and seventh versions), and
the ukulele's shapes named after its open chords. The other shapes follow in grey.

A 5-string banjo has a short drone string, tuned to a high g and starting at the
5th fret. It is played open when g is in the chord. Up the neck it is fretted on a
chord tone when a finger is free, and otherwise it isn't played.

Styling, chord spelling and the staff come from chart_common, and charts are drawn
at several times their size and scaled down, like there.
"""
import itertools
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageDraw

import banjo_voicings
import chart_common
from chart_common import (
    ACCENT, CARD, FRET_LINE, INK, MUTED, NECK, PAGE, SANS_BOLD, STAFF_LEFT, STAFF_LINE, STAFF_RIGHT,
    SUPERSAMPLE,
)

DEPTHS = chart_common.DEPTHS


@dataclass(frozen=True)
class Figure:
    """A chord figure: fret offsets per string that make a chord wherever they are slid to.

    At offset 0 the figure uses the open strings, so the offsets are the frets of
    the chord it makes at the nut. None leaves a string out.
    """
    name: str  # Empty to name it after that chord, such as "C-shape"
    quality: str  # As in chord names: "" major, "-" minor, "7" seventh
    offsets: tuple
    fingers: tuple | None = None  # Fingers from a chord chart, used where no string is open


@dataclass(frozen=True)
class Tuning:
    name: str
    # Written pitches (MIDI numbers) of the open strings, in the order they lie on
    # the chart from left to right. Fretted instruments other than the ukulele are
    # written an octave above how they sound.
    strings: tuple
    drone: bool = False  # The first string is a 5-string banjo's drone
    curated: dict | None = None  # Hand-picked voicings, kept with the worked-out ones
    figures: tuple = ()  # Chord figures on the strings other than a drone, shown first


def _figures(table):
    """Figures from {quality: [(name, offsets) or (name, offsets, fingers), ...]}."""
    return tuple(Figure(figure[0], quality, *figure[1:]) for quality, figures in table.items() for figure in figures)


# The banjo's three movable shapes per kind of chord, named after the chord each
# makes low on the neck: F at the 1st fret, A at the 2nd, D at the 2nd and C7 at the 1st.
# An augmented chord is symmetrical: its one shape makes the next augmented chord four
# frets up, so each instrument has a single Aug-shape, the augmented chord at its nut.
BANJO_FIGURES = _figures({
    "": [("F-shape", (2, 1, 0, 2)), ("A-shape", (0, 0, 0, 0)), ("D-shape", (2, 0, 1, 2))],
    "-": [("Fm-shape", (2, 0, 0, 2)), ("Am-shape", (1, 1, 0, 1)), ("Dm-shape", (1, 0, 1, 1))],
    "7": [("F7-shape", (0, 1, 0, 2)), ("A7-shape", (0, 0, 0, 3)), ("C7-shape", (1, 2, 0, 1))],
    "+": [("Aug-shape", (1, 0, 0, 1))],
})
# The tenor banjo's three movable shapes per kind of chord, from banjochords.net:
# the root on the 4th string, the root on the 4th and 3rd strings under a barre, and
# the root on the 3rd string with the 4th left out. Both tunings use the same shapes,
# a fifth apart, so each is named after the chord it makes at the nut in its tuning,
# except the first seventh shape, which is a C7 there too and is named after the D7 it
# makes at the 2nd fret instead.
# Each shape is (offsets, fingers), with the fingers from the same chart.
TENOR_SHAPES = {
    "": (((3, 0, 1, 1), (4, 1, 2, 3)), ((0, 0, 2, 3), (1, 1, 3, 4)), ((None, 0, 0, 2), (0, 1, 1, 3))),
    "-": (((2, 2, 3, 0), (2, 3, 4, 1)), ((0, 0, 1, 3), (1, 1, 2, 4)), ((None, 0, 0, 1), (0, 1, 1, 2))),
    "7": (((0, 3, 2, 3), (1, 3, 2, 4)), ((0, 0, 2, 1), (1, 1, 3, 2)), ((None, 0, 3, 2), (0, 1, 4, 3))),
}


def _tenor_figures(names):
    """The tenor shapes named for a tuning, given as {quality: (name per shape)}, and the
    augmented shape: the diagonal that instruments tuned in fifths share."""
    return _figures({**{quality: [(name, *shape) for name, shape in zip(names[quality], shapes)]
                        for quality, shapes in TENOR_SHAPES.items()},
                     "+": [("Aug-shape", (0, 1, 2, 3))]})


TENOR_FIGURES = _tenor_figures({"": ("E♭-shape", "C-shape", "G-shape"), "-": ("Dm-shape", "Cm-shape", "Gm-shape"),
                                "7": ("D7-shape", "C7-shape", "G7-shape")})
IRISH_FIGURES = _tenor_figures({"": ("B♭-shape", "G-shape", "D-shape"), "-": ("Am-shape", "Gm-shape", "Dm-shape"),
                                "7": ("A7-shape", "G7-shape", "D7-shape")})
# The double-C banjo's three movable major shapes, named as in Peghead Nation's
# clawhammer course: a barre with the 1st string two frets up, the triangle on the
# three highest strings, and the F chord at the nut. No names are known for minor
# and seventh shapes in this tuning.
DOUBLE_C_FIGURES = _figures({
    "": [("Barre", (0, 0, 0, 2)), ("Triangle", (None, 1, 0, 1)), ("F-shape", (0, 2, 0, 3))],
    "+": [("Aug-shape", (0, 1, 0, 2))],
})
# Ukulele open chords that slide up the neck, named after the chord each makes at the
# nut. The baritone has the same intervals, so its names come out as G, E, D, C and A.
UKULELE_FIGURES = _figures({
    "": [("", (0, 0, 0, 3)), ("", (2, 1, 0, 0)), ("", (0, 2, 3, 2)), ("", (2, 0, 1, 0)), ("", (2, 2, 2, 0))],
    "-": [("", (0, 3, 3, 3)), ("", (2, 0, 0, 0)), ("", (0, 2, 3, 1)), ("", (1, 0, 1, 3)), ("", (2, 2, 1, 0))],
    "7": [("", (0, 0, 0, 1)), ("", (0, 1, 0, 0)), ("", (0, 2, 1, 2)), ("", (2, 3, 1, 3)), ("", (2, 2, 2, 3))],
    "+": [("Aug-shape", (1, 0, 0, 3))],
})

# Colours for the figures, by their place in the list for their kind of chord, so the
# major, minor and seventh versions of a shape share a colour. And one for other shapes.
FIGURE_COLOURS = ("#d4553a", "#2f7fd1", "#2a9d6f", "#8a5cc7", "#d4920f")
OTHER_COLOUR = "#a39d92"


DRONE_START = 5  # The fret where the drone string starts
REACH = 3  # Frets between the lowest and highest finger
FIFTHS_REACH = 4  # Instruments tuned in fifths need a wider hand, as their chord books show
HIGHEST_START = 15  # Highest fret a shape may start on
# A shape with open strings counts as an open chord only this close to the nut.
# Higher up it would only be a closed shape with a note swapped for an open string.
OPEN_POSITION = 4

INSTRUMENTS = {
    "Banjo": (
        Tuning("Open G", (79, 62, 67, 71, 74), drone=True, curated=banjo_voicings.VOICINGS, figures=BANJO_FIGURES),
        Tuning("Double C", (79, 60, 67, 72, 74), drone=True, figures=DOUBLE_C_FIGURES),
    ),
    "Tenor banjo": (
        Tuning("Standard", (60, 67, 74, 81), figures=TENOR_FIGURES),
        Tuning("Irish", (55, 62, 69, 76), figures=IRISH_FIGURES),
    ),
    "Ukulele": (
        Tuning("Standard", (67, 60, 64, 69), figures=UKULELE_FIGURES),
        Tuning("Low G", (55, 60, 64, 69), figures=UKULELE_FIGURES),
    ),
    "Baritone ukulele": (
        Tuning("Standard", (62, 67, 71, 76), figures=UKULELE_FIGURES),
    ),
}


def tuning_label(tuning):
    """A tuning's name with its strings, such as "Open G (gDGBD)"."""
    names = []
    for index, pitch in enumerate(tuning.strings):
        letter, accidental = _pitch_name(pitch)
        name = letter + ("♯" if accidental else "")
        names.append(name.lower() if tuning.drone and index == 0 or _is_reentrant(tuning, index) else name)
    return f"{tuning.name} ({''.join(names)})"


def _pitch_name(pitch):
    sharps = ("C", "C", "D", "D", "E", "F", "F", "G", "G", "A", "A", "B")
    return sharps[pitch % 12], pitch % 12 in (1, 3, 6, 8, 10)


def _is_reentrant(tuning, index):
    """Whether a string on the bass side is tuned above the string next to it, like a high g."""
    return index == 0 and len(tuning.strings) > 1 and tuning.strings[0] > tuning.strings[1]


def get_tuning(instrument, name):
    tunings = INSTRUMENTS[instrument]
    return next((t for t in tunings if t.name == name), tunings[0])


# Chord tones

def _chord_tones(chord):
    """The pitch classes of a chord, as (root, third, fifth, seventh or None)."""
    root, quality = chart_common.split_chord_name(chord)
    root_pitch = chart_common.NATURALS[chart_common.LETTERS.index(root[0].upper())] + (root[1:] == "#")
    tones = [(root_pitch + interval) % 12 for interval in chart_common.QUALITIES[quality]]
    return root_pitch % 12, tones[0], tones[1], tones[2] if len(tones) > 2 else None


def sounding_offset(tuning, string, fret):
    """Semitones above the open string that a neck fret plays. The drone starts at the 5th fret."""
    if tuning.drone and string == 0 and fret:
        return fret - DRONE_START
    return fret


# Fingering

def assign_fingers(frets):
    """Fingers for a voicing, per string (0 for open or muted), or None if it can't be held.

    Fingers go up with the fret, and across the strings at one fret. A single note
    near the nut takes the finger for its fret. When the notes don't fit on four
    fingers, three or more share the lowest fret, or two or more fingers would sit
    between notes at the lowest fret, the first finger lies across them as a barre.
    """
    fretted = [(fret, string) for string, fret in enumerate(frets) if fret]
    fingers = [0] * len(frets)
    if not fretted:
        return tuple(fingers)
    low = min(fret for fret, _ in fretted)
    if len(fretted) == 1 and low <= 4:
        fingers[fretted[0][1]] = low
        return tuple(fingers)

    def spread(notes, first_finger):
        """Fingers for notes sorted by (fret, string), from first_finger, or None.

        Each finger sits as many frets above the first finger as it is numbered above it.
        """
        result, previous = [], first_finger - 1
        for fret, _ in notes:
            finger = max(previous + 1, 1 + fret - low)
            result.append(finger)
            previous = finger
        # Pull fingers back down where a gap pushed them past the little finger
        for i in range(len(result) - 1, -1, -1):
            result[i] = min(result[i], 4 - (len(result) - 1 - i))
            if i and result[i - 1] >= result[i]:
                result[i - 1] = result[i] - 1
        if result and result[0] < first_finger:
            return None
        return result

    notes = sorted(fretted)
    at_low = [string for fret, string in notes if fret == low]
    barre_strings = range(at_low[0], at_low[-1] + 1)
    can_barre = len(at_low) > 1 and all(frets[s] and frets[s] >= low for s in barre_strings)
    enclosed = sum(frets[s] > low for s in barre_strings) >= 2

    if not can_barre or (len(at_low) < 3 and not enclosed):
        plain = spread(notes, 1)
        if plain is not None:
            for (_, string), finger in zip(notes, plain):
                fingers[string] = finger
            return tuple(fingers)
    if not can_barre:
        return None
    rest = [(fret, string) for fret, string in notes if fret != low]
    others = spread(rest, 2) if rest else []
    if others is None:
        return None
    for string in at_low:
        fingers[string] = 1
    for (_, string), finger in zip(rest, others):
        fingers[string] = finger
    return tuple(fingers)


# Working out voicings

def _string_options(tuning, string, tones, low, reach):
    """The frets a string may play in the window from low to low + reach, or None to mute it."""
    open_pitch = tuning.strings[string]
    options = []
    if open_pitch % 12 in tones:
        options.append(0)
    for fret in range(max(low, 1), low + reach + 1):
        if tuning.drone and string == 0 and fret <= DRONE_START:
            continue
        if (open_pitch + sounding_offset(tuning, string, fret)) % 12 in tones:
            options.append(fret)
    if tuning.drone and string == 0:
        options.append(None)  # The drone may be left out
    return options


def _score(tuning, frets, fingers, root):
    """Lower is better: few fingers, a root in the bass, open strings and a small reach."""
    played = [(tuning.strings[s] + sounding_offset(tuning, s, f), s) for s, f in enumerate(frets) if f is not None]
    lowest_pitch = min(pitch for pitch, _ in played)
    fretted = [f for f in frets if f]
    reach = max(fretted) - min(fretted) if fretted else 0
    return (len(set(fingers) - {0}) * 2 + reach + (0 if lowest_pitch % 12 == root else 2)
            - frets.count(0) * 0.5 + (1 if fingers.count(1) > 1 else 0) + (3 if frets[0] is None else 0))


def _worked_out(tuning, chord, reach):
    root, third, fifth, seventh = _chord_tones(chord)
    tones = {root, third, fifth} | ({seventh} if seventh is not None else set())
    main = range(1 if tuning.drone else 0, len(tuning.strings))
    # A four-note chord may drop its fifth on four strings
    required = {root, third} | ({seventh} if seventh is not None else {fifth})
    if seventh is None or len(main) > 4:
        required.add(fifth)

    found = {}
    for low in range(0, HIGHEST_START + 1):
        options = [_string_options(tuning, s, tones, low, reach) for s in range(len(tuning.strings))]
        for frets in itertools.product(*options):
            if frets in found:
                continue
            fretted = [f for f in frets if f]
            if fretted and max(fretted) - min(fretted) > reach:
                continue
            pitches = {(tuning.strings[s] + sounding_offset(tuning, s, frets[s])) % 12
                       for s in main if frets[s] is not None}
            if not required <= pitches:
                continue
            fingers = assign_fingers(frets)
            if fingers is None:
                continue
            found[frets] = fingers
    return found


def _add_drone(tuning, chord, frets, fingers):
    """A 4-string banjo voicing with the drone in front: open, fretted up the neck, or left out."""
    root, third, fifth, seventh = _chord_tones(chord)
    tones = {root, third, fifth, seventh} - {None}
    if tuning.strings[0] % 12 in tones:
        return (0, *frets), (0, *fingers)
    fretted = [f for f in frets if f]
    if fretted and max(fretted) > DRONE_START:
        for fret in range(max(min(fretted), DRONE_START + 1), max(fretted) + 1):
            if (tuning.strings[0] + fret - DRONE_START) % 12 in tones:
                with_drone = (fret, *frets)
                new_fingers = assign_fingers(with_drone)
                if new_fingers is not None:
                    return with_drone, new_fingers
    return (None, *frets), (0, *fingers)


def _reach(tuning):
    tuned_in_fifths = all(high - low == 7 for low, high in zip(tuning.strings, tuning.strings[1:]))
    return FIFTHS_REACH if tuned_in_fifths else REACH


def _is_option(frets):
    """Whether a shape is its own way to play a chord: closed, or an open chord near the nut."""
    fretted = [f for f in frets if f]
    return 0 not in frets or not fretted or max(fretted) <= OPEN_POSITION


ROOTS = ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b")


def figure_name(tuning, figure):
    """A figure's name, or the chord it makes at the nut plus "-shape", such as "Cm-shape"."""
    if figure.name:
        return figure.name
    main = tuning.strings[1:] if tuning.drone else tuning.strings
    for root in ROOTS:
        tones = set(chart_common.spell_chord(root + figure.quality))
        if {(pitch + offset) % 12 for pitch, offset in zip(main, figure.offsets)} <= tones:
            return shape_name(root, figure.quality)
    return "Shape"


def shape_name(root, quality):
    """The name of the shape a chord makes, such as "Am-shape" or "C7-shape"."""
    return chart_common.chord_title(root) + {"": "", "-": "m", "7": "7"}[quality] + "-shape"


def figure_colours(tuning):
    """Each figure name's colour, by its place among the figures for its kind of chord."""
    colours = {}
    for quality in dict.fromkeys(f.quality for f in tuning.figures):
        names = dict.fromkeys(figure_name(tuning, f) for f in tuning.figures if f.quality == quality)
        for i, name in enumerate(names):
            colours.setdefault(name, FIGURE_COLOURS[i % len(FIGURE_COLOURS)])
    return colours


def _placed_figures(tuning, main, chord):
    """Each figure of the chord's quality at every fret where it makes the chord, as
    {frets: (name, fingers or None)}. A figure's own fingers apply where no string is open."""
    _, quality = chart_common.split_chord_name(chord)
    tones = set(chart_common.spell_chord(chord))
    root = _chord_tones(chord)[0]
    placed = {}
    for figure in tuning.figures:
        if figure.quality != quality:
            continue
        for shift in range(chart_common.MAX_FRET + 1):
            frets = tuple(None if offset is None else offset + shift for offset in figure.offsets)
            if max(f for f in frets if f is not None) > chart_common.MAX_FRET:
                break
            pitches = {(pitch + fret) % 12 for pitch, fret in zip(main.strings, frets) if fret is not None}
            if pitches <= tones and root in pitches and len(pitches) >= 3:
                fingers = figure.fingers if figure.fingers and 0 not in frets else None
                placed.setdefault(frets, (figure_name(tuning, figure), fingers))
    return placed


@lru_cache(maxsize=None)
def voicings(instrument, tuning_name, chord):
    """Every voicing of a chord as ("frets/fingers", figure name or None), x for a muted string.

    The figures come first, then the other shapes, each lowest on the neck first.
    A 5-string banjo's shapes are worked out on its four long strings, and then
    each gets its drone.
    """
    tuning = get_tuning(instrument, tuning_name)
    main = Tuning(tuning.name, tuning.strings[1:]) if tuning.drone else tuning
    shapes = {frets: fingers for frets, fingers in _worked_out(main, chord, _reach(main)).items()
              if _is_option(frets)}
    for voicing in (tuning.curated or {}).get(chord, ()):
        frets, fingers = banjo_voicings.parse_voicing(voicing)
        shapes[frets] = fingers  # Hand-picked fingers win
    figures = _placed_figures(tuning, main, chord)
    for frets, (_, fingers) in figures.items():
        if fingers:
            shapes[frets] = fingers
        elif frets not in shapes:
            shapes[frets] = assign_fingers(frets)
    root = _chord_tones(chord)[0]
    ordered = sorted(((frets, fingers) for frets, fingers in shapes.items() if fingers), key=lambda shape: (
        shape[0] not in figures, chart_common.lowest_fret(shape[0]), _score(main, *shape, root),
        [-1 if f is None else f for f in shape[0]]))
    result = []
    for frets, fingers in ordered:
        name = figures[frets][0] if frets in figures else None
        if tuning.drone:
            frets, fingers = _add_drone(tuning, chord, frets, fingers)
        result.append((_format(frets, fingers), name))
    return result


def _format(frets, fingers):
    return (" ".join("x" if f is None else str(f) for f in frets) + "/"
            + " ".join(map(str, fingers)))


def parse_voicing(voicing):
    """Split a "frets/fingers" entry into two tuples. A muted string has the fret None."""
    frets, fingers = voicing.split("/")
    return (tuple(None if f == "x" else int(f) for f in frets.split()),
            tuple(map(int, fingers.split())))


def at_depth(tuning, shapes, depth):
    """The (voicing, figure name) pairs at one depth from DEPTHS or several.

    Closed shapes may move up an octave to reach a depth. An open drone doesn't
    stop that, as it is the same open string anywhere on the neck.
    """
    ranges = [DEPTHS[name] for name in ([depth] if isinstance(depth, str) else depth)]

    def lowest(entry):
        frets = parse_voicing(entry[0])[0]
        return chart_common.lowest_fret(frets[1:] if tuning.drone else frets)

    def distance(entry):
        fret = lowest(entry)
        return min(max(low - fret, fret - high, 0) for low, high in ranges)

    def shifted(entry):
        voicing, name = entry
        frets, fingers = parse_voicing(voicing)
        main = frets[1:] if tuning.drone else frets
        if 0 in main:
            return None
        moved = tuple(f if f in (None, 0) else f + 12 for f in frets)
        if max(f for f in moved if f is not None) > chart_common.MAX_FRET:
            return None
        return _format(moved, fingers), name

    candidates = list(shapes)
    if not any(distance(v) == 0 for v in candidates):
        candidates += [v for v in map(shifted, shapes) if v]
    nearest = min(distance(v) for v in candidates)
    return [v for v in candidates if distance(v) == nearest]


# Drawing

BOARD_LEFT = 50
BOARD_RIGHT = 146  # The highest string, whatever the number of strings
BOARD_TOP = 84
NECK_PAD = 14
FRET_GAP = 34
BOARD_HEIGHT = 5 * FRET_GAP  # Frets get closer when more of them must fit
MIN_FRETS_SHOWN = 4
TAB_TOP = 202
TAB_GAP = 13


def canvas_size(scale=1.0, count=chart_common.COLUMNS, columns=chart_common.COLUMNS):
    """Size of the image render_chord returns for a number of voicings, as (width, height)."""
    columns = max(1, min(columns, count))
    rows = max(1, -(-count // columns))
    return round(columns * chart_common.CELL_WIDTH * scale), round(rows * chart_common.CELL_HEIGHT * scale)


def best_columns(count, width, height):
    """The number of columns that draws a number of cards largest in a space of width by height."""
    def card_scale(columns):
        grid_width, grid_height = canvas_size(1.0, count, columns)
        return min(width / grid_width, height / grid_height)
    return max(range(1, max(1, count) + 1), key=card_scale)


def draw_grid(count, draw_cell, scale=1.0, columns=chart_common.COLUMNS):
    """An image with a card per voicing, in rows that are centred like the cards in them.

    draw_cell(cell, index) draws card index on a chart_common._Cell.
    """
    cell_width, cell_height = chart_common.CELL_WIDTH, chart_common.CELL_HEIGHT
    columns = max(1, min(columns, count))
    width, height = canvas_size(scale, count, columns)
    image = Image.new("RGB", (width * SUPERSAMPLE, height * SUPERSAMPLE), PAGE)
    draw = ImageDraw.Draw(image)
    for index in range(count):
        row, column = divmod(index, columns)
        in_row = min(columns, count - row * columns)
        left = (columns - in_row) * cell_width / 2 + column * cell_width
        draw_cell(chart_common._Cell(draw, left, row * cell_height, scale), index)
    return image.resize((width, height), Image.LANCZOS)


LABEL_SIZE = 14


def draw_card(cell, name, colour):
    """A card, with the name of its figure at the top right in the figure's colour.

    Symbols such as ♭ come from a symbol font when the text font lacks them.
    """
    chart_common._draw_card(cell, 0, 1)
    if not name:
        return
    font = cell.font(SANS_BOLD, LABEL_SIZE)
    symbols = cell.font(chart_common.SYMBOLS, LABEL_SIZE)
    parts = [(char, symbols if not chart_common._has_glyph(font, char) and chart_common._has_glyph(symbols, char)
              else font) for char in name]
    x, y = cell.point(chart_common.CELL_WIDTH - 24, chart_common.TITLE_Y - 8)
    x -= sum(used.getlength(char) for char, used in parts)
    for char, used in parts:
        cell.draw.text((x, y), char, font=used, fill=colour, anchor="lm")
        x += used.getlength(char)


def base_fret(tuning, frets):
    """The fret at the top of the fretboard. 1 means it starts at the nut.

    A shape starts at the nut when it reaches the 4th fret at most, or the 5th
    with an open string. The drone's open string doesn't count, as it starts higher.
    """
    fretted = [fret for fret in frets if fret]
    main = frets[1:] if tuning.drone else frets
    if not fretted or max(fretted) <= 4 or (0 in main and max(fretted) <= 5):
        return 1
    return min(fretted)


def _draw_fretboard(cell, tuning, frets, fingers, colour=ACCENT):
    count = len(frets)
    gap = (BOARD_RIGHT - BOARD_LEFT) / (count - 1)
    dot_radius = min(11.5, gap * 0.42)
    base = base_fret(tuning, frets)
    played = [fret for fret in frets if fret]
    rows = max(MIN_FRETS_SHOWN, (max(played) if played else 0) - base + 1)
    if tuning.drone and base <= DRONE_START:
        rows = max(rows, DRONE_START - base + 2)  # Show where the drone string starts, and a fret of it
    fret_gap = min(FRET_GAP, BOARD_HEIGHT / rows)
    bottom = BOARD_TOP + rows * fret_gap
    drone_top = BOARD_TOP + (DRONE_START - base + 1) * fret_gap

    def string_x(string):
        return BOARD_LEFT + string * gap

    def marker_y(string):
        """Where a string's open or muted marker goes: above the nut, or at the drone's start."""
        if tuning.drone and string == 0 and base <= DRONE_START:
            return drone_top - 15
        return BOARD_TOP - 15

    cell.rounded(BOARD_LEFT - NECK_PAD, BOARD_TOP, BOARD_RIGHT + NECK_PAD, bottom, 4, NECK)
    for row in range(1, rows + 1):
        y = BOARD_TOP + row * fret_gap
        cell.line(BOARD_LEFT - NECK_PAD, y, BOARD_RIGHT + NECK_PAD, y, 1.4, FRET_LINE)
    for string in range(count):
        top = BOARD_TOP
        if tuning.drone and string == 0 and base <= DRONE_START:
            top = drone_top
            cell.circle(string_x(0), top, 3.5, STAFF_LINE)  # The drone's peg
        cell.line(string_x(string), top, string_x(string), bottom, 1.5, STAFF_LINE)

    if base == 1:
        cell.line(BOARD_LEFT - NECK_PAD, BOARD_TOP - 1, BOARD_RIGHT + NECK_PAD, BOARD_TOP - 1, 4.5, INK)
    else:
        cell.line(BOARD_LEFT - NECK_PAD, BOARD_TOP, BOARD_RIGHT + NECK_PAD, BOARD_TOP, 1.4, FRET_LINE)
        cell.text(BOARD_LEFT - NECK_PAD - 7, BOARD_TOP + fret_gap / 2, f"{base}", SANS_BOLD, 15, MUTED, "rm")

    dots = []
    for string, (fret, finger) in enumerate(zip(frets, fingers)):
        x, y = string_x(string), marker_y(string)
        if fret is None:
            cell.line(x - 4, y - 4, x + 4, y + 4, 1.8, MUTED)
            cell.line(x - 4, y + 4, x + 4, y - 4, 1.8, MUTED)
        elif fret == 0:
            cell.circle(x, y, 6, CARD, colour, 2)
        else:
            dots.append((x, BOARD_TOP + (fret - base + 0.5) * fret_gap, fret, finger, string))

    # A finger laid flat across several strings is a barre, drawn behind its dots
    for finger in sorted({dot[3] for dot in dots}):
        held = [dot for dot in dots if dot[3] == finger]
        if len(held) > 1 and len({dot[2] for dot in held}) == 1:
            cell.line(held[0][0], held[0][1], held[-1][0], held[-1][1], dot_radius * 2, colour)

    for x, y, _, finger, _ in dots:
        cell.circle(x, y, dot_radius, colour)
        cell.text(x, y - 0.5, str(finger), SANS_BOLD, 13 if dot_radius > 10 else 12, "#ffffff")


def _draw_tab(cell, frets):
    """A tab with the highest-numbered string at the bottom, as banjo and ukulele tabs are written."""
    count = len(frets)
    bottom = TAB_TOP + (count - 1) * TAB_GAP
    for line in range(count):
        y = TAB_TOP + line * TAB_GAP
        cell.line(STAFF_LEFT, y, STAFF_RIGHT, y, 1.1, STAFF_LINE)
    cell.line(STAFF_LEFT, TAB_TOP, STAFF_LEFT, bottom, 1.1, STAFF_LINE)
    cell.line(STAFF_RIGHT, TAB_TOP, STAFF_RIGHT, bottom, 1.1, STAFF_LINE)
    cell.text(STAFF_LEFT + 14, TAB_TOP + (count - 1) / 2 * TAB_GAP, "TAB", SANS_BOLD, 9, MUTED)

    for line, fret in enumerate(reversed(frets)):
        if fret is None:
            continue
        x, y = cell.point(chart_common.NOTE_X, TAB_TOP + line * TAB_GAP)
        half_width = (4.5 if fret < 10 else 8) * cell.factor
        half_height = 5.5 * cell.factor
        cell.draw.rectangle((x - half_width, y - half_height, x + half_width, y + half_height), fill=CARD)
        cell.text(chart_common.NOTE_X, TAB_TOP + line * TAB_GAP - 0.3, str(fret), SANS_BOLD, 12)


def shown_voicings(chord, depth="All", instrument="Banjo", tuning=None):
    """The (voicing, figure name) pairs a chart shows."""
    tuning = get_tuning(instrument, tuning)
    return at_depth(tuning, voicings(instrument, tuning.name, chord), depth)


def card_count(chord, depth="All", instrument="Banjo", tuning=None):
    """The number of cards render_chord draws."""
    return len(shown_voicings(chord, depth, instrument, tuning))


def render_chord(chord, scale=1.0, depth="All", instrument="Banjo", tuning=None, columns=chart_common.COLUMNS):
    """Draw the voicings of a chord, such as "a#7", at a depth from DEPTHS as a PIL image.

    Figures are drawn in their colours. When a chord has figures, its other shapes are grey.
    """
    tuning = get_tuning(instrument, tuning)
    title = chart_common.chord_title(chord)
    shown = shown_voicings(chord, depth, instrument, tuning.name)
    colours = figure_colours(tuning)
    has_figures = any(name for _, name in shown)

    def draw_cell(cell, index):
        voicing, name = shown[index]
        frets, fingers = parse_voicing(voicing)
        colour = colours[name] if name else (OTHER_COLOUR if has_figures else ACCENT)
        draw_card(cell, name, colour)
        cell.title(chart_common.TITLE_X, chart_common.TITLE_Y + 9, title, chart_common.TITLE_SIZE)
        _draw_fretboard(cell, tuning, frets, fingers, colour)
        # The staff takes how far above the open string each note sounds
        offsets = tuple(None if f is None else sounding_offset(tuning, s, f) for s, f in enumerate(frets))
        chart_common._draw_staff(cell, chord, offsets, tuning.strings)
        _draw_tab(cell, frets)

    return draw_grid(len(shown), draw_cell, scale, columns)
