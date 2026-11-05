"""Draws guitar chord charts as antialiased images.

Each chord is drawn as one card per voicing: name, fretboard, staff and tab. Styling,
chord spelling and the staff come from chart_common, and the chart is drawn at
several times its size and scaled down, like there. Voicings are open chords plus
the five movable shapes of the CAGED system (named after the open C, A, G, E and D
chords they come from), which are worked out for each root.
"""
import chart_common
import fretted_drawer
from chart_common import ACCENT, CARD, FRET_LINE, INK, MUTED, NECK, SANS_BOLD, STAFF_LEFT, STAFF_LINE, STAFF_RIGHT

# The CAGED shapes are the guitar's chord figures, shown first and each in its colour.
# They are named per kind of chord, such as "Am-shape", and coloured per letter.
CAGED = "CAGED"
COLOURS = dict(zip(CAGED, fretted_drawer.FIGURE_COLOURS))
# An augmented chord is symmetrical, so its one movable shape is its figure
AUG = "Aug-shape"
TUNING = fretted_drawer.Tuning("Standard", (52, 57, 62, 67, 71, 76))

# Written pitches (MIDI numbers) of the open strings, low to high: E A D G B E.
# Guitar music is written an octave above how it sounds.
OPEN_STRINGS = (52, 57, 62, 67, 71, 76)
SOUNDING_STRINGS = tuple(pitch - 12 for pitch in OPEN_STRINGS)
STRINGS = len(OPEN_STRINGS)

# Open chords, as "frets/fingers" per string from low to high. x is a muted string
# and 0 an open one.
OPEN_VOICINGS = {
    "c": ["x 3 2 0 1 0/0 3 2 0 1 0"],
    "d": ["x x 0 2 3 2/0 0 0 1 3 2"],
    "e": ["0 2 2 1 0 0/0 2 3 1 0 0"],
    "g": ["3 2 0 0 0 3/2 1 0 0 0 3", "3 2 0 0 3 3/2 1 0 0 3 4"],
    "a": ["x 0 2 2 2 0/0 0 1 2 3 0"],
    "d-": ["x x 0 2 3 1/0 0 0 2 3 1"],
    "e-": ["0 2 2 0 0 0/0 2 3 0 0 0"],
    "a-": ["x 0 2 2 1 0/0 0 2 3 1 0"],
    "c7": ["x 3 2 3 1 0/0 3 2 4 1 0"],
    "d7": ["x x 0 2 1 2/0 0 0 2 1 3"],
    "e7": ["0 2 0 1 0 0/0 2 0 1 0 0"],
    "g7": ["3 2 0 0 0 1/3 2 0 0 0 1"],
    "a7": ["x 0 2 0 2 0/0 0 2 0 3 0"],
    "b7": ["x 2 1 2 0 2/0 2 1 3 0 4"],
}

# Movable shapes as (fret offsets, fingers) from the fret of the root, with None
# for a muted string. The root is on the string at ROOT_STRING.
E_SHAPES = {
    "": ((0, 2, 2, 1, 0, 0), "1 3 4 2 1 1"),
    "-": ((0, 2, 2, 0, 0, 0), "1 3 4 1 1 1"),
    "7": ((0, 2, 0, 1, 0, 0), "1 3 1 2 1 1"),
}
A_SHAPES = {
    "": ((None, 0, 2, 2, 2, 0), "0 1 3 3 3 1"),
    "-": ((None, 0, 2, 2, 1, 0), "0 1 3 4 2 1"),
    "7": ((None, 0, 2, 0, 2, 0), "0 1 3 1 4 1"),
    "°": ((None, 0, 1, 2, 1, None), "0 1 2 4 3 0"),
}
D_DIMINISHED = ((None, None, 0, 1, 3, 1), "0 0 1 2 4 3")
D_SHAPES = {
    "": ((None, None, 0, 2, 3, 2), "0 0 1 2 3 2"),
    "-": ((None, None, 0, 2, 3, 1), "0 0 1 3 4 2"),
    "7": ((None, None, 0, 2, 1, 2), "0 0 1 3 2 4"),
}
# The C and G shapes reach down from the root, so their fingers are worked out per fret.
# C shapes have the root on the A string, G shapes on the low E string. Moved up the
# neck, the C7 shape leaves out the high E and the G minor shape the two highest
# strings, as their full forms would need five fingers.
C_SHAPES = {
    "": (None, 0, -1, -3, -2, -3),
    "-": (None, 0, -2, -3, -2, None),
    "7": (None, 0, -1, 0, -2, None),
}
G_SHAPES = {
    "": (0, -1, -3, -3, -3, 0),
    "-": (0, -2, -3, -3, None, None),
    "7": (0, -1, -3, -3, -3, -2),
}
# An augmented chord is symmetric, so this shape fits on any of its three notes.
A_AUGMENTED = (None, 0, -1, -2, -2, -3)
DEPTHS = chart_common.DEPTHS


def _shape(root_fret, offsets, fingers):
    frets = " ".join("x" if o is None else str(root_fret + o) for o in offsets)
    return f"{frets}/{fingers}"


def _pitch_class(chord):
    root, _ = chart_common.split_chord_name(chord)
    name = chart_common.FLAT_ROOTS.get(chord, root.upper())
    letter = chart_common.NATURALS[chart_common.LETTERS.index(name[0])]
    return (letter + {"": 0, "#": 1, "b": -1}[name[1:]]) % 12


def _root_fret(pitch_class, open_pitch):
    """The fret, from 1 to 12, of a note on a string."""
    return (pitch_class - open_pitch) % 12 or 12


def _augmented_fingers(frets):
    ranks = sorted({fret for fret in frets if fret})
    return " ".join("0" if fret in (None, 0) else str(min(4, ranks.index(fret) + 1)) for fret in frets)


def _voicings(chord):
    """The voicings of a chord as ("frets/fingers", CAGED shape or None), the CAGED shapes first."""
    root, quality = chart_common.split_chord_name(chord)
    pitch = _pitch_class(chord)
    figure = quality in ("", "-", "7")
    # An open chord on C, A, G, E or D is that CAGED shape at the nut
    def name(letter):
        return fretted_drawer.shape_name(letter.lower(), quality) if figure else None

    open_name = name(root) if root.upper() in CAGED and len(root) == 1 else None
    voicings = {voicing: open_name for voicing in OPEN_VOICINGS.get(chord, [])}

    def add(voicing, name):
        voicings.setdefault(voicing, name)

    def add_shape(string, offsets, fingers, name):
        add(_shape(_root_fret(pitch, SOUNDING_STRINGS[string]), offsets, fingers), name)

    def add_reaching_shape(string, offsets, name):
        """A shape with frets below its root, which must sit at the 3rd fret or higher.

        At the 3rd fret it is the open chord itself, so it is only added higher up.
        """
        root_fret = _root_fret(pitch, SOUNDING_STRINGS[string])
        if root_fret <= 3:
            root_fret += 12
        frets = tuple(None if o is None else root_fret + o for o in offsets)
        fingers = fretted_drawer.assign_fingers(frets)
        if fingers and max(f for f in frets if f is not None) <= chart_common.MAX_FRET:
            add(_shape(root_fret, offsets, " ".join(map(str, fingers))), name)

    if quality in E_SHAPES:
        add_shape(0, *E_SHAPES[quality], name("E"))
    if quality in A_SHAPES:
        add_shape(1, *A_SHAPES[quality], name("A"))
    if quality in D_SHAPES:
        add_shape(2, *D_SHAPES[quality], name("D"))
    if quality == "°":
        add_shape(2, *D_DIMINISHED, None)
    for string, shapes, letter in ((1, C_SHAPES, "C"), (0, G_SHAPES, "G")):
        if quality in shapes:
            add_reaching_shape(string, shapes[quality], name(letter))
    if quality == "+":
        for note in (pitch, pitch + 4, pitch + 8):
            root_fret = _root_fret(note, SOUNDING_STRINGS[1])
            root_fret += 12 if root_fret < 3 else 0
            frets = [None if o is None else root_fret + o for o in A_AUGMENTED]
            add(" ".join("x" if f is None else str(f) for f in frets) + "/" + _augmented_fingers(frets), AUG)
    return sorted(voicings.items(), key=lambda entry: (
        entry[1] is None, chart_common.lowest_fret(parse_voicing(entry[0])[0])))


def parse_voicing(voicing):
    """Split a "frets/fingers" entry into two tuples. A muted string has the fret None."""
    frets, fingers = voicing.split("/")
    return (tuple(None if f == "x" else int(f) for f in frets.split()),
            tuple(map(int, fingers.split())))


def _build():
    voicings = {}
    for root in ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"):
        for quality in ("", "-", "7", "+", "°"):
            voicings[root + quality] = _voicings(root + quality)
    return voicings


# Chord name -> voicings, such as "a#7"
VOICINGS = _build()

# Layout, in pixels at scale 1
BOARD_LEFT = 44
BOARD_TOP = 84
STRING_GAP = 19
NECK_PAD = 13
FRET_GAP = 34
MIN_FRETS_SHOWN = 4
DOT_RADIUS = 9.5
TAB_TOP = 192
TAB_GAP = 12


def shown_voicings(chord, depth="All"):
    """The (voicing, CAGED shape) pairs a chart shows."""
    return fretted_drawer.at_depth(TUNING, VOICINGS[chord], depth)


def card_count(chord, depth="All"):
    """The number of cards render_chord draws."""
    return len(shown_voicings(chord, depth))


def base_fret(frets):
    """The fret at the top of the fretboard. 1 means it starts at the nut."""
    fretted = [fret for fret in frets if fret]
    if not fretted or min(fretted) == 1 or 0 in frets:
        return 1
    return min(fretted)


def _draw_fretboard(cell, frets, fingers, colour=ACCENT):
    base = base_fret(frets)
    played = [fret for fret in frets if fret is not None]
    rows = max(MIN_FRETS_SHOWN, max(played) - base + 1)
    right = BOARD_LEFT + (STRINGS - 1) * STRING_GAP
    bottom = BOARD_TOP + rows * FRET_GAP

    cell.rounded(BOARD_LEFT - NECK_PAD, BOARD_TOP, right + NECK_PAD, bottom, 4, NECK)
    for row in range(1, rows + 1):
        y = BOARD_TOP + row * FRET_GAP
        cell.line(BOARD_LEFT - NECK_PAD, y, right + NECK_PAD, y, 1.4, FRET_LINE)
    for string in range(STRINGS):
        x = BOARD_LEFT + string * STRING_GAP
        cell.line(x, BOARD_TOP, x, bottom, 1.4, STAFF_LINE)

    if base == 1:
        cell.line(BOARD_LEFT - NECK_PAD, BOARD_TOP - 1, right + NECK_PAD, BOARD_TOP - 1, 4.5, INK)
    else:
        cell.line(BOARD_LEFT - NECK_PAD, BOARD_TOP, right + NECK_PAD, BOARD_TOP, 1.4, FRET_LINE)
        cell.text(BOARD_LEFT - NECK_PAD - 7, BOARD_TOP + FRET_GAP / 2, f"{base}", SANS_BOLD, 15, MUTED, "rm")

    dots = []
    for string, (fret, finger) in enumerate(zip(frets, fingers)):
        x = BOARD_LEFT + string * STRING_GAP
        if fret is None:
            cell.line(x - 4, BOARD_TOP - 19, x + 4, BOARD_TOP - 11, 1.8, MUTED)
            cell.line(x - 4, BOARD_TOP - 11, x + 4, BOARD_TOP - 19, 1.8, MUTED)
        elif fret == 0:
            cell.circle(x, BOARD_TOP - 15, 5.5, CARD, colour, 2)
        else:
            dots.append((x, BOARD_TOP + (fret - base + 0.5) * FRET_GAP, fret, finger, string))

    # A finger laid flat across several strings is a barre, drawn behind its dots.
    for finger in sorted({dot[3] for dot in dots}):
        held = [dot for dot in dots if dot[3] == finger]
        fret = held[0][2]
        first, last = held[0], held[-1]
        between = [f for f in frets[first[4]:last[4] + 1]]
        if (len(held) > 1 and {dot[2] for dot in held} == {fret}
                and all(f is not None and f >= fret for f in between)):
            cell.line(first[0], first[1], last[0], last[1], DOT_RADIUS * 2, colour)

    for x, y, _, finger, _ in dots:
        cell.circle(x, y, DOT_RADIUS, colour)
        cell.text(x, y - 0.5, str(finger), SANS_BOLD, 12, "#ffffff")


def _draw_tab(cell, frets):
    bottom = TAB_TOP + (STRINGS - 1) * TAB_GAP
    for line in range(STRINGS):
        y = TAB_TOP + line * TAB_GAP
        cell.line(STAFF_LEFT, y, STAFF_RIGHT, y, 1.1, STAFF_LINE)
    cell.line(STAFF_LEFT, TAB_TOP, STAFF_LEFT, bottom, 1.1, STAFF_LINE)
    cell.line(STAFF_RIGHT, TAB_TOP, STAFF_RIGHT, bottom, 1.1, STAFF_LINE)
    cell.text(STAFF_LEFT + 14, TAB_TOP + (STRINGS - 1) / 2 * TAB_GAP, "TAB", SANS_BOLD, 9, MUTED)

    # The highest string is the top line of the tab.
    for line, fret in enumerate(reversed(frets)):
        if fret is None:
            continue
        x, y = cell.point(chart_common.NOTE_X, TAB_TOP + line * TAB_GAP)
        half_width = (4.5 if fret < 10 else 8) * cell.factor
        half_height = 5.5 * cell.factor
        cell.draw.rectangle((x - half_width, y - half_height, x + half_width, y + half_height), fill=CARD)
        cell.text(chart_common.NOTE_X, TAB_TOP + line * TAB_GAP - 0.3, str(fret), SANS_BOLD, 11)


def render_chord(chord, scale=1.0, depth="All", columns=chart_common.COLUMNS):
    """Draw the voicings of a chord, such as "a#7", at a depth from DEPTHS as a PIL image.

    CAGED shapes are drawn in their colours. When a chord has them, its other shapes are grey.
    """
    title = chart_common.chord_title(chord)
    shown = shown_voicings(chord, depth)
    has_figures = any(name for _, name in shown)

    def draw_cell(cell, index):
        voicing, name = shown[index]
        frets, fingers = parse_voicing(voicing)
        if name == AUG:
            colour = fretted_drawer.FIGURE_COLOURS[0]
        else:
            colour = COLOURS[name[0]] if name else (fretted_drawer.OTHER_COLOUR if has_figures else ACCENT)
        fretted_drawer.draw_card(cell, name, colour)
        cell.title(chart_common.TITLE_X, chart_common.TITLE_Y + 9, title, chart_common.TITLE_SIZE)
        _draw_fretboard(cell, frets, fingers, colour)
        chart_common._draw_staff(cell, chord, frets, OPEN_STRINGS)
        _draw_tab(cell, frets)

    return fretted_drawer.draw_grid(len(shown), draw_cell, scale, columns)
