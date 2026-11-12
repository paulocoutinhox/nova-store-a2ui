"""Live, paid-model smoke test. Run manually with `make test-ai`."""
import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))

from dotenv import load_dotenv
load_dotenv(ROOT/'backend'/'.env')
from app import db
from app.ai import reply_with_ai, ai_config


async def main():
    config=ai_config()
    if not config['configured']:
        raise SystemExit('Set OPENAI_API_KEY in backend/.env before running make test-ai')
    db.initialize()
    sid='smoke_'+uuid.uuid4().hex
    db.ensure_session(sid)
    print('Calling real model:',config['model'])
    output,tools=await reply_with_ai('Find headphones with noise cancellation in the catalog and tell me the price.',sid)
    print('Tools used:',tools)
    print('Response:',output)
    if 'find_products' not in tools:
        raise SystemExit('The agent did not call the search tool. Check the prompt and model configuration.')
    print('AI and tool invocation: OK')


if __name__=='__main__':
    asyncio.run(main())
