"""Entry point for a Hugging Face Space: serves the explorer (web/app.py) on 0.0.0.0:7860.

Locally, run the explorer directly instead: cd web && ../.venv/bin/python app.py
"""
import os
import sys
from pathlib import Path

web = Path(__file__).resolve().parent / "web" / "app.py"
os.execv(sys.executable, [sys.executable, str(web), "--host", "0.0.0.0", "--port", os.environ.get("PORT", "7860")])
