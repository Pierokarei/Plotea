"""Launch the real app, capture documentation screenshots, then quit."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from plotea.ui.main_window import MainWindow
from plotea.ui.style import build_qss

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(build_qss(False))
win = MainWindow()
win.apply_theme(False)
win.resize(1560, 950)
win.show()

shots = []


def shot(name):
    for _ in range(3):
        app.processEvents()
    win.canvas.canvas.repaint()
    win.grab().save(os.path.join(DOCS, name))
    shots.append(name)


def scenario():
    spec = win.current_spec()
    spec.theme = "Nature"
    spec.title = "Effet des traitements"
    spec.ylabel = "Viabilité (%)"
    spec.xlabel = ""
    win._sync_inspector()
    win._render_now()
    shot("screenshot.png")

    win.load_example("Dose-réponse (fit 4PL)")
    spec = win.current_spec()
    spec.plot_type = "scatter"
    spec.x = "log[C] (M)"
    spec.y = ["Réponse (%)"]
    spec.group = "Composé"
    spec.fit_model = "Dose-reponse log"
    spec.theme = "PNAS"
    spec.xlabel = "log [inhibiteur] (M)"
    spec.ylabel = "Réponse (%)"
    spec.title = "Courbes dose-réponse"
    spec.fit_equation_loc = "Bas gauche"
    spec.legend_loc = "upper right"
    win._sync_inspector()
    win._render_now()
    shot("screenshot_fit.png")

    win.load_example("Expression génique (violin/histogramme)")
    spec = win.current_spec()
    spec.plot_type = "violin"
    spec.group = ""
    spec.y = ["Sain", "Tumeur", "Métastase"]
    spec.theme = "Cell"
    spec.show_points = False
    spec.stats_enabled = True
    spec.xlabel = ""
    spec.ylabel = "Expression (UA)"
    spec.title = "Expression par stade"
    spec.ymax = 60.0
    win._sync_inspector()
    win._render_now()
    win.apply_theme(True)
    shot("screenshot_dark.png")
    win.apply_theme(False)

    # a composite figure built from four plots made for the occasion
    recipes = [
        ("Viabilité cellulaire (barres, stats)", "bar",
         dict(group="Traitement", y=["Viabilité"], ylabel="Viabilité (%)",
              stats_enabled=True, title="")),
        ("Dose-réponse (fit 4PL)", "scatter",
         dict(x="log[C] (M)", y=["Réponse (%)"], group="Composé",
              fit_model="Dose-reponse log", xlabel="log [C] (M)",
              ylabel="Réponse (%)", legend_loc="upper right")),
        ("Expression génique (violin/histogramme)", "violin",
         dict(y=["Sain", "Tumeur", "Métastase"], group="", xlabel="",
              ylabel="Expression (UA)", show_points=False, ymax=60.0)),
        ("Courbe de croissance (courbes + SD)", "line",
         dict(x="Temps (h)", y=["WT", "KO", "KO + rescue"],
              error_cols=["WT SD", "KO SD", "KO + rescue SD"],
              error_band=True, xlabel="Temps (h)", ylabel="DO 600")),
    ]
    for index, (example, kind, options) in enumerate(recipes):
        if index:
            win.new_plot()
        win.load_example(example)
        spec = win.current_spec()
        spec.plot_type = kind
        spec.theme = "Nature"
        for key, value in options.items():
            setattr(spec, key, value)
        win._sync_inspector()
        win._render_now()

    win.new_panel()
    panel = win.current_panel()
    panel.plots = [s.name for s in win.project.plots[:4]]
    panel.cols = 2
    panel.span = "double"
    panel.height_mm = 115.0
    win.panel_editor.set_panel(panel, win.project.plot_names())
    win._render_now()
    shot("screenshot_panel.png")

    win.project.dirty = False
    print("captures:", ", ".join(shots))
    app.quit()


QTimer.singleShot(900, scenario)
sys.exit(app.exec())
