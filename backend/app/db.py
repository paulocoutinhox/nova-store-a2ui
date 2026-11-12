"""SQLite catalog, order lifecycle and demo-only payment engine."""
from __future__ import annotations

import json
import os
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv('DATABASE_PATH', str(BASE / 'data' / 'commerce.sqlite3')))
FREE_SHIPPING_THRESHOLD = 30000
SHIPPING_CENTS = 1990

CATALOG = [
    ('notebook-orbit', 'Notebook Orbit 14', 'Eletrônicos', 429900, 12, 'laptop', 'Leve, rápido e ideal para criar de qualquer lugar.', '16 GB RAM · SSD 512 GB · Tela 14”'),
    ('fone-studio', 'Fone Studio ANC', 'Áudio', 69900, 22, 'headphones', 'Som imersivo com cancelamento ativo de ruído.', 'Bluetooth 5.3 · Até 32 horas'),
    ('smartphone-nova', 'Smartphone Nova 5G', 'Eletrônicos', 289900, 9, 'smartphone', 'Fotografia brilhante e bateria para o dia todo.', '256 GB · OLED 6,5” · 5G'),
    ('watch-pulse', 'Smartwatch Pulse', 'Eletrônicos', 99900, 18, 'smartwatch', 'Bem-estar, movimento e notificações no pulso.', 'GPS · 7 dias de bateria'),
    ('camera-frame', 'Câmera Frame X', 'Eletrônicos', 389900, 6, 'camera', 'Capture cada detalhe com estilo e precisão.', '24 MP · 4K · Wi-Fi'),
    ('teclado-type', 'Teclado Type Mini', 'Acessórios', 47900, 30, 'keyboard', 'Um toque de personalidade para o seu setup.', 'Mecânico · USB-C · 68 teclas'),
    ('caixa-sound', 'Caixa Sound Go', 'Áudio', 34900, 35, 'speaker', 'Áudio encorpado em um formato compacto.', 'IPX7 · Bluetooth · 12 horas'),
    ('buds-cloud', 'Buds Cloud Pro', 'Áudio', 59900, 28, 'earbuds', 'Liberdade e clareza do início ao fim do dia.', 'ANC · Estojo USB-C'),
    ('mochila-terra', 'Mochila Terra', 'Lifestyle', 45900, 14, 'backpack', 'Acompanhe a rotina com espaço e elegância.', 'Compartimento para notebook 15”'),
    ('tenis-flow', 'Tênis Flow Runner', 'Lifestyle', 54900, 17, 'sneakers', 'Conforto para todos os seus caminhos.', 'Malha respirável · Solado leve'),
    ('garrafa-pure', 'Garrafa Pure Steel', 'Lifestyle', 15900, 42, 'bottle', 'Hidratação com design minimalista.', '500 ml · Aço inox · Térmica'),
    ('luminaria-glow', 'Luminária Glow', 'Acessórios', 32900, 16, 'lamp', 'Uma luz aconchegante para qualquer ambiente.', 'LED · Luz quente · Bivolt'),
]

SEARCH_ALIASES = {
    'fone-studio': 'fone fones headset headphone headphones ouvido musica anc bluetooth',
    'buds-cloud': 'fone fones earbuds intra auricular bluetooth sem fio tws anc ouvido',
    'caixa-sound': 'caixa som speaker alto falante portatil bluetooth',
    'notebook-orbit': 'computador laptop notebook trabalho programacao estudo',
    'watch-pulse': 'relogio smartwatch inteligente pulso',
    'teclado-type': 'teclado mecanico computador digitacao',
    'smartphone-nova': 'celular smartphone telefone telefone movel',
    'camera-frame': 'camera fotografia foto video',
}


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(write=False):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=12, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=12000')
    try:
        if write:
            conn.execute('BEGIN IMMEDIATE')
        yield conn
        if write:
            conn.execute('COMMIT')
    except Exception:
        if write:
            conn.execute('ROLLBACK')
        raise
    finally:
        conn.close()


def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS products (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
          price_cents INTEGER NOT NULL CHECK(price_cents>=0), stock INTEGER NOT NULL CHECK(stock>=0),
          image TEXT NOT NULL, description TEXT NOT NULL, specs TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY, view TEXT NOT NULL DEFAULT 'home', arg TEXT NOT NULL DEFAULT '',
          draft_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cart_items (
          session_id TEXT NOT NULL REFERENCES sessions(id),
          product_id TEXT NOT NULL REFERENCES products(id), qty INTEGER NOT NULL CHECK(qty>0),
          PRIMARY KEY(session_id,product_id));
        CREATE TABLE IF NOT EXISTS orders (
          id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
          customer_json TEXT NOT NULL, method TEXT NOT NULL, coupon TEXT NOT NULL,
          subtotal_cents INTEGER NOT NULL, discount_cents INTEGER NOT NULL,
          shipping_cents INTEGER NOT NULL, total_cents INTEGER NOT NULL,
          status TEXT NOT NULL, created_at TEXT NOT NULL, paid_at TEXT);
        CREATE TABLE IF NOT EXISTS order_items (
          order_id TEXT NOT NULL REFERENCES orders(id), product_id TEXT NOT NULL,
          name TEXT NOT NULL, price_cents INTEGER NOT NULL, qty INTEGER NOT NULL,
          PRIMARY KEY(order_id,product_id));
        CREATE TABLE IF NOT EXISTS payments (
          id TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE REFERENCES orders(id),
          provider TEXT NOT NULL, status TEXT NOT NULL, method TEXT NOT NULL,
          external_reference TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
    with connect(write=True) as db:
        if db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
            db.executemany('INSERT INTO products VALUES (?,?,?,?,?,?,?,?)',
                           [(i,n,c,p,s,f'/images/{img}.webp',d,sp) for i,n,c,p,s,img,d,sp in CATALOG])
    initialize_chat()


def rowdict(row):
    return dict(row) if row is not None else None


def _search_words(value):
    """Accent-insensitive, small-catalog search with Portuguese stop words."""
    folded = ''.join(c for c in unicodedata.normalize('NFKD', str(value).lower())
                     if not unicodedata.combining(c))
    stop = {'de', 'do', 'da', 'dos', 'das', 'a', 'o', 'os', 'as', 'e', 'um', 'uma',
            'para', 'com', 'por', 'ouvido', 'ate', 'quero', 'me', 'mostre', 'ver'}
    words = []
    for raw in folded.replace('-', ' ').split():
        word = raw.strip('.,:;!?"\\/()[]{}')
        if word in stop or len(word) < 2:
            continue
        if word.endswith('s') and len(word) > 4 and not word.endswith('ss'):
            word = word[:-1]
        words.append(word)
    return words[:8]


def get_products(category=None, query=None, max_cents=None, limit=12):
    """Deterministic filter; a full-text index would replace this for large stores."""
    with connect() as conn:
        candidates = [dict(row) for row in conn.execute(
            'SELECT * FROM products ORDER BY name')]
    words = _search_words(query) if query else []
    matched = []
    for item in candidates:
        if category and item['category'] != category:
            continue
        if max_cents is not None and item['price_cents'] > max_cents:
            continue
        searchable = _search_words(' '.join(str(item[field]) for field in
                             ('name', 'category', 'description', 'specs')))
        searchable += _search_words(SEARCH_ALIASES.get(item['id'], ''))
        if words:
            score = sum(any(token == word or token.startswith(word) for token in searchable)
                        for word in words)
            if not score:
                continue
        else:
            score = 0
        matched.append((score, item))
    matched.sort(key=lambda entry: (-entry[0], entry[1]['name']))
    return [item for _, item in matched[:max(1, min(int(limit), 60))]]



def get_product(pid):
    with connect() as db:
        return rowdict(db.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone())


def categories():
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT category AS name, COUNT(*) AS count FROM products GROUP BY category ORDER BY category')]


def ensure_session(sid):
    if not sid or len(sid)>80 or not all(c.isalnum() or c in '-_' for c in sid):
        raise ValueError('Sessão inválida')
    with connect(write=True) as db:
        db.execute('INSERT OR IGNORE INTO sessions(id,created_at) VALUES (?,?)', (sid, now()))


def session(sid):
    with connect() as db:
        return rowdict(db.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone())


def navigate(sid, view, arg='', draft=None):
    with connect(write=True) as db:
        if draft is None:
            db.execute('UPDATE sessions SET view=?,arg=? WHERE id=?',(view,str(arg),sid))
        else:
            db.execute('UPDATE sessions SET view=?,arg=?,draft_json=? WHERE id=?',(view,str(arg),json.dumps(draft,ensure_ascii=False),sid))


def cart(sid):
    with connect() as db:
        return [dict(row) for row in db.execute('''SELECT p.*, c.qty FROM cart_items c JOIN products p ON p.id=c.product_id
            WHERE c.session_id=? ORDER BY p.name''',(sid,))]


def cart_count(sid):
    return sum(x['qty'] for x in cart(sid))


def set_qty(sid, pid, qty):
    if not isinstance(qty, int) or qty<0 or qty>10:
        raise ValueError('Quantidade deve estar entre 0 e 10.')
    with connect(write=True) as db:
        p=db.execute('SELECT stock FROM products WHERE id=?',(pid,)).fetchone()
        if not p: raise ValueError('Produto não encontrado.')
        if qty>p['stock']: raise ValueError('Estoque insuficiente.')
        if qty == 0:
            db.execute('DELETE FROM cart_items WHERE session_id=? AND product_id=?',(sid,pid))
        else:
            db.execute('''INSERT INTO cart_items(session_id,product_id,qty) VALUES (?,?,?)
             ON CONFLICT(session_id,product_id) DO UPDATE SET qty=excluded.qty''',(sid,pid,qty))


def add_to_cart(sid,pid,qty=1):
    if qty not in range(1,11): raise ValueError('Quantidade inválida.')
    with connect(write=True) as db:
        p=db.execute('SELECT stock FROM products WHERE id=?',(pid,)).fetchone()
        if not p: raise ValueError('Produto não encontrado.')
        current=db.execute('SELECT qty FROM cart_items WHERE session_id=? AND product_id=?',(sid,pid)).fetchone()
        new=(current['qty'] if current else 0)+qty
        if new>10 or new>p['stock']: raise ValueError('Limite por pedido ou estoque insuficiente.')
        db.execute('''INSERT INTO cart_items(session_id,product_id,qty) VALUES (?,?,?)
           ON CONFLICT(session_id,product_id) DO UPDATE SET qty=excluded.qty''',(sid,pid,new))


def quote(sid, coupon=''):
    items=cart(sid)
    subtotal=sum(p['price_cents']*p['qty'] for p in items)
    code=(coupon or '').strip().upper()
    discount=(subtotal//10) if code=='BEMVINDO10' else 0
    shipping=0 if subtotal == 0 or subtotal >= FREE_SHIPPING_THRESHOLD else SHIPPING_CENTS
    return dict(items=items,subtotal_cents=subtotal,discount_cents=discount,
                shipping_cents=shipping,total_cents=subtotal-discount+shipping,
                coupon=code if code=='BEMVINDO10' else '',coupon_invalid=bool(code and code!='BEMVINDO10'))


def create_order(sid, customer, method, coupon=''):
    if method not in ('pix','card','boleto'): raise ValueError('Forma de pagamento inválida.')
    required=('name','email','zip','address','number','city','state')
    if any(not str(customer.get(k,'')).strip() for k in required):
        raise ValueError('Preencha nome, e-mail e endereço de entrega.')
    if '@' not in customer['email'] or '.' not in customer['email'].split('@')[-1]:
        raise ValueError('Informe um e-mail válido.')
    if len(''.join(ch for ch in customer['zip'] if ch.isdigit()))!=8:
        raise ValueError('Informe um CEP de 8 dígitos.')
    if len(customer['name'])>120 or len(customer['address'])>200 or len(customer['email'])>180:
        raise ValueError('Dados de cadastro muito longos.')
    with connect(write=True) as db:
        items=[dict(row) for row in db.execute('''SELECT p.*,c.qty FROM cart_items c
           JOIN products p ON p.id=c.product_id WHERE c.session_id=?''',(sid,))]
        if not items: raise ValueError('Seu carrinho está vazio.')
        for item in items:
            if item['qty']>item['stock']:
                raise ValueError(f'Estoque insuficiente para {item["name"]}.')
        subtotal=sum(x['price_cents']*x['qty'] for x in items)
        code=(coupon or '').strip().upper()
        if code and code != 'BEMVINDO10': raise ValueError('Cupom inválido.')
        discount=subtotal//10 if code else 0
        shipping=0 if subtotal>=FREE_SHIPPING_THRESHOLD else SHIPPING_CENTS
        total=subtotal-discount+shipping
        oid='PED-'+uuid.uuid4().hex[:9].upper()
        db.execute('''INSERT INTO orders(id,session_id,customer_json,method,coupon,subtotal_cents,discount_cents,shipping_cents,total_cents,status,created_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (oid,sid,json.dumps(customer,ensure_ascii=False),method,code,subtotal,discount,shipping,total,'pending',now()))
        for item in items:
            db.execute('INSERT INTO order_items VALUES (?,?,?,?,?)', (oid,item['id'],item['name'],item['price_cents'],item['qty']))
            db.execute('UPDATE products SET stock=stock-? WHERE id=? AND stock>=?',(item['qty'],item['id'],item['qty']))
        ref='TESTE-'+uuid.uuid4().hex[:16].upper()
        db.execute('INSERT INTO payments VALUES (?,?,?,?,?,?,?)',('PAY-'+uuid.uuid4().hex[:10].upper(),oid,'simulator','pending',method,ref,now()))
        db.execute('DELETE FROM cart_items WHERE session_id=?',(sid,))
    return oid


def get_order(oid,sid):
    with connect() as db:
        order=rowdict(db.execute('SELECT * FROM orders WHERE id=? AND session_id=?',(oid,sid)).fetchone())
        if not order: return None
        order['customer']=json.loads(order.pop('customer_json'))
        order['items']=[dict(r) for r in db.execute('SELECT * FROM order_items WHERE order_id=?',(oid,))]
        order['payment']=rowdict(db.execute('SELECT * FROM payments WHERE order_id=?',(oid,)).fetchone())
        return order


def get_orders(sid):
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT id,total_cents,method,status,created_at FROM orders WHERE session_id=? ORDER BY created_at DESC',(sid,))]


def approve_demo_payment(oid,sid):
    with connect(write=True) as db:
        order=db.execute('SELECT status FROM orders WHERE id=? AND session_id=?',(oid,sid)).fetchone()
        if not order: raise ValueError('Pedido não encontrado.')
        if order['status']=='paid': return
        if order['status']!='pending': raise ValueError('Pagamento não pode ser aprovado.')
        db.execute('UPDATE orders SET status=?,paid_at=? WHERE id=?',('paid',now(),oid))
        db.execute('UPDATE payments SET status=? WHERE order_id=?',('approved',oid))


def cancel_demo_order(oid, sid):
    """Cancel a still-unpaid demo order and atomically return reserved stock."""
    with connect(write=True) as conn:
        order = conn.execute('SELECT status FROM orders WHERE id=? AND session_id=?',
                             (oid, sid)).fetchone()
        if not order:
            raise ValueError('Pedido não encontrado nesta sessão.')
        if order['status'] == 'cancelled':
            return
        if order['status'] != 'pending':
            raise ValueError('Um pedido pago não pode ser cancelado neste simulador.')
        for item in conn.execute('SELECT product_id, qty FROM order_items WHERE order_id=?', (oid,)):
            conn.execute('UPDATE products SET stock = stock + ? WHERE id=?',
                         (item['qty'], item['product_id']))
        conn.execute("UPDATE orders SET status='cancelled' WHERE id=?", (oid,))
        conn.execute("UPDATE payments SET status='cancelled' WHERE order_id=?", (oid,))

# Conversational interface history and PydanticAI model-message history.
# Chat messages include a full, immutable A2UI snapshot for session replay.
def initialize_chat():
    with connect() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS chat_messages (
          id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
          role TEXT NOT NULL, content TEXT NOT NULL, surface_id TEXT,
          a2ui_json TEXT, created_at TEXT NOT NULL, via TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, created_at);
        CREATE TABLE IF NOT EXISTS ai_history (
          session_id TEXT PRIMARY KEY REFERENCES sessions(id), history_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS action_events (
          id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
          event_name TEXT NOT NULL, outcome TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS action_receipts (
          event_token TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
          created_at TEXT NOT NULL);
        ''')
    # Preserve existing databases from earlier demo versions.
    with connect(write=True) as conn:
        cols = {row['name'] for row in conn.execute('PRAGMA table_info(chat_messages)')}
        if 'via' not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN via TEXT NOT NULL DEFAULT ''")


def save_chat_message(sid, role, content, a2ui=None, surface_id=None, via=''):
    mid=uuid.uuid4().hex
    with connect(write=True) as conn:
        conn.execute('''INSERT INTO chat_messages(id,session_id,role,content,surface_id,a2ui_json,created_at,via)
          VALUES(?,?,?,?,?,?,?,?)''',
          (mid,sid,role,content,surface_id,json.dumps(a2ui,ensure_ascii=False) if a2ui else None,now(),via))
    return get_chat_message(mid)


def get_chat_message(mid):
    with connect() as conn:
        row=rowdict(conn.execute('SELECT * FROM chat_messages WHERE id=?',(mid,)).fetchone())
    if not row: return None
    row['a2ui']=json.loads(row.pop('a2ui_json')) if row['a2ui_json'] else None
    return row


def chat_history(sid, limit=80):
    # SQLite rowid is not exposed by SELECT * in the derived table.
    # Select newest rows first, then restore natural chronological order in Python.
    with connect() as conn:
        rows=[dict(r) for r in conn.execute('''
          SELECT * FROM chat_messages WHERE session_id=?
          ORDER BY rowid DESC LIMIT ?''', (sid,limit))]
    rows.reverse()
    for row in rows:
        row['a2ui']=json.loads(row.pop('a2ui_json')) if row['a2ui_json'] else None
    return rows


def surface_belongs_to(sid,surface_id):
    with connect() as conn:
        return bool(conn.execute('''SELECT 1 FROM chat_messages WHERE session_id=? AND surface_id=?
          AND role='assistant' LIMIT 1''',(sid,surface_id)).fetchone())


def load_ai_history(sid):
    with connect() as conn:
        row=conn.execute('SELECT history_json FROM ai_history WHERE session_id=?',(sid,)).fetchone()
    return row['history_json'] if row else None


def save_ai_history(sid, history):
    with connect(write=True) as conn:
        conn.execute('''INSERT INTO ai_history(session_id,history_json) VALUES(?,?)
          ON CONFLICT(session_id) DO UPDATE SET history_json=excluded.history_json''',(sid,history))


def record_action(sid, event_name, outcome):
    """Record a UI gesture without inventing a user chat message."""
    with connect(write=True) as conn:
        conn.execute('INSERT INTO action_events VALUES (?,?,?,?,?)',
                     (uuid.uuid4().hex, sid, event_name, outcome, now()))


def recent_actions(sid, limit=5):
    with connect() as conn:
        rows = conn.execute('SELECT event_name, outcome FROM action_events WHERE session_id=? ORDER BY rowid DESC LIMIT ?',
                            (sid, limit))
        return [dict(row) for row in rows]


def authorize_surface_action(sid, surface_id, component_id, name, context):
    """Check the original button contract, including immutable action arguments."""
    with connect() as conn:
        row = conn.execute('SELECT a2ui_json FROM chat_messages WHERE session_id=? AND surface_id=? AND role=? LIMIT 1',
                           (sid, surface_id, 'assistant')).fetchone()
    if not row or not row['a2ui_json']:
        return False
    for wire in json.loads(row['a2ui_json']):
        surface = wire.get('createSurface', {})
        if surface.get('surfaceId') != surface_id:
            continue
        for component in surface.get('components', []):
            if component.get('id') != component_id or component.get('component') != 'Button':
                continue
            spec = component.get('action', {}).get('event', {})
            if spec.get('name') != name:
                return False
            expected = spec.get('context', {})
            if set(expected) != set(context):
                return False
            for key, value in expected.items():
                if isinstance(value, dict) and set(value) == {'@path'}:
                    if not isinstance(value['@path'], str) or not value['@path'].startswith('/form/'):
                        return False
                    continue
                if value != context[key]:
                    return False
            return True
    return False


def claim_action(sid, surface_id, component_id, timestamp):
    """Prevent duplicate retries of a single A2UI gesture."""
    token = f'{sid}:{surface_id}:{component_id}:{timestamp}'
    with connect(write=True) as conn:
        try:
            conn.execute('INSERT INTO action_receipts VALUES (?,?,?)', (token, sid, now()))
            return True
        except sqlite3.IntegrityError:
            return False
