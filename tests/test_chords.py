"""Checks that every chord shape on every instrument is right and playable.

Each shape must play only notes of its chord and hold the root and third (and the
seventh of a seventh chord). Its fingers must be ones a hand can hold. Chord figures
must appear wherever they make the chord, and standard open chords must be there.
"""
import pytest

import chart_common
import fretted_drawer
import guitar_drawer
import piano_drawer

ROOTS = ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b")
QUALITIES = ("", "-", "7", "+", "°")
CHORDS = [root + quality for root in ROOTS for quality in QUALITIES]
TUNINGS = [(instrument, tuning) for instrument, tunings in fretted_drawer.INSTRUMENTS.items() for tuning in tunings]
TUNING_IDS = [f"{instrument}/{tuning.name}" for instrument, tuning in TUNINGS]
GUITAR_STRINGS = (52, 57, 62, 67, 71, 76)
DEPTH_CHOICES = [("All",), *[(name,) for name in fretted_drawer.DEPTHS if name != "All"],
                 ("Low (1–5)", "Mid (6–10)"), ("Mid (6–10)", "High (11+)"), ("Low (1–5)", "High (11+)")]


def check_notes(chord, pitches):
    """pitches: the pitch class each string plays, or None for a string left out."""
    root, third, fifth, seventh = fretted_drawer._chord_tones(chord)
    played = {p for p in pitches if p is not None}
    assert played <= set(chart_common.spell_chord(chord)), "a note outside the chord"
    assert {root, third} <= played, "no root or third"
    if seventh is not None:
        assert seventh in played, "no seventh"
    else:
        assert fifth in played, "a triad without its fifth"


def check_fingers(frets, fingers):
    held = [(fret, finger, string) for string, (fret, finger) in enumerate(zip(frets, fingers)) if fret]
    assert all(finger for _, finger, _ in held), "a fretted note without a finger"
    assert not any(finger and not fret for fret, finger in zip(frets, fingers)), "a finger on an open string"
    assert all(1 <= finger <= 4 for _, finger, _ in held), "more than four fingers"
    for fret_a, finger_a, _ in held:
        for fret_b, finger_b, _ in held:
            if fret_a < fret_b:
                assert finger_a < finger_b, "fingers out of order with the frets"
    by_finger = {}
    for fret, finger, string in held:
        by_finger.setdefault(finger, []).append((fret, string))
    for notes in by_finger.values():
        if len(notes) > 1:
            fret = notes[0][0]
            strings = range(min(s for _, s in notes), max(s for _, s in notes) + 1)
            assert all(frets[s] and frets[s] >= fret for s in strings), "a barre over a lower or open string"
    reach = [fret for fret, _, _ in held]
    if reach:
        assert max(reach) - min(reach) <= 4, "a reach over four frets"


@pytest.mark.parametrize(("instrument", "tuning"), TUNINGS, ids=TUNING_IDS)
@pytest.mark.parametrize("chord", CHORDS)
def test_fretted_shapes(instrument, tuning, chord):
    shapes = fretted_drawer.voicings(instrument, tuning.name, chord)
    assert shapes, "no shapes"
    seen = set()
    for voicing, _ in shapes:
        frets, fingers = fretted_drawer.parse_voicing(voicing)
        assert frets not in seen, "the same shape twice"
        seen.add(frets)
        check_notes(chord, [None if f is None else (tuning.strings[s] + fretted_drawer.sounding_offset(tuning, s, f)) % 12
                            for s, f in enumerate(frets)])
        check_fingers(frets, fingers)
        if tuning.drone:
            assert frets[0] is None or frets[0] == 0 or frets[0] > fretted_drawer.DRONE_START, \
                "the 5th string fretted below its peg"
    for depth in DEPTH_CHOICES:
        assert fretted_drawer.at_depth(tuning, shapes, depth), f"nothing at {depth}"


@pytest.mark.parametrize(("instrument", "tuning"), TUNINGS, ids=TUNING_IDS)
@pytest.mark.parametrize("chord", CHORDS)
def test_figures_come_first_and_everywhere(instrument, tuning, chord):
    shapes = fretted_drawer.voicings(instrument, tuning.name, chord)
    names = [name for _, name in shapes]
    if None in names:
        assert not any(names[names.index(None):]), "a figure after an other shape"
    main_strings = tuning.strings[1:] if tuning.drone else tuning.strings
    shown = {}
    for voicing, name in shapes:
        frets = fretted_drawer.parse_voicing(voicing)[0]
        shown[frets[1:] if tuning.drone else frets] = name
    _, quality = chart_common.split_chord_name(chord)
    root = fretted_drawer._chord_tones(chord)[0]
    for figure in tuning.figures:
        if figure.quality != quality:
            continue
        for shift in range(chart_common.MAX_FRET + 1):
            frets = tuple(None if o is None else o + shift for o in figure.offsets)
            if max(f for f in frets if f is not None) > chart_common.MAX_FRET:
                break
            pitches = {(p + f) % 12 for p, f in zip(main_strings, frets) if f is not None}
            if pitches <= set(chart_common.spell_chord(chord)) and root in pitches:
                assert shown.get(frets), f"{figure.name or figure.offsets} missing at {frets}"


@pytest.mark.parametrize("chord", CHORDS)
def test_guitar_shapes(chord):
    shapes = guitar_drawer.VOICINGS[chord]
    names = [name for _, name in shapes]
    for voicing, name in shapes:
        frets, fingers = guitar_drawer.parse_voicing(voicing)
        pitches = [None if f is None else (GUITAR_STRINGS[s] + f) % 12 for s, f in enumerate(frets)]
        check_notes(chord, pitches)
        check_fingers(frets, fingers)
        if name and not name.startswith("Aug"):
            lowest = next(p for p in pitches if p is not None)
            assert lowest == fretted_drawer._chord_tones(chord)[0], "a CAGED shape without its root in the bass"
    _, quality = chart_common.split_chord_name(chord)
    if quality in ("", "-", "7"):
        for letter in guitar_drawer.CAGED:
            assert fretted_drawer.shape_name(letter.lower(), quality) in names, f"no {letter}-shape"
    for depth in DEPTH_CHOICES:
        assert guitar_drawer.shown_voicings(chord, depth), f"nothing at {depth}"


@pytest.mark.parametrize("chord", CHORDS)
@pytest.mark.parametrize("inversion", range(4))
def test_piano_inversions(chord, inversion):
    tones = [t for t in fretted_drawer._chord_tones(chord) if t is not None]
    used = min(inversion, len(tones) - 1)  # A triad shows a 3rd inversion as its 2nd
    pitches = piano_drawer.chord_pitches(chord, used)
    assert {p % 12 for p in pitches} == set(tones)
    assert min(pitches) % 12 == tones[used], "the wrong lowest note"


# Open chords that chord charts agree on, as frets from the left of the chart
STANDARD_CHORDS = {
    ("Ukulele", "Standard"): {
        "c": "0 0 0 3", "d": "2 2 2 0", "e": "4 4 4 2", "f": "2 0 1 0", "g": "0 2 3 2", "a": "2 1 0 0", "b": "4 3 2 2",
        "c-": "0 3 3 3", "d-": "2 2 1 0", "e-": "0 4 3 2", "f-": "1 0 1 3", "g-": "0 2 3 1", "a-": "2 0 0 0",
        "b-": "4 2 2 2", "c7": "0 0 0 1", "d7": "2 2 2 3", "e7": "1 2 0 2", "f7": "2 3 1 3", "g7": "0 2 1 2",
        "a7": "0 1 0 0", "b7": "2 3 2 2"},
    ("Baritone ukulele", "Standard"): {
        "g": "0 0 0 3", "c": "2 0 1 0", "d": "0 2 3 2", "e": "2 1 0 0", "a": "2 2 2 0", "a-": "2 2 1 0",
        "e-": "2 0 0 0", "d-": "0 2 3 1", "g7": "0 0 0 1", "d7": "0 2 1 2", "e7": "0 1 0 0", "a7": "2 2 2 3"},
    ("Tenor banjo", "Standard"): {"c": "0 0 2 3", "g": "2 0 0 2", "f": "0 2 3 0"},
    # Tradtab's Irish (GDAE) chord chart
    ("Tenor banjo", "Irish"): {
        "g": "0 0 2 3", "d": "2 0 0 2", "a": "2 2 4 0", "c": "0 2 3 0", "e-": "0 2 2 0", "a-": "2 2 3 0",
        "b-": "4 0 2 2", "d-": "2 0 0 1", "g7": "0 0 2 1", "d7": "2 0 3 2", "a7": "2 2 4 3"},
    # On the four long strings, without the 5th
    ("Banjo", "Open G"): {"g": "0 0 0 0", "c": "2 0 1 2", "d": "0 2 3 4", "e-": "2 0 0 2", "d7": "0 2 1 4",
                          "a": "2 2 2 2", "f": "3 2 1 3", "g7": "0 0 0 3"},
    ("Banjo", "Double C"): {"c": "0 0 0 2", "f": "0 2 0 3", "g7": "2 4 5 5"},
}
GUITAR_STANDARD = {
    "c": "x 3 2 0 1 0", "a": "x 0 2 2 2 0", "g": "3 2 0 0 0 3", "e": "0 2 2 1 0 0", "d": "x x 0 2 3 2",
    "a-": "x 0 2 2 1 0", "e-": "0 2 2 0 0 0", "d-": "x x 0 2 3 1", "c7": "x 3 2 3 1 0", "g7": "3 2 0 0 0 1",
    "e7": "0 2 0 1 0 0", "a7": "x 0 2 0 2 0", "d7": "x x 0 2 1 2", "b7": "x 2 1 2 0 2", "f": "1 3 3 2 1 1",
}


def parse_frets(text):
    return tuple(None if f == "x" else int(f) for f in text.split())


@pytest.mark.parametrize(("instrument", "tuning", "chord", "frets"),
                         [(i, t, c, f) for (i, t), chords in STANDARD_CHORDS.items() for c, f in chords.items()])
def test_standard_chords_are_there(instrument, tuning, chord, frets):
    drone = fretted_drawer.get_tuning(instrument, tuning).drone
    shapes = {fretted_drawer.parse_voicing(v)[0][1 if drone else 0:] for v, _ in
              fretted_drawer.voicings(instrument, tuning, chord)}
    assert parse_frets(frets) in shapes


@pytest.mark.parametrize(("chord", "frets"), GUITAR_STANDARD.items())
def test_standard_guitar_chords_are_there(chord, frets):
    assert parse_frets(frets) in {guitar_drawer.parse_voicing(v)[0] for v, _ in guitar_drawer.VOICINGS[chord]}


@pytest.mark.parametrize(("first", "second", "shift"), [
    (("Tenor banjo", "Standard"), ("Tenor banjo", "Irish"), 7),     # GDAE is CGDA a fifth up
    (("Ukulele", "Standard"), ("Baritone ukulele", "Standard"), 7),  # DGBE is gCEA a fifth up
    (("Ukulele", "Standard"), ("Ukulele", "Low G"), 0),              # Only the g moves, an octave
])
def test_related_tunings_share_shapes(first, second, shift):
    for index, root in enumerate(ROOTS):
        for quality in QUALITIES:
            a = {fretted_drawer.parse_voicing(v)[0] for v, _ in fretted_drawer.voicings(*first, root + quality)}
            b = {fretted_drawer.parse_voicing(v)[0] for v, _ in
                 fretted_drawer.voicings(*second, ROOTS[(index + shift) % 12] + quality)}
            assert a == b, root + quality


def test_hand_picked_banjo_shapes_are_kept():
    import banjo_voicings
    for chord, picked in banjo_voicings.VOICINGS.items():
        shown = {v.split("/")[0].split(" ", 1)[1] for v, _ in fretted_drawer.voicings("Banjo", "Open G", chord)}
        for voicing in picked:
            assert voicing.split("/")[0] in shown, f"{chord} {voicing}"


@pytest.mark.parametrize(("instrument", "tuning"), TUNINGS, ids=TUNING_IDS)
def test_charts_draw(instrument, tuning):
    count = fretted_drawer.card_count("f#7", ("All",), instrument, tuning.name)
    image = fretted_drawer.render_chord("f#7", 0.25, ("All",), instrument, tuning.name,
                                        fretted_drawer.best_columns(count, 1000, 400))
    assert image.width > 0 and image.height > 0


def test_guitar_and_piano_charts_draw():
    assert guitar_drawer.render_chord("a-", 0.25).width > 0
    assert piano_drawer.render_chord("c7", 0.25, 3).width > 0


@pytest.fixture
def no_system_fonts(monkeypatch):
    """Only the bundled fonts load, as on a Mac or a Linux system without DejaVu."""
    truetype = chart_common.ImageFont.truetype
    bundled = {chart_common.BUNDLED_SANS, chart_common.BUNDLED_SANS_BOLD}

    def bundled_only(font, *args, **kwargs):
        if font not in bundled:
            raise OSError(f"{font} is not installed")
        return truetype(font, *args, **kwargs)

    monkeypatch.setattr(chart_common.ImageFont, "truetype", bundled_only)
    monkeypatch.setattr(chart_common, "_fonts", {})


@pytest.mark.parametrize("chord", ["c", "f#-", "a#7", "e+", "b°"])
def test_charts_draw_with_only_the_bundled_fonts(no_system_fonts, chord):
    assert piano_drawer.render_chord(chord).getbbox()
    assert guitar_drawer.render_chord(chord).getbbox()
    for instrument, tuning in TUNINGS:
        assert fretted_drawer.render_chord(chord, instrument=instrument, tuning=tuning.name).getbbox()
