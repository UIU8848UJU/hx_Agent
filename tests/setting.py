# hx_agent/app_context/settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

KB_DB = os.getenv(
    "HX_KB_DB",
    str(BASE_DIR / "kb.sqlite")
)