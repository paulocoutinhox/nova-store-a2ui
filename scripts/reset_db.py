"""Reset local demo state only. Do not use with a production database."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app import db  # noqa: E402

if db.DB_PATH.resolve() != (ROOT / 'backend' / 'data' / 'commerce.sqlite3').resolve():
    raise SystemExit('Refusing to reset a custom DATABASE_PATH. Point DATABASE_PATH to the local demo DB.')
if db.DB_PATH.exists():
    db.DB_PATH.unlink()
for suffix in ('-wal', '-shm'):
    path = Path(str(db.DB_PATH) + suffix)
    if path.exists():
        path.unlink()
db.initialize()
print(f'Demo database reset and seeded: {db.DB_PATH}')
