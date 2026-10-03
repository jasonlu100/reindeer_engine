"""Launcher for the Reindeer editor.

Run::

    python run_editor.py
    python run_editor.py path/to/project

See ``editor/app.py`` for details.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from editor.app import main

if __name__ == "__main__":
    main()
