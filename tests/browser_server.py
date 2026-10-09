"""Isolated browser test server. This model double is never used by app.main."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from app.main import create_app
from tests.test_api import TestVision

directory = TemporaryDirectory(prefix="canopy-browser-")
os.environ["JEV_API_KEY"] = ""
os.environ["GEMMA_ENDPOINT"] = ""
app = create_app(Path(directory.name), vision=TestVision())
