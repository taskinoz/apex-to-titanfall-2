"""Machine-specific locations, so no script hard-codes a user's folders.

Each name is read from the environment, then from the untracked `local_paths.json`
next to this file (copy `local_paths.example.json`). An unset name gives a
placeholder path that names the setting, so a script that needs it fails with
that name in the error instead of a guessed folder.

  APEX_WORK_ROOT   conversion work area: apex-current/, rsx-latest/, poi-survey/, br-visibility/, new-arena-ports/
  APEX_GAME        Apex Legends install (paks/Win64)
  TITANFALL2_GAME  Titanfall 2 install with Northstar
  R5R_LIBRARY      R5Reloaded library folder (R5R Library)
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILE = ROOT / 'local_paths.json'


def path(name):
    value = os.environ.get(name)
    if not value and FILE.exists():
        value = json.loads(FILE.read_text(encoding='utf-8')).get(name)
    return Path(value) if value else Path(f'<set {name} in the environment or local_paths.json>')


def rsx():
    return path('APEX_WORK_ROOT') / 'rsx-latest/bin/Release_NoGui/rsx.exe'


def apex_paks():
    return path('APEX_GAME') / 'paks/Win64'
