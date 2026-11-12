#!/usr/bin/env python3
"""Fail fast when a real provider is unavailable; never silently fake AI."""
import os
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'backend/.env'
values = {}
if path.is_file():
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"\'')
key = os.getenv('OPENAI_API_KEY') or values.get('OPENAI_API_KEY', '')
if not key or key.startswith(('sk-sua', 'sk-COLOQUE', 'your-', 'test-')):
    raise SystemExit('\nOpenAI key missing. Set OPENAI_API_KEY in backend/.env and run make again.\n'
                     'This app requires a real model; it does not pretend keyword searches are AI.\n')
print('OpenAI credential configured (not verified remotely).')
