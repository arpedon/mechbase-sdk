"""Dump mechbase-v2's Ninja OpenAPI schema to stdout.

Run from a mechbase-v2 checkout (or worktree) where the venv has Django
installed:

    cd /path/to/mechbase-v2
    uv run python /path/to/mechbase-sdk/scripts/dump-openapi.py > /path/to/mechbase-sdk/openapi.json
"""

from __future__ import annotations

import json
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from api.urls import api  # noqa: E402

print(json.dumps(api.get_openapi_schema(), indent=2, default=str))
