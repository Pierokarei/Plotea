"""Issues reported from real use."""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox,
    QPushButton,
    QToolBar,
    QToolButton,
)

app = QApplication.instance()


def click_type(win, plot_type: str):
    """Press the plot-type card the way a person would."""
    for button in win.inspector.type_buttons.buttons():
        if button.property("plot_type") == plot_type:
            button.setChecked(True)
            button.click()
            return button
    raise AssertionError(plot_type)


# --------------------------------------------------------------------------
# Switching between curve and scatter
# --------------------------------------------------------------------------
def test_curve_comes_back_after_scatter(shared_window):
    """Courbe -> Nuage -> Courbe must draw a line again.

    Scatter turns the line off; if nothing turns it back on, the curve keeps
    drawing markers with no line and still looks like a scatter.
    """
    win = shared_window
    win.load_example("Courbe de croissance (courbes + SD)")
    click_type(win, "line")
    win._render_now()
    assert win.current_spec().show_line is True

    click_type(win, "scatter")
    win._render_now()
    assert win.current_spec().show_line is False

    click_type(win, "line")
    win._render_now()
    spec = win.current_spec()
    assert spec.plot_type == "line"
    assert spec.show_line is True, "la courbe doit retrouver son trait"

    drawn = [line for line in win.canvas.figure.axes[0].lines
             if line.get_linestyle() not in ("None", "none", " ", "")]
    assert drawn, "aucun trait trace : le graphique est reste un nuage"


@pytest.mark.parametrize("detour", ["bar", "box", "violin", "histogram"])
def test_curve_survives_a_detour(shared_window, detour):
    """Even after visiting another type in between."""
    win = shared_window
    win.load_example("Courbe de croissance (courbes + SD)")
    click_type(win, "line")
    click_type(win, "scatter")
    click_type(win, detour)
    click_type(win, "line")
    win._render_now()

    spec = win.current_spec()
    assert spec.plot_type == "line", spec.plot_type
    assert spec.show_line is True
    drawn = [line for line in win.canvas.figure.axes[0].lines
             if line.get_linestyle() not in ("None", "none", " ", "")]
    assert drawn, f"retour a la courbe casse apres un passage par {detour}"


def test_every_type_round_trip(shared_window):
    """Any type, then any other, then back: the first one still applies."""
    win = shared_window
    win.load_example("Viabilité cellulaire (barres, stats)")
    types = ["line", "scatter", "histogram", "box", "violin", "bar"]
    for first in types:
        for second in types:
            if first == second:
                continue
            click_type(win, first)
            click_type(win, second)
            click_type(win, first)
            win._render_now()
            spec = win.current_spec()
            assert spec.plot_type == first, (first, second, spec.plot_type)
            if first == "line":
                assert spec.show_line, (first, second)
            if first == "scatter":
                assert not spec.show_line, (first, second)


# --------------------------------------------------------------------------
# Reaching the export buttons
# --------------------------------------------------------------------------
def test_export_actions_are_on_the_toolbar(shared_window):
    """Beside the graph actions, with a label, not behind the chevron."""
    win = shared_window
    toolbar = win.findChild(QToolBar, "main_toolbar")
    actions = list(toolbar.actions())
    assert win.a_copy_png in actions
    assert win.a_export in actions

    for action in (win.a_copy_png, win.a_export):
        button = toolbar.widgetForAction(action)
        assert button is not None
        assert button.toolButtonStyle() != Qt.ToolButtonStyle.ToolButtonIconOnly
        assert action.iconText().strip(), action.text()
        assert not action.icon().isNull()

    # they sit in the same group as the graph actions
    names = [a.iconText() for a in actions if a.iconText()]
    assert names.index("Copier") == names.index("Dupliquer") + 1, names


def test_toolbar_fits_the_default_window(shared_window):
    """At the size the application opens at, nothing hides behind the chevron.

    Qt collapses what does not fit into an extension button with no label,
    which is exactly how the export action became unreachable.
    """
    win = shared_window
    toolbar = win.findChild(QToolBar, "main_toolbar")
    assert toolbar is not None
    needed = toolbar.sizeHint().width()
    assert needed <= 1520, f"barre d'outils trop large : {needed} px"


def test_export_lives_in_one_place(shared_window):
    """On the toolbar, and nowhere else: no duplicate under the figure."""
    win = shared_window
    assert not hasattr(win.canvas, "btn_export")
    assert win.a_export.shortcut().toString() == "Ctrl+E"
    assert win.a_copy_png.shortcut().toString() == "Ctrl+Shift+C"


# --------------------------------------------------------------------------
# One language throughout
# --------------------------------------------------------------------------
def test_qt_standard_buttons_are_french(qapp):
    """Qt's own dialogs must not answer in English."""
    box = QMessageBox()
    box.setStandardButtons(QMessageBox.StandardButton.Save
                           | QMessageBox.StandardButton.Cancel
                           | QMessageBox.StandardButton.Close)
    texts = {b.text().replace("&", "") for b in box.buttons()}
    assert "Enregistrer" in texts, texts
    assert "Annuler" in texts, texts
    assert "Fermer" in texts, texts
    assert not texts & {"Save", "Cancel", "Close", "Discard"}, texts


def test_interface_is_accented(shared_window):
    """The French interface carries its accents, menus and data alike."""
    from plotea.core import demo, enums

    win = shared_window
    menus = {action.text().replace("&", "")
             for action in win.menuBar().actions()}
    assert {"Données", "Édition"} <= menus, menus
    assert win.dock_data.windowTitle() == "Données"

    # the option labels people read, not the keys stored in the file
    assert "t apparié" in enums.STATS_TEST.labels()
    assert "Étoiles" in enums.STATS_FORMAT.labels()
    assert "Aligné" in enums.POINT_STYLE.labels()

    # and the demo tables, which end up on the axes of a figure
    table = demo.viability()
    assert "Viabilité" in table.df.columns, list(table.df.columns)
    assert "Contrôle" in set(table.df["Traitement"])


def test_no_english_left_in_the_menus(shared_window):
    """A sweep for the words that betray an untranslated widget."""
    win = shared_window
    english = {"Save", "Open", "Close", "Discard", "Cancel", "Export",
               "Import", "Undo", "Redo", "Help", "File", "Edit"}
    seen = set()
    for menu in win.menuBar().actions():
        submenu = menu.menu()
        seen.add(menu.text().replace("&", ""))
        if submenu is not None:
            seen.update(a.text().replace("&", "") for a in submenu.actions())
    leftovers = {word for word in seen if word in english}
    assert not leftovers, leftovers


# --------------------------------------------------------------------------
# Inline stylesheets
# --------------------------------------------------------------------------
def test_colour_swatch_stylesheet_is_valid(qapp):
    """A swatch with a broken sheet loses its colour entirely.

    Only the first fragment used to be an f-string, so its doubled brace came
    out literal and Qt rejected the whole rule.
    """
    from plotea.ui.widgets import ColorButton

    button = ColorButton("#E64B35")
    sheet = button.styleSheet()
    assert sheet.count("{") == sheet.count("}"), sheet
    assert "}}" not in sheet, sheet
    assert "#E64B35" in sheet

    button.setColor("#00A087")
    assert "#00A087" in button.styleSheet()


def test_every_inline_stylesheet_is_balanced(shared_window):
    """Sweep the live window: an unbalanced sheet is silently dropped by Qt."""
    from PyQt6.QtWidgets import QWidget

    unbalanced = []
    for widget in shared_window.findChildren(QWidget):
        sheet = widget.styleSheet()
        if sheet and sheet.count("{") != sheet.count("}"):
            unbalanced.append((type(widget).__name__, sheet[:80]))
    assert not unbalanced, unbalanced


# --------------------------------------------------------------------------
# The panels must hold their width
# --------------------------------------------------------------------------
def test_figure_size_does_not_move_the_panels(shared_window):
    """Changing the figure size must not squeeze the side panels.

    The preview is sized in millimetres and can get large; if it asks the
    window for that much room, the docks give theirs up and their labels get
    cut off.
    """
    win = shared_window
    win.resize(1400, 900)
    app.processEvents()
    spec = win.current_spec()
    spec.span = "single"
    win._render_now()
    app.processEvents()
    before = (win.dock_inspector.width(), win.dock_data.width(),
              win.dock_stats.height())

    for span, width, height in (("double", 183.0, 120.0),
                                ("custom", 450.0, 320.0),
                                ("single", 89.0, 69.0)):
        spec.span = span
        spec.width_mm, spec.height_mm = width, height
        win._render_now()
        app.processEvents()
        after = (win.dock_inspector.width(), win.dock_data.width(),
                 win.dock_stats.height())
        assert after == before, f"{span} a decale les panneaux : {before} -> {after}"


def test_canvas_shows_the_figure_size(shared_window):
    """The millimetre readout must stay visible beside the zoom controls."""
    win = shared_window
    win.resize(1400, 900)
    app.processEvents()
    win._render_now()
    app.processEvents()
    label = win.canvas.size_label
    assert "mm" in label.text(), label.text()
    assert label.width() > 40, label.width()


def test_analyses_buttons_keep_their_label(shared_window):
    """"Exporter CSV" must stay readable when the panel is narrow."""
    win = shared_window
    panel = win.stats_panel
    buttons = [b for b in panel.findChildren(QPushButton)
               if b.text() in ("Copier", "Exporter CSV")]
    assert len(buttons) == 2, [b.text() for b in buttons]

    for width in (1400, 900, 600):
        win.resize(width, 900)
        app.processEvents()
        for button in buttons:
            assert button.width() >= button.sizeHint().width(), (
                f"{button.text()} tronque a {width} px : "
                f"{button.width()} < {button.sizeHint().width()}")


def test_plot_type_cards_are_identical(shared_window):
    """Six tiles, one size."""
    win = shared_window
    app.processEvents()
    buttons = win.inspector.type_buttons.buttons()
    assert len(buttons) == 6
    heights = {b.height() for b in buttons}
    assert len(heights) == 1, heights
    widths = [b.width() for b in buttons]
    # an odd panel width splits into two columns that differ by one pixel;
    # anything beyond that means the label is driving the size again
    assert max(widths) - min(widths) <= 1, widths
    # the shortened label keeps the full wording within reach
    for button in buttons:
        assert button.toolTip(), button.text()


def test_dock_buttons_are_styled_for_both_themes(shared_window):
    """The float and close glyphs must exist and follow the theme."""
    from plotea.core.project import config_dir
    from plotea.resources import write_dock_icons
    from plotea.ui.style import build_qss, palette_colors

    for dark in (False, True):
        colours = palette_colors(dark)
        icons = write_dock_icons(config_dir(), colours["text_dim"])
        assert {"float", "close"} <= set(icons), icons
        sheet = build_qss(dark, icons)
        assert "QDockWidget::float-button" in sheet
        assert "QDockWidget::close-button" in sheet
        assert icons["float"] in sheet and icons["close"] in sheet
        assert "icon-size" in sheet

    # light and dark must not share the same file
    light = write_dock_icons(config_dir(), palette_colors(False)["text_dim"])
    dark = write_dock_icons(config_dir(), palette_colors(True)["text_dim"])
    assert light["close"] != dark["close"]


# --------------------------------------------------------------------------
# A toolbar that reads the same from end to end
# --------------------------------------------------------------------------
def test_every_toolbar_button_shows_its_label(shared_window):
    """No naked glyph next to labelled buttons: same row, same treatment."""
    win = shared_window
    toolbar = win.findChild(QToolBar, "main_toolbar")
    for action in toolbar.actions():
        if action.isSeparator():
            continue
        button = toolbar.widgetForAction(action)
        if button is None or not hasattr(button, "toolButtonStyle"):
            continue
        assert action.iconText().strip(), action.text()
        assert button.toolButtonStyle() == (
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon), action.iconText()

    labels = [a.iconText() for a in toolbar.actions() if a.iconText()]
    assert "Ouvrir" in labels and "Enregistrer" in labels, labels


def test_the_theme_picker_left_the_toolbar(shared_window):
    """It sits on the tab row now; the toolbar had no room for it."""
    win = shared_window
    toolbar = win.findChild(QToolBar, "main_toolbar")
    combo = win.cmb_theme_quick
    assert combo.parent() is not toolbar
    assert toolbar.widgetForAction(toolbar.actions()[-1]) is not combo
    # it still drives the theme of the current graph
    combo.setCurrentText("Science")
    assert win.current_spec().theme == "Science"


def test_composite_and_blank_table_have_different_icons(shared_window):
    """Two neighbouring buttons drawn with the same glyph are unreadable."""
    from PyQt6.QtCore import QSize

    from plotea.ui.widgets import make_icon

    win = shared_window
    assert win.a_new_panel.property("icon_name") == "composite"

    table_button = [b for b in win.data_panel.findChildren(QToolButton)
                    if b.property("icon_name") == "table"]
    assert table_button, "la table vierge a perdu son icone"

    size = QSize(17, 17)
    composite = make_icon("composite", "#1C2430", 17).pixmap(size)
    table = make_icon("table", "#1C2430", 17).pixmap(size)
    assert composite.toImage() != table.toImage(), "memes pixels"


def test_dock_buttons_are_big_enough_to_aim_at(shared_window):
    """As large as the other controls, not a few grey pixels."""
    import re

    from plotea.ui.style import build_qss

    sheet = build_qss(False, {"float": "a.png", "close": "b.png"})
    block = sheet.split("QDockWidget::float-button, "
                        "QDockWidget::close-button")[1].split("}")[0]
    icon = int(re.search(r"icon-size:\s*(\d+)px", block).group(1))
    width = int(re.search(r"width:\s*(\d+)px", block).group(1))
    height = int(re.search(r"height:\s*(\d+)px", block).group(1))
    assert icon >= 17, icon
    assert width >= 24 and height >= 24, (width, height)
    # and the title keeps its text clear of them
    title = sheet.split("QDockWidget::title")[1].split("}")[0]
    right = int(re.search(r"padding:\s*\d+px\s+(\d+)px", title).group(1))
    assert right >= 2 * width, (right, width)


def test_the_dropdown_marker_is_drawn(shared_window):
    """A style sheet cannot make a triangle out of transparent borders.

    Qt draws every border of the CSS trick, so each combo box showed a grey
    block where its chevron belongs.
    """
    from plotea.core.project import config_dir
    from plotea.resources import write_dock_icons
    from plotea.ui.style import build_qss, palette_colors

    icons = write_dock_icons(config_dir(), palette_colors(False)["text_dim"])
    assert icons.get("chevron"), icons

    sheet = build_qss(False, icons)
    arrow = sheet.rsplit("QComboBox::down-arrow {", 1)[1].split("}")[0]
    assert f"image: url({icons['chevron']})" in arrow, arrow
    assert "border: none" in arrow, arrow


# --------------------------------------------------------------------------
# One glyph, one meaning
# --------------------------------------------------------------------------
def icon_image(name: str):
    from PyQt6.QtCore import QSize

    from plotea.ui.widgets import make_icon

    return make_icon(name, "#1C2430", 17).pixmap(QSize(17, 17)).toImage()


def test_duplicate_and_copy_have_different_icons(shared_window):
    """Side by side on the toolbar, two copies of the same glyph read as one."""
    win = shared_window
    assert win.a_dup_plot.property("icon_name") == "duplicate"
    assert win.a_copy_png.property("icon_name") == "copy"
    assert icon_image("duplicate") != icon_image("copy")


def test_no_two_toolbar_buttons_share_a_glyph(shared_window):
    """The general rule, so the next added action cannot repeat one."""
    win = shared_window
    toolbar = win.findChild(QToolBar, "main_toolbar")
    seen = {}
    for action in toolbar.actions():
        name = action.property("icon_name")
        if not name:
            continue
        image = icon_image(name)
        for other, other_image in seen.items():
            assert image != other_image, (name, other)
        seen[name] = image
    assert len(seen) >= 8, seen


# --------------------------------------------------------------------------
# Dock buttons that say what they do
# --------------------------------------------------------------------------
def test_dock_buttons_carry_a_tooltip(shared_window):
    """Hovering must explain the button, like everywhere else in the window."""
    from PyQt6.QtWidgets import QAbstractButton

    win = shared_window
    for dock in (win.dock_data, win.dock_inspector, win.dock_stats):
        tips = {b.objectName(): b.toolTip()
                for b in dock.findChildren(QAbstractButton)
                if b.objectName().startswith("qt_dockwidget")}
        assert set(tips) == {"qt_dockwidget_floatbutton",
                             "qt_dockwidget_closebutton"}, tips
        assert "Détacher" in tips["qt_dockwidget_floatbutton"]
        close = tips["qt_dockwidget_closebutton"]
        assert "Fermer" in close
        # closing only hides the panel: say where it comes back from
        assert "Affichage" in close, close
        for tip in tips.values():
            assert dock.windowTitle() in tip, (tip, dock.windowTitle())


def test_the_close_cross_turns_red(shared_window):
    """The colour every browser uses for "this closes something"."""
    from plotea.core.project import config_dir
    from plotea.resources import write_dock_icons
    from plotea.ui.style import build_qss, palette_colors

    for dark in (False, True):
        colours = palette_colors(dark)
        icons = write_dock_icons(config_dir(), colours["text"],
                                 {"close": colours["danger"],
                                  "float": colours["accent"]})
        assert icons["close_hover"] != icons["close"]
        assert colours["danger"].lstrip("#") in icons["close_hover"]

        sheet = build_qss(dark, icons)
        hover = [block for block in sheet.split("QDockWidget::close-button")
                 if block.startswith(":hover")]
        assert hover, "aucune regle de survol pour la croix"
        joined = "".join(hover)
        assert colours["danger"] in joined, joined[:200]
        assert icons["close_hover"] in joined
        # and the detach arrow keeps the neutral accent, not the red
        float_hover = [block for block
                       in sheet.split("QDockWidget::float-button")
                       if block.startswith(":hover")]
        assert colours["accent"] in "".join(float_hover)


def test_old_glyph_files_are_purged(tmp_path, qapp):
    """A new drawing leaves its predecessors behind; clean them up.

    Only the generated names, and only the versions that are no longer in
    use: everything else in the configuration folder is somebody's data.
    """
    import os

    from plotea.resources import GLYPH_VERSION, write_dock_icons

    folder = str(tmp_path)
    stale = ["dock-close-1C2430.png",          # the first, unversioned naming
             "dock-float-98A1AE.png",
             f"dock-chevron-v{GLYPH_VERSION - 1}-6B7684.png"]
    keep = ["presets.json", "journal.log", "dock-notes.txt",
            "mes-donnees-dock-close-v1-1C2430.png"]
    for name in stale + keep:
        (tmp_path / name).write_text("x", encoding="utf-8")

    icons = write_dock_icons(folder, "#1C2430", {"close": "#D9484A"})
    left = set(os.listdir(folder))

    for name in stale:
        assert name not in left, name
    for name in keep:
        assert name in left, name
    for path in icons.values():
        assert os.path.exists(path), path
        assert f"-v{GLYPH_VERSION}-" in path, path


def test_purging_survives_a_locked_file(tmp_path, qapp, monkeypatch):
    """A file another instance holds open must not take startup down."""
    import os

    from plotea import resources

    (tmp_path / "dock-close-1C2430.png").write_text("x", encoding="utf-8")

    def refuse(path):
        raise PermissionError(path)

    monkeypatch.setattr(os, "remove", refuse)
    icons = resources.write_dock_icons(str(tmp_path), "#1C2430")
    assert icons, "les glyphes doivent etre produits malgre l'echec du menage"


# --------------------------------------------------------------------------
# Tooltips that keep up with the pointer
# --------------------------------------------------------------------------
def test_tooltip_effects_are_off(qapp):
    """The fade outlives the pointer and shows up as a flickering bubble."""
    from plotea.app import steady_tooltips

    steady_tooltips(qapp)
    assert qapp.isEffectEnabled(Qt.UIEffect.UI_FadeTooltip) is False
    assert qapp.isEffectEnabled(Qt.UIEffect.UI_AnimateTooltip) is False


def test_tooltip_style_has_a_border(qapp):
    """Qt needs one to repaint a styled tooltip in full."""
    import re

    from plotea.ui.style import build_qss

    for dark in (False, True):
        sheet = build_qss(dark)
        block = sheet.split("QToolTip {")[1].split("}")[0]
        border = re.search(r"border:\s*([^;]+);", block)
        assert border, block
        assert border.group(1).strip() != "none", block


def test_header_tooltip_is_bound_to_its_section(shared_window, monkeypatch):
    """Each column tooltip must carry the rectangle it belongs to.

    Qt asks the model for the text and shows it with no area attached, which
    is why the bubble kept the previous column's text while the pointer was
    already over the next one. Handing showText the section rectangle is the
    whole fix, so that is what this checks - the text alone would pass even
    with the filter removed.
    """
    from PyQt6.QtCore import QEvent, QPoint, QRect
    from PyQt6.QtGui import QHelpEvent

    from plotea.ui import widgets

    win = shared_window
    win.load_example("Viabilité cellulaire (barres, stats)")
    app.processEvents()
    header = win.data_panel.table.horizontalHeader()
    assert header.count() >= 3
    assert isinstance(win.data_panel._header_tips, widgets._SectionTips), (
        "le filtre doit rester reference, sinon PyQt le collecte")

    shown = []
    monkeypatch.setattr(widgets.QToolTip, "showText",
                        staticmethod(lambda *a: shown.append(a)))

    for index in range(3):
        x = (header.sectionViewportPosition(index)
             + header.sectionSize(index) // 2)
        point = QPoint(x, header.height() // 2)
        app.sendEvent(header.viewport(),
                      QHelpEvent(QEvent.Type.ToolTip, point,
                                 header.viewport().mapToGlobal(point)))

    assert len(shown) == 3, shown
    texts = [call[1] for call in shown]
    assert len(set(texts)) == 3, texts
    for index, call in enumerate(shown):
        assert str(win.data_panel.model._df.columns[index]) in call[1]
        rect = call[3]
        assert isinstance(rect, QRect) and rect.isValid(), call
        assert rect.width() == header.sectionSize(index), (rect, index)
        assert rect.x() == header.sectionViewportPosition(index), (rect, index)


def test_a_section_without_a_tooltip_clears_the_bubble(shared_window,
                                                       monkeypatch):
    """Past the last column there is nothing to say, so say nothing."""
    from PyQt6.QtCore import QEvent, QPoint
    from PyQt6.QtGui import QHelpEvent

    from plotea.ui import widgets

    calls = []
    monkeypatch.setattr(widgets.QToolTip, "hideText",
                        lambda: calls.append("hide"))
    monkeypatch.setattr(widgets.QToolTip, "showText",
                        lambda *a, **k: calls.append("show"))

    win = shared_window
    header = win.data_panel.table.horizontalHeader()
    point = QPoint(header.width() + 80, header.height() // 2)
    event = QHelpEvent(QEvent.Type.ToolTip, point,
                       header.viewport().mapToGlobal(point))
    app.sendEvent(header.viewport(), event)

    # the event is refused, so Qt hands it to the header as well and the
    # filter answers once per widget: what matters is that nothing is shown
    assert calls and set(calls) == {"hide"}, calls
    assert not event.isAccepted(), "l'evenement doit etre rendu a Qt"


def test_dock_tooltips_survive_a_detach(shared_window):
    """Floating a panel rebuilds its title bar; the tooltips must come back."""
    from PyQt6.QtWidgets import QAbstractButton

    win = shared_window
    dock = win.dock_stats
    try:
        dock.setFloating(True)
        app.processEvents()
        tips = [b.toolTip() for b in dock.findChildren(QAbstractButton)
                if b.objectName().startswith("qt_dockwidget")]
        assert len(tips) == 2, tips
        assert all(tips), tips
    finally:
        dock.setFloating(False)
        app.processEvents()


def test_selftest_reports_the_silent_invariants(shared_window, qapp):
    """The packaged build can only be asked what it prints."""
    from plotea.app import selftest_report, steady_tooltips

    steady_tooltips(qapp)
    lines = "\n".join(selftest_report(qapp, shared_window))
    assert "fondu=off" in lines and "animation=off" in lines, lines
    assert "filtre d'en-tête : actif" in lines, lines
    assert "PERDU" not in lines, lines
    assert "glyphes de panneau : 5 fichiers" in lines, lines
