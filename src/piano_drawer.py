"""Draws piano chord charts as antialiased keyboard diagrams.

A chart shows a keyboard of several octaves with the notes of a chord marked, so
inversions have room to move up the keyboard. Chord spelling and styling come from
chart_common. Like there, the chart is drawn at several times its size and scaled
down, which smooths every edge.
"""
import random

from PIL import Image, ImageDraw

import chart_common
from chart_common import (
    ACCENT, CARD, CARD_EDGE, CARD_RADIUS, CARD_SHADOW, INK, MUTED, NATURALS, PAGE,
    QUALITIES, SANS, SANS_BOLD, STAFF_LINE, SUPERSAMPLE,
)

LOWEST_OCTAVE = 4  # Octave number of the lowest C, where middle C is C4
OCTAVES = 3
WHITE_KEYS = OCTAVES * 7
LOWEST_PITCH = 12 * (LOWEST_OCTAVE + 1)  # MIDI number of the lowest C

# Layout, in pixels at scale 1
KEY_WIDTH = 36
KEY_HEIGHT = 150
BLACK_WIDTH = 22
BLACK_HEIGHT = 92
KEYBOARD_LEFT = 30
KEYBOARD_TOP = 84
CARD_MARGIN = 7
CANVAS_WIDTH = 2 * KEYBOARD_LEFT + WHITE_KEYS * KEY_WIDTH
CANVAS_HEIGHT = 270
TITLE_X = 24
TITLE_Y = 42

HIGHLIGHT_WHITE = "#f3c9bf"
HIGHLIGHT_BLACK = "#b8432c"
WHITE_KEY = "#ffffff"
BLACK_KEY = "#262a33"

# Names of the white keys in an octave, and the black keys after them
WHITE_PITCHES = NATURALS
BLACK_AFTER = {0: 1, 1: 3, 3: 6, 4: 8, 5: 10}  # White key index -> pitch class


INVERSION_NAMES = ("Root position", "1st inversion", "2nd inversion", "3rd inversion")


def pick_inversion(chord, chosen):
    """The inversion to show for a chord: a random one from the inversion numbers in chosen.

    A triad has no 3rd inversion, so a chosen 3rd is shown as its highest one, the 2nd.
    """
    count = len(chord_pitches(chord))
    return random.choice(sorted({min(number, count - 1) for number in chosen}))


def canvas_size(scale=1.0):
    """Size of the image render_chord returns, as (width, height)."""
    return round(CANVAS_WIDTH * scale), round(CANVAS_HEIGHT * scale)


def chord_pitches(chord, inversion=0):
    """The MIDI numbers of a chord, lowest first, with the root in the lowest octave.

    Each inversion moves the lowest note up an octave, so a seventh chord has
    inversions 0 to 3 and a triad 0 to 2.
    """
    root, quality = chart_common.split_chord_name(chord)
    name = chart_common.FLAT_ROOTS.get(chord, root.upper())
    letter = chart_common.LETTERS.index(name[0])
    accidental = {"": 0, "#": 1, "b": -1}[name[1:]]
    root_pitch = LOWEST_PITCH + (NATURALS[letter] + accidental) % 12
    pitches = [root_pitch] + [root_pitch + semitones for semitones in QUALITIES[quality]]
    if not 0 <= inversion < len(pitches):
        raise ValueError(f"{chord} has no inversion {inversion}")
    return sorted(pitches[inversion:] + [pitch + 12 for pitch in pitches[:inversion]])


def key_label(chord, pitch):
    """The note name shown on a key, spelled for the chord, such as "E♭"."""
    letter, accidental = chart_common.spell_chord(chord)[pitch % 12]
    return (chart_common.LETTERS[letter] + {0: "", 1: "♯", -1: "♭", 2: "𝄪", -2: "𝄫"}[accidental])


def _white_key_x(index):
    return KEYBOARD_LEFT + index * KEY_WIDTH


def _white_index(pitch):
    """Index of a white key from the left of the keyboard."""
    octave, pitch_class = divmod(pitch - LOWEST_PITCH, 12)
    return octave * 7 + WHITE_PITCHES.index(pitch_class)


def _key_geometry(pitch):
    """The (left, right, is_black) of a key in layout units."""
    octave, pitch_class = divmod(pitch - LOWEST_PITCH, 12)
    if pitch_class in WHITE_PITCHES:
        left = _white_key_x(octave * 7 + WHITE_PITCHES.index(pitch_class))
        return left, left + KEY_WIDTH, False
    boundary = _white_key_x(octave * 7 + WHITE_PITCHES.index(pitch_class - 1) + 1)
    return boundary - BLACK_WIDTH / 2, boundary + BLACK_WIDTH / 2, True


def _label(cell, x, y, text, size):
    """White text centred on (x, y), taking symbols such as ♯ from a symbol font."""
    font = cell.font(SANS_BOLD, size)
    symbols = cell.font(chart_common.SYMBOLS, size * 0.9)
    parts = [(char, symbols if not chart_common._has_glyph(font, char)
              and chart_common._has_glyph(symbols, char) else font) for char in text]
    px, py = cell.point(x, y - 0.5)
    px -= sum(f.getlength(c) for c, f in parts) / 2
    for char, use in parts:
        cell.draw.text((px, py), char, font=use, fill="#ffffff", anchor="lm")
        px += use.getlength(char)


def _draw_keyboard(cell, chord, pitches):
    marked = set(pitches)
    root_class = chord_pitches(chord)[0] % 12
    bottom = KEYBOARD_TOP + KEY_HEIGHT
    all_pitches = range(LOWEST_PITCH, LOWEST_PITCH + 12 * OCTAVES)

    for pitch in all_pitches:
        left, right, black = _key_geometry(pitch)
        if not black:
            fill = HIGHLIGHT_WHITE if pitch in marked else WHITE_KEY
            cell.rounded(left, KEYBOARD_TOP - 6, right, bottom, 5, fill, STAFF_LINE, 1.2)
    # Square off the tops of the white keys, which are rounded only at the bottom
    for pitch in all_pitches:
        left, right, black = _key_geometry(pitch)
        if not black:
            fill = HIGHLIGHT_WHITE if pitch in marked else WHITE_KEY
            cell.rounded(left + 1, KEYBOARD_TOP - 1, right - 1, KEYBOARD_TOP + 12, 0, fill)
    for pitch in all_pitches:
        left, right, black = _key_geometry(pitch)
        if black:
            fill = HIGHLIGHT_BLACK if pitch in marked else BLACK_KEY
            cell.rounded(left, KEYBOARD_TOP - 1, right, KEYBOARD_TOP + BLACK_HEIGHT, 3, fill)

    for pitch in all_pitches:
        left, right, black = _key_geometry(pitch)
        if pitch % 12 == 0:
            octave = pitch // 12 - 1
            cell.text((left + right) / 2, bottom + 17, f"C{octave}", SANS, 12, MUTED)
        if pitch in marked:
            is_root = pitch % 12 == root_class
            x = (left + right) / 2
            y = KEYBOARD_TOP + BLACK_HEIGHT - 17 if black else bottom - 22
            cell.circle(x, y, 11, INK if is_root else ACCENT)
            _label(cell, x, y, key_label(chord, pitch), 12)


def render_chord(chord, scale=1.0, inversion=0):
    """Draw a chord, such as "a#7", on a keyboard and return it as a PIL image."""
    width, height = canvas_size(scale)
    image = Image.new("RGB", (width * SUPERSAMPLE, height * SUPERSAMPLE), PAGE)
    cell = chart_common._Cell(ImageDraw.Draw(image), 0, 0, scale)

    cell.rounded(CARD_MARGIN, CARD_MARGIN + 3, CANVAS_WIDTH - CARD_MARGIN, CANVAS_HEIGHT - CARD_MARGIN + 3,
                 CARD_RADIUS, CARD_SHADOW)
    cell.rounded(CARD_MARGIN, CARD_MARGIN, CANVAS_WIDTH - CARD_MARGIN, CANVAS_HEIGHT - CARD_MARGIN,
                 CARD_RADIUS, CARD, CARD_EDGE, 1.2)
    cell.title(TITLE_X, TITLE_Y + 9, chart_common.chord_title(chord), chart_common.TITLE_SIZE)
    cell.text(CANVAS_WIDTH - 24, TITLE_Y, INVERSION_NAMES[inversion], SANS, 15, MUTED, "rm")

    _draw_keyboard(cell, chord, chord_pitches(chord, inversion))
    return image.resize((width, height), Image.LANCZOS)
