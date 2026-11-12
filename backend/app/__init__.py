"""NOVA Commerce Python package and local environment configuration."""
from pathlib import Path
from dotenv import load_dotenv

# Explicit environment variables take precedence over local .env values.
load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
