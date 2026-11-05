"""The chord switcher app, built with Flet.

The menu picks an instrument and the kinds of chord, and the practice view shows
a random chord every few seconds, with its chart when help is on. The charts are
drawn by the drawer modules as Pillow images.
"""
import asyncio
import io
import random
import time
from pathlib import Path

import flet as ft
from PIL import Image, ImageChops

import chart_common
import fretted_drawer
import guitar_drawer
import piano_drawer

# The kinds of chord, each with an example of how it is written
CHORD_KINDS = {"Major": "", "Minor": "-", "Seventh": "7", "Augmented": "+", "Diminished": "°"}
ROOTS = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]

# The module that draws the chords of each instrument, in the order of the menu
DRAWERS = {"Piano": piano_drawer, "Guitar": guitar_drawer,
           **{name: fretted_drawer for name in fretted_drawer.INSTRUMENTS}}
FRETBOARD_DRAWERS = (guitar_drawer, fretted_drawer)  # These take a depth

# Short names for the menus
INVERSION_LABELS = ("Root", "1st", "2nd", "3rd")
DEPTH_LABELS = {"All": "All", "Low (1–5)": "Low 1–5", "Mid (6–10)": "Mid 6–10", "High (11+)": "High 11+"}

ACCENT = chart_common.ACCENT  # The charts' highlight colour, used as the app's seed colour
CHART_BG = chart_common.PAGE
MIN_INTERVAL, MAX_INTERVAL = 1, 30  # Seconds between chords
TICK = 0.03  # Seconds between timer updates
RELAYOUT_DELAY = 0.3  # Seconds after the last resize before the chart is drawn again
# Fonts don't all have the sharp, flat and other chord symbols, so a bundled one fills in
ASSETS = Path(__file__).resolve().parent / "assets"
FONTS = {"Symbols": "fonts/DejaVuSans-Bold.ttf"}
SYMBOLS = ft.TextStyle(font_family_fallback=list(FONTS))

WINDOW_SIZE = (1000, 700)
PRACTICE_PADDING = 36  # Around the practice view, left and right
CHART_PADDING = 12  # Inside the panel around the chart
# Height in the practice view that isn't the chart: bar, chord name, timer and gaps
PRACTICE_CHROME = 270
MIN_WINDOW_SIZE = (820, 640)


CHART_MARGIN = 12  # Pixels of background kept around a cropped chart


def chart_png(image):
    """A chart as PNG, cropped to what is drawn, since the drawers leave empty cells."""
    image = image.convert("RGB")
    box = ImageChops.difference(image, Image.new("RGB", image.size, CHART_BG)).getbbox()
    if box:
        left, top, right, bottom = box
        image = image.crop((max(0, left - CHART_MARGIN), max(0, top - CHART_MARGIN),
                            min(image.width, right + CHART_MARGIN), min(image.height, bottom + CHART_MARGIN)))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class Settings:
    """What the menu sets. It outlives the views, so going back keeps it."""

    def __init__(self):
        self.instrument = "Piano"
        self.tunings = {}  # Instrument -> the name of its picked tuning, when it has several
        self.depth = ("All",)  # "All", or one or two parts of the neck
        self.inversions = {0}
        self.interval = 3
        self.show_help = True
        self.kinds = {"Major"}

    @property
    def drawer(self):
        return DRAWERS[self.instrument]

    def tunings_of(self):
        """The tunings to choose from for the instrument; empty when it has one or none."""
        tunings = fretted_drawer.INSTRUMENTS.get(self.instrument, ())
        return tunings if len(tunings) > 1 else ()

    @property
    def tuning(self):
        tunings = fretted_drawer.INSTRUMENTS.get(self.instrument)
        return self.tunings.get(self.instrument, tunings[0].name) if tunings else None

    def chords(self):
        return [root + CHORD_KINDS[kind] for kind in CHORD_KINDS if kind in self.kinds for root in ROOTS]

    def caption(self):
        """The instrument and its options, shown at the top of the practice view."""
        parts = [self.instrument]
        if self.tunings_of():
            parts.append(self.tuning)
        if self.drawer in FRETBOARD_DRAWERS and self.depth != ("All",):
            parts.append(" + ".join(DEPTH_LABELS[name] for name in self.depth))
        return "  ·  ".join(parts)


class Chord:
    """A chord to show: its name, its inversion on the piano and, with help, its chart.

    A chart with many cards is laid out in the number of columns that draws them
    largest in the chart's space, given as (width, height). Drawing a chord again
    for another space takes the inversion it had.
    """

    def __init__(self, name, settings, space, inversion=None):
        self.name = name
        self.title = chart_common.chord_title(name)
        self.inversion = None
        self.chart = None
        self.columns = None
        options = {}
        if settings.drawer is piano_drawer:
            self.inversion = inversion if inversion is not None else piano_drawer.pick_inversion(
                name, sorted(settings.inversions))
            options["inversion"] = self.inversion
        elif settings.drawer in FRETBOARD_DRAWERS:
            options["depth"] = settings.depth
        if settings.drawer is fretted_drawer:
            options.update(instrument=settings.instrument, tuning=settings.tuning)
        if not settings.show_help:
            return
        if settings.drawer in FRETBOARD_DRAWERS:
            count = settings.drawer.card_count(name, **options)
            options["columns"] = self.columns = fretted_drawer.best_columns(count, *space)
        self.chart = chart_png(settings.drawer.render_chord(name, 1.0, **options))

    @property
    def inversion_name(self):
        return "" if self.inversion is None else piano_drawer.INVERSION_NAMES[self.inversion]


def card(title, *controls, expand=None):
    """A rounded panel with a title."""
    return ft.Container(
        content=ft.Column(
            [ft.Text(title, size=20, weight=ft.FontWeight.W_700), *controls],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,  # For small windows
        ),
        padding=28,
        border_radius=24,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        expand=expand,
    )


def field(label, control, top=22):
    """A small heading over a control."""
    return ft.Column(
        [ft.Text(label.upper(), size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT),
         control],
        spacing=10,
        margin=ft.Margin.only(top=top),
    )


def segments(values, labels):
    return [ft.Segment(value=str(value), label=ft.Text(label)) for value, label in zip(values, labels)]


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self.settings = Settings()
        self.session = 0  # Raised when a practice session ends, which stops its timer
        self.last_chord = None
        self.shown = None  # The Chord on screen
        self.resizes = 0  # Counts window resizes, so only the last one redraws the chart

        page.title = "Chord Switcher"
        page.theme_mode = ft.ThemeMode.SYSTEM
        page.theme = ft.Theme(color_scheme_seed=ACCENT)
        page.dark_theme = ft.Theme(color_scheme_seed=ACCENT)
        page.padding = 0
        page.fonts = FONTS
        page.window.width, page.window.height = WINDOW_SIZE
        page.window.min_width, page.window.min_height = MIN_WINDOW_SIZE
        page.on_keyboard_event = self.on_key
        page.on_resize = self.on_resize

        self.root = ft.AnimatedSwitcher(
            content=self.menu_view(),
            transition=ft.AnimatedSwitcherTransition.FADE,
            duration=220,
            reverse_duration=120,
            expand=True,
        )
        page.add(ft.SafeArea(self.root, expand=True))

    # Navigation

    def show(self, view):
        self.root.content = view
        self.page.update()

    def open_menu(self):
        self.session += 1
        self.show(self.menu_view())

    def start(self):
        if not self.settings.chords():
            return
        self.session += 1
        self.show(self.practice_view())
        self.page.run_task(self.practice, self.session)

    def on_key(self, e: ft.KeyboardEvent):
        if e.key == "Escape" and isinstance(self.root.content.data, Practice):
            self.open_menu()
        elif e.key == "Enter" and self.root.content.data == "menu":
            self.start()

    def toggle_theme(self, _):
        dark = self.page.theme_mode == ft.ThemeMode.DARK or (
            self.page.theme_mode == ft.ThemeMode.SYSTEM and self.page.platform_brightness == ft.Brightness.DARK)
        self.page.theme_mode = ft.ThemeMode.LIGHT if dark else ft.ThemeMode.DARK
        self.page.update()

    # The menu

    def menu_view(self):
        s = self.settings

        hint = ft.Text("", size=14, color=ft.Colors.ON_SURFACE_VARIANT)
        start_button = ft.FilledButton(
            "Start",
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            on_click=lambda _: self.start(),
            height=54,
            width=180,
            style=ft.ButtonStyle(
                text_style=ft.TextStyle(size=17, weight=ft.FontWeight.W_600),
                shape=ft.RoundedRectangleBorder(radius=16),
            ),
        )

        def refresh_start():
            none = not s.chords()
            start_button.disabled = none
            hint.value = "Pick at least one kind of chord" if none else "Press Enter to start"

        # Depth for instruments with a fretboard, inversions for the piano
        def pick_depth(e):
            """Up to two parts of the neck together. All three, none, or All itself means All."""
            clicked = set(e.control.selected)
            picked = set(clicked)
            parts = [name for name in chart_common.DEPTHS if name != "All"]
            if "All" in picked and "All" not in s.depth:
                picked = {"All"}
            picked.discard("All")
            if not picked or picked == set(parts):
                picked = {"All"}
            s.depth = tuple(name for name in chart_common.DEPTHS if name in picked)
            if picked != clicked:
                # The button keeps its own selection when changed from its event, so a new one replaces it
                depth_field.controls[1] = depth_button()
                depth_field.update()

        def depth_button():
            return ft.SegmentedButton(
                segments=segments(chart_common.DEPTHS, DEPTH_LABELS.values()),
                selected=list(s.depth),
                allow_multiple_selection=True,
                allow_empty_selection=True,
                show_selected_icon=False,
                on_change=pick_depth,
            )

        depth_field = field("How deep on the fretboard", depth_button())
        inversion_field = field("Inversions", ft.SegmentedButton(
            segments=segments(range(4), INVERSION_LABELS),
            selected=[str(n) for n in sorted(s.inversions)],
            allow_multiple_selection=True,
            on_change=lambda e: setattr(s, "inversions", {int(v) for v in e.control.selected}),
        ))

        # A tuning switch for instruments with more than one common tuning
        tuning_field = field("Tuning", ft.Container())

        def pick_tuning(e):
            s.tunings[s.instrument] = e.control.selected[0]

        def show_instrument_options():
            depth_field.visible = s.drawer in FRETBOARD_DRAWERS
            inversion_field.visible = s.drawer is piano_drawer
            tunings = s.tunings_of()
            tuning_field.visible = bool(tunings)
            if tunings:
                tuning_field.controls[1] = ft.SegmentedButton(
                    segments=[ft.Segment(value=t.name, label=ft.Text(fretted_drawer.tuning_label(t), style=SYMBOLS))
                              for t in tunings],
                    selected=[s.tuning],
                    show_selected_icon=False,
                    on_change=pick_tuning,
                )

        def pick_instrument(e):
            s.instrument = e.control.value
            show_instrument_options()
            self.page.update()

        show_instrument_options()

        interval_text = ft.Text(f"{s.interval} s", size=15, weight=ft.FontWeight.W_600, width=44,
                                text_align=ft.TextAlign.RIGHT)

        def set_interval(e):
            s.interval = int(e.control.value)
            interval_text.value = f"{s.interval} s"
            interval_text.update()

        interval = ft.Row(
            [ft.Slider(value=s.interval, min=MIN_INTERVAL, max=MAX_INTERVAL,
                       divisions=MAX_INTERVAL - MIN_INTERVAL, on_change=set_interval, expand=True,
                       padding=0),
             interval_text],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        def set_help(e):
            s.show_help = e.control.value

        help_row = ft.Container(
            content=ft.Row(
                [ft.Column([ft.Text("Show chart", size=16, weight=ft.FontWeight.W_600),
                            ft.Text("Draw each chord on the instrument", size=13,
                                    color=ft.Colors.ON_SURFACE_VARIANT)],
                           spacing=2, expand=True),
                 ft.Switch(value=s.show_help, on_change=set_help)],
            ),
            margin=ft.Margin.only(top=26),
        )

        practice = card(
            "Practice",
            field("Instrument", ft.Dropdown(
                options=[ft.DropdownOption(key=name, text=name) for name in DRAWERS],
                value=s.instrument,
                on_select=pick_instrument,
                width=240,
                menu_height=360,
                border_radius=14,
            ), top=18),
            tuning_field,
            depth_field,
            inversion_field,
            field("Change chord every", interval),
            help_row,
            expand=3,
        )

        def kind_chip(kind):
            def toggle(e):
                (s.kinds.add if e.control.selected else s.kinds.discard)(kind)
                refresh_start()
                self.page.update()

            example = chart_common.chord_title("c" + CHORD_KINDS[kind])
            return ft.Chip(
                label=ft.Row([ft.Text(kind, size=15, weight=ft.FontWeight.W_500, expand=True),
                              ft.Text(example, size=15, color=ft.Colors.ON_SURFACE_VARIANT, style=SYMBOLS)],
                             expand=True),
                selected=kind in s.kinds,
                show_checkmark=False,
                on_select=toggle,
                shape=ft.RoundedRectangleBorder(radius=14),
                padding=ft.Padding.symmetric(horizontal=8, vertical=10),
            )

        chords = card(
            "Chords",
            ft.Text("Pick at least one", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Column([kind_chip(kind) for kind in CHORD_KINDS], spacing=10, margin=ft.Margin.only(top=18),
                      horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            expand=2,
        )

        refresh_start()

        header = ft.Row(
            [ft.Column([ft.Text("Chord Switcher", size=36, weight=ft.FontWeight.W_800),
                        ft.Text("Practise recognising and playing chords.", size=16,
                                color=ft.Colors.ON_SURFACE_VARIANT)],
                       spacing=2, expand=True),
             ft.IconButton(icon=ft.Icons.CONTRAST_ROUNDED, tooltip="Light or dark",
                           on_click=self.toggle_theme)],
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        return ft.Container(
            content=ft.Column(
                [header,
                 ft.Row([practice, chords], spacing=20, expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH),
                 ft.Row([hint, start_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)],
                spacing=24,
            ),
            padding=ft.Padding.symmetric(horizontal=40, vertical=32),
            expand=True,
            data="menu",
        )

    # The practice view

    def practice_view(self):
        s = self.settings
        view = Practice()
        view.title = ft.AnimatedSwitcher(
            content=ft.Text(""),
            transition=ft.AnimatedSwitcherTransition.SCALE,
            duration=260,
            reverse_duration=100,
            switch_in_curve=ft.AnimationCurve.EASE_OUT_BACK,
        )
        view.subtitle = ft.Text("", size=24, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT)
        view.chart = ft.Image(src=b"", fit=ft.BoxFit.CONTAIN, gapless_playback=True, visible=False)
        view.progress = ft.ProgressBar(value=0, bar_height=8, border_radius=8,
                                       bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST)
        view.title_size = 64 if s.show_help else 180

        top_bar = ft.Row(
            [ft.IconButton(icon=ft.Icons.ARROW_BACK_ROUNDED, tooltip="Back (Esc)",
                           on_click=lambda _: self.open_menu()),
             ft.Container(
                 content=ft.Text(s.caption(), size=14, weight=ft.FontWeight.W_600),
                 padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                 border_radius=999,
                 bgcolor=ft.Colors.SECONDARY_CONTAINER,
             )],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        middle = [view.title, view.subtitle]
        if s.show_help:
            # The panel hugs the chart, which shrinks to fit the space it gets
            middle.append(ft.Container(
                content=ft.Container(
                    content=view.chart,
                    bgcolor=CHART_BG,
                    border_radius=24,
                    padding=CHART_PADDING,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    shadow=ft.BoxShadow(blur_radius=30, spread_radius=-6, offset=ft.Offset(0, 10),
                                        color=ft.Colors.with_opacity(0.18, ft.Colors.SHADOW)),
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
                margin=ft.Margin.only(top=12),
            ))

        return ft.Container(
            content=ft.Column(
                [top_bar,
                 ft.Column(middle, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                           alignment=ft.MainAxisAlignment.CENTER, spacing=4, expand=True),
                 view.progress],
                spacing=20,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=ft.Padding.symmetric(horizontal=PRACTICE_PADDING, vertical=28),
            expand=True,
            data=view,
        )

    def pick_chord(self):
        """A random chord from the picked kinds, not the one shown last."""
        names = [name for name in self.settings.chords() if name != self.last_chord] or self.settings.chords()
        self.last_chord = random.choice(names)
        return self.last_chord

    def chart_space(self):
        """The width and height the chart has in the practice view, from the window's size."""
        width = self.page.width or WINDOW_SIZE[0]
        height = self.page.height or WINDOW_SIZE[1]
        return (max(200, width - 2 * PRACTICE_PADDING - 2 * CHART_PADDING),
                max(150, height - PRACTICE_CHROME - 2 * CHART_PADDING))

    async def next_chord(self):
        """Pick and draw the next chord, off the main thread as drawing takes a moment."""
        return await asyncio.to_thread(Chord, self.pick_chord(), self.settings, self.chart_space())

    def on_resize(self, _):
        if isinstance(self.root.content.data, Practice) and self.shown and self.shown.columns:
            self.resizes += 1
            self.page.run_task(self.relayout, self.resizes, self.session)

    async def relayout(self, resize, session):
        """Draw the chart again in the columns that suit the resized window, once resizing stops."""
        await asyncio.sleep(RELAYOUT_DELAY)
        shown = self.shown
        if resize != self.resizes or session != self.session or not shown:
            return
        space = self.chart_space()
        if fretted_drawer.best_columns(self.settings.drawer.card_count(
                shown.name, **self.chart_options()), *space) == shown.columns:
            return
        chord = await asyncio.to_thread(Chord, shown.name, self.settings, space, shown.inversion)
        if session == self.session and self.shown is shown:
            self.shown = chord
            self.root.content.data.chart.src = chord.chart
            self.page.update()

    def chart_options(self):
        """The options a fretboard drawer takes for the current settings, without columns."""
        options = {"depth": self.settings.depth}
        if self.settings.drawer is fretted_drawer:
            options.update(instrument=self.settings.instrument, tuning=self.settings.tuning)
        return options

    def show_chord(self, view, chord):
        self.shown = chord
        view.title.content = ft.Text(chord.title, size=view.title_size, weight=ft.FontWeight.W_800, style=SYMBOLS,
                                     key=f"{chord.name}-{time.monotonic()}")
        # The chart names the inversion itself
        view.subtitle.value = "" if chord.chart else chord.inversion_name
        view.subtitle.visible = bool(view.subtitle.value)
        if chord.chart:
            view.chart.src = chord.chart
            view.chart.visible = True

    async def practice(self, session):
        """Show a new chord every interval until the session ends."""
        view = self.root.content.data
        upcoming = asyncio.ensure_future(self.next_chord())
        while session == self.session:
            chord = await upcoming
            if session != self.session:
                return
            self.show_chord(view, chord)
            upcoming = asyncio.ensure_future(self.next_chord())
            started = time.monotonic()
            while session == self.session:
                elapsed = time.monotonic() - started
                view.progress.value = min(1, elapsed / self.settings.interval)
                self.page.update()
                if elapsed >= self.settings.interval:
                    break
                await asyncio.sleep(TICK)
        upcoming.cancel()


class Practice:
    """The controls of the practice view that change while practising."""
    title: ft.AnimatedSwitcher
    subtitle: ft.Text
    chart: ft.Image
    progress: ft.ProgressBar
    title_size: int


def main(page: ft.Page):
    App(page)


if __name__ == "__main__":
    ft.run(main, assets_dir=str(ASSETS))
