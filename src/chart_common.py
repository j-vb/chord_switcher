"""What every chord chart shares: chord spelling, the card, the staff, fonts and colours.

The drawers draw each chart at several times its size and scale it down, which
smooths every edge. The fretted instruments lay their cards out on the grid set
here, one card per voicing: name, fretboard, staff and tab.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

LETTERS = "CDEFGAB"
NATURALS = (0, 2, 4, 5, 7, 9, 11)  # Pitch class of each letter in LETTERS

# Semitones above the root of the third, fifth and (optionally) seventh.
QUALITIES = {
    "": (4, 7),
    "-": (3, 7),
    "7": (4, 7, 10),
    "+": (4, 8),
    "°": (3, 6),
}

# Augmented chords on these roots are spelled with flats, as a sharp root would
# need a double-sharp fifth.
FLAT_ROOTS = {"a#+": "Bb", "d#+": "Eb", "g#+": "Ab"}


MAX_FRET = 19  # Highest fret a drawn voicing may use

# How far up the neck to play, as the range of the lowest fretted fret of a voicing.
# Open strings don't count, so "0 0 0 0" is as low as it gets. The segments are the
# same for every fretboard instrument: the neck repeats an octave higher from the
# twelfth fret, so the three segments cover the first fifteen frets or so.
DEPTHS = {"All": (0, 99), "Low (1–5)": (0, 5), "Mid (6–10)": (6, 10), "High (11+)": (11, 99)}


def lowest_fret(frets):
    """The lowest fretted fret of a voicing, or 0 when it only has open or muted strings."""
    fretted = [fret for fret in frets if fret]
    return min(fretted) if fretted else 0


# Layout, in pixels at scale 1. Each voicing gets a card in a grid of cells, up to
# COLUMNS wide unless the app asks for another width. Cards are centred in each row.
COLUMNS = 4
CELL_WIDTH = 345
CELL_HEIGHT = 295
CARD_MARGIN = 7
CARD_RADIUS = 18

TITLE_X = 24
TITLE_Y = 33
TITLE_SIZE = 27


STAFF_LEFT = 172
STAFF_RIGHT = 324
STAFF_TOP = 120
STAFF_GAP = 8
NOTE_X = STAFF_LEFT + 76


# Colours
PAGE = "#ffffff"
CARD = "#faf8f4"
CARD_EDGE = "#e4dfd5"
CARD_SHADOW = "#efebe3"
INK = "#262a33"
MUTED = "#8d887e"
STAFF_LINE = "#6b675f"
FRET_LINE = "#c4bcad"
NECK = "#f1eadc"
ACCENT = "#d4553a"

# Treble clef outline in staff gaps from where it crosses the G line, for
# systems without a font that has the clef.
CLEF = (
    (0.2, 0.5), (-0.5, 0.1), (-0.2, -0.6), (0.7, -0.5), (1.0, 0.3), (0.4, 1.0),
    (-0.7, 0.6), (-1.2, -0.4), (-0.6, -1.5), (0.5, -2.4), (0.9, -3.4), (0.4, -4.0),
    (0.1, -3.2), (0.2, -1.5), (0.6, 1.2), (0.7, 1.9), (0.2, 2.3), (-0.3, 2.0),
)


def split_chord_name(chord):
    """Split a chord name such as "a#7" into its root and quality."""
    root_length = 2 if chord[1:2] == "#" else 1
    return chord[:root_length], chord[root_length:]


def spell_chord(chord):
    """Map each pitch class in a chord to its spelling as (letter index, accidental)."""
    root, quality = split_chord_name(chord)
    name = FLAT_ROOTS.get(chord, root.upper())
    letter = LETTERS.index(name[0])
    accidental = {"": 0, "#": 1, "b": -1}[name[1:]]
    root_pitch = NATURALS[letter] + accidental

    spelling = {root_pitch % 12: (letter, accidental)}
    for step, semitones in zip((2, 4, 6), QUALITIES[quality]):
        tone_letter = (letter + step) % 7
        pitch = (root_pitch + semitones) % 12
        # The difference between the tone and its plain letter, from -6 to 5.
        spelling[pitch] = (tone_letter, (pitch - NATURALS[tone_letter] + 6) % 12 - 6)
    return spelling


def written_notes(chord, frets, open_strings):
    """List the notes of a voicing as (staff position, accidental), lowest first.

    The staff position counts letter names from C0, so each step is a line or a
    space. Strings that sound the same note appear once, and muted strings
    (a fret of None) don't appear.
    """
    spelling = spell_chord(chord)
    notes = set()
    for open_pitch, fret in zip(open_strings, frets):
        if fret is None:
            continue
        pitch = open_pitch + fret
        letter, accidental = spelling[pitch % 12]
        octave = (pitch - NATURALS[letter] - accidental) // 12 - 1
        notes.add((octave * 7 + letter, accidental))
    return sorted(notes)


def chord_title(chord):
    """The display name of a chord, such as "A♯m" for "a#-"."""
    root, quality = split_chord_name(chord)
    name = FLAT_ROOTS.get(chord, root.upper())
    name = name.replace("#", "♯").replace("b", "♭")
    return name + {"": "", "-": "m", "7": "⁷", "+": "⁺", "°": "°"}[quality]


# The chart is drawn this many times larger than shown, then scaled down.
SUPERSAMPLE = 4

# The system fonts to try first, then the bundled DejaVu fonts, so every system
# has one. Pillow matches file names exactly, so macOS's Arial.ttf is listed too.
BUNDLED_FONTS = Path(__file__).resolve().parent / "assets" / "fonts"
BUNDLED_SANS = str(BUNDLED_FONTS / "DejaVuSans.ttf")
BUNDLED_SANS_BOLD = str(BUNDLED_FONTS / "DejaVuSans-Bold.ttf")
SANS = ("segoeui.ttf", "arial.ttf", "Arial.ttf", "Lato-Medium.ttf", "DejaVuSans.ttf",
        "LiberationSans-Regular.ttf", BUNDLED_SANS)
SANS_BOLD = ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "Arial Bold.ttf", "Lato-Bold.ttf",
             "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", BUNDLED_SANS_BOLD)
# Fonts that hold the musical symbols (clef, sharp, flat) and superscripts.
SYMBOLS = ("seguisym.ttf", "DejaVuSans.ttf", BUNDLED_SANS)

_fonts = {}


def _load_font(names, size):
    """The first font in names that can be loaded at this size, or None."""
    key = (names, size)
    if key not in _fonts:
        _fonts[key] = None
        for name in names:
            try:
                _fonts[key] = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
    return _fonts[key]


def _has_glyph(font, char):
    """Whether the font draws char, rather than its box for a missing glyph."""
    if font is None:
        return False
    mask = font.getmask(char)
    missing = font.getmask("\U0010FFFF")
    return mask.getbbox() is not None and (mask.size, bytes(mask)) != (missing.size, bytes(missing))


def _spline(points, steps=8):
    """Points along a Catmull-Rom curve through the given points."""
    padded = [points[0], *points, points[-1]]
    curve = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1:i + 3]
        for step in range(steps):
            t = step / steps
            curve.append(tuple(
                0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                       + (-a + 3 * b - 3 * c + d) * t ** 3)
                for a, b, c, d in zip(p0, p1, p2, p3)
            ))
    curve.append(points[-1])
    return curve


class _Cell:
    """Draws on an image in the layout units of one voicing card."""

    def __init__(self, draw, left, top, scale):
        self.draw = draw
        self.factor = scale * SUPERSAMPLE
        self.left = left
        self.top = top

    def point(self, x, y):
        return (self.left + x) * self.factor, (self.top + y) * self.factor

    def width(self, units):
        return max(1, round(units * self.factor))

    def font(self, names, units):
        return _load_font(names, max(6, round(units * self.factor)))

    def _dot(self, x, y, radius, fill):
        self.draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)

    def _stroke(self, coords, width, fill):
        """A line with round ends and joins through device coordinates."""
        self.draw.line(coords, fill=fill, width=width, joint="curve")
        for x, y in (coords[0], coords[-1]):
            self._dot(x, y, width / 2, fill)

    def line(self, x1, y1, x2, y2, width=1.0, fill=INK):
        self._stroke([self.point(x1, y1), self.point(x2, y2)], self.width(width), fill)

    def curve(self, points, width=1.0, fill=INK):
        smooth = _spline([self.point(x, y) for x, y in points])
        self._stroke(smooth, self.width(width), fill)

    def circle(self, x, y, radius, fill, outline=None, width=1.0):
        cx, cy = self.point(x, y)
        r = radius * self.factor
        if outline:
            self._dot(cx, cy, r, outline)
            r -= self.width(width)
        self._dot(cx, cy, r, fill)

    def rounded(self, x1, y1, x2, y2, radius, fill, outline=None, width=1.0):
        (px1, py1), (px2, py2) = self.point(x1, y1), self.point(x2, y2)
        self.draw.rounded_rectangle(
            (px1, py1, px2, py2), radius * self.factor, fill=fill,
            outline=outline, width=self.width(width),
        )

    def text(self, x, y, text, names, size, fill=INK, anchor="mm"):
        self.draw.text(self.point(x, y), text, font=self.font(names, size), fill=fill, anchor=anchor)

    def title(self, x, y, text, size):
        """Text anchored at its left that takes symbols such as ♯ from a symbol font."""
        font = self.font(SANS_BOLD, size)
        symbols = self.font(SYMBOLS, size * 0.9)
        px, py = self.point(x, y)
        for char in text:
            use = symbols if not _has_glyph(font, char) and _has_glyph(symbols, char) else font
            self.draw.text((px, py), char, font=use, fill=INK, anchor="ls")
            px += use.getlength(char) + 0.04 * size * self.factor


def _draw_card(cell, index, count):
    cell.rounded(CARD_MARGIN, CARD_MARGIN + 3, CELL_WIDTH - CARD_MARGIN, CELL_HEIGHT - CARD_MARGIN + 3,
                 CARD_RADIUS, CARD_SHADOW)
    cell.rounded(CARD_MARGIN, CARD_MARGIN, CELL_WIDTH - CARD_MARGIN, CELL_HEIGHT - CARD_MARGIN,
                 CARD_RADIUS, CARD, CARD_EDGE, 1.2)
    if count > 1:
        cell.text(CELL_WIDTH - 24, TITLE_Y - 9, f"{index + 1} / {count}", SANS, 13, MUTED, "rm")


def _draw_clef(cell, g_line):
    """A treble clef from a symbol font, or a hand-drawn outline without one."""
    font = cell.font(SYMBOLS, 6.9 * STAFF_GAP)
    if _has_glyph(font, "\U0001D11E"):
        # The glyph's baseline sits on the G line.
        cell.draw.text(cell.point(STAFF_LEFT + 24, g_line + 1.55 * STAFF_GAP), "\U0001D11E",
                       font=font, fill=INK, anchor="ms")
        return
    x = STAFF_LEFT + 24
    points = [(x + dx * STAFF_GAP, g_line + dy * STAFF_GAP) for dx, dy in CLEF]
    cell.curve(points, 2)
    last = points[-1]
    cell.circle(last[0], last[1], 2, INK)


def _draw_note_head(cell, x, y):
    half_width, half_height = 5.4, 3.8
    tilt = math.radians(-22)
    points = []
    for i in range(48):
        angle = 2 * math.pi * i / 48
        dx = half_width * math.cos(angle)
        dy = half_height * math.sin(angle)
        points.append(cell.point(
            x + dx * math.cos(tilt) - dy * math.sin(tilt),
            y + dx * math.sin(tilt) + dy * math.cos(tilt),
        ))
    cell.draw.polygon(points, fill=INK)


def _draw_accidental(cell, x, y, accidental):
    if accidental == 1:  # Sharp
        cell.line(x - 1.8, y - 8, x - 1.8, y + 8, 1.1)
        cell.line(x + 1.8, y - 8.5, x + 1.8, y + 7.5, 1.1)
        cell.line(x - 4.5, y - 1.5, x + 4.5, y - 3.5, 2.2)
        cell.line(x - 4.5, y + 3.5, x + 4.5, y + 1.5, 2.2)
    elif accidental == 2:  # Double sharp
        cell.line(x - 3.2, y - 3.2, x + 3.2, y + 3.2, 1.8)
        cell.line(x - 3.2, y + 3.2, x + 3.2, y - 3.2, 1.8)
    elif accidental < 0:  # Flat, drawn twice for a double flat
        for i in range(-accidental):
            flat_x = x - i * 7
            cell.line(flat_x - 2.5, y - 11, flat_x - 2.5, y + 4, 1.2)
            cell.curve(
                [(flat_x - 2.5, y - 2), (flat_x + 1, y - 4), (flat_x + 3, y - 2),
                 (flat_x + 1, y + 1), (flat_x - 2.5, y + 4)],
                1.7,
            )


def _draw_staff(cell, chord, frets, open_strings):
    step = STAFF_GAP / 2
    staff_bottom = STAFF_TOP + 4 * STAFF_GAP

    E4 = 4 * 7 + LETTERS.index("E")
    top_line = E4 + 8

    def line_y(position):
        return staff_bottom - (position - E4) * step

    for line in range(5):
        y = STAFF_TOP + line * STAFF_GAP
        cell.line(STAFF_LEFT, y, STAFF_RIGHT, y, 1.1, STAFF_LINE)
    cell.line(STAFF_RIGHT, STAFF_TOP, STAFF_RIGHT, staff_bottom, 1.1, STAFF_LINE)

    _draw_clef(cell, line_y(E4 + 2))

    notes = written_notes(chord, frets, open_strings)

    # Notes one step apart can't share a column, so the upper one moves right.
    previous = None
    shifted = False
    accidentals = []
    for position, accidental in notes:
        shifted = previous is not None and position - previous == 1 and not shifted
        previous = position
        x = NOTE_X + (11 if shifted else 0)
        y = line_y(position)

        for ledger in range(E4 - 2, position - 1, -2):
            cell.line(x - 9, line_y(ledger), x + 9, line_y(ledger), 1.3, STAFF_LINE)
        for ledger in range(top_line + 2, position + 1, 2):
            cell.line(x - 9, line_y(ledger), x + 9, line_y(ledger), 1.3, STAFF_LINE)

        _draw_note_head(cell, x, y)
        if accidental:
            accidentals.append((position, accidental))

    # Accidentals fill columns from the top down, moving left when they'd touch.
    placed = []
    for position, accidental in reversed(accidentals):
        column = 0
        while any(c == column and p - position < 6 for p, c in placed):
            column += 1
        placed.append((position, column))
        _draw_accidental(cell, NOTE_X - 14 - column * 10, line_y(position), accidental)


