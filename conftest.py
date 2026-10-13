"""Pytest bootstrap: make the repo root importable so `import pawpal_system` works everywhere."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
