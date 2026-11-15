"""Vercel Python function: every /api/* request is rewritten here (see vercel.json)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from posting_validation.wsgi import app  # noqa: E402,F401  (Vercel looks for `app`)
