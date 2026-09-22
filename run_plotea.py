"""Entry point for the standalone build and for `python run_plotea.py`.

Uses an absolute import on purpose: PyInstaller runs this file as a top-level
script, where the relative imports of `plotea/__main__.py` have no package to
resolve against.
"""
import sys

from plotea.app import main

if __name__ == "__main__":
    sys.exit(main())
