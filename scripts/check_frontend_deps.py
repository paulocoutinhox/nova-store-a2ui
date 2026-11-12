#!/usr/bin/env python3
"""Check the tested React + Tailwind v4 + daisyUI v5 dependency family."""
import json
from pathlib import Path

manifest = json.loads((Path(__file__).resolve().parents[1] / 'frontend/package.json').read_text())
deps = manifest['dependencies']
dev = manifest['devDependencies']
requirements = {
    'react': '19',
    'react-dom': '19',
    'tailwindcss': '4',
    '@tailwindcss/vite': '4',
    'daisyui': '5',
}
for name, major in requirements.items():
    version = str((deps | dev).get(name, '')).lstrip('^~')
    if not version.startswith(major + '.'):
        raise SystemExit(f'Expected {name} major {major}, got {version}')
if '@a2ui/react' in deps or '@a2ui/web_core' in deps:
    raise SystemExit('Do not install the incompatible generic A2UI CSS renderer in this custom React catalog.')
print('React, Tailwind CSS 4 and daisyUI 5 dependency families: OK')
