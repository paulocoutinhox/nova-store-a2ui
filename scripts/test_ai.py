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
        raise SystemExit('Configure OPENAI_API_KEY em backend/.env antes de make test-ai')
    db.initialize()
    sid='smoke_'+uuid.uuid4().hex
    db.ensure_session(sid)
    print('Chamando modelo real:',config['model'])
    output,tools=await reply_with_ai('Procure no catálogo um fone com cancelamento de ruído e diga o preço.',sid)
    print('Ferramentas usadas:',tools)
    print('Resposta:',output)
    if 'find_products' not in tools:
        raise SystemExit('O agente respondeu sem chamar a ferramenta de busca; verifique o prompt e o modelo.')
    print('IA e ferramenta: OK')


if __name__=='__main__':
    asyncio.run(main())
