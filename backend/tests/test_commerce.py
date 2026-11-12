"""End-to-end API tests against disposable SQLite, with fake payment gateway.

No real OpenAI calls or money transfers during automated tests.
"""
import json
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from app import db
from app.main import app


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'commerce.sqlite3')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    monkeypatch.setenv('AI_ENABLED','true')
    monkeypatch.setenv('AI_MODEL','gpt-5')
    with TestClient(app) as test_client:
        yield test_client


def session(client):
    response=client.post('/api/session',json={})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['history'][0]['role']=='assistant'
    assert data['session_id']
    return data['session_id']


def attach(client,sid):
    # A user can receive A2UI via a concrete UI action; use this to exercise
    # authenticated source-surface checks for subsequent clicks.
    surface='ui_'+sid[:20]
    db.save_chat_message(sid,'assistant','Produtos locais',
        [{'version':'1.0','createSurface':{'surfaceId':surface,'components':[], 'dataModel':{}}}],surface)
    return surface


def event(client,sid,surface,event_name,**context):
    # Simulate an authenticated A2UI button with form-bound context values.
    # The real browser receives the same contract from the server-rendered surface.
    import uuid
    from datetime import datetime, timezone
    surface='ui_'+uuid.uuid4().hex
    button={'id':'action-button','component':'Button','child':'action-label',
            'action':{'event':{'name':event_name,
                  'context':{key:{'@path':'/form/'+key} for key in context}}}}
    wire={'version':'1.0','createSurface':{
        'surfaceId':surface, 'catalogId':'https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json',
        'components':[button,{'id':'action-label','component':'Text','text':event_name}],
        'dataModel':{'form':context}}}
    db.save_chat_message(sid,'assistant','',[wire],surface)
    response=client.post('/api/action',json={'session_id':sid,'message':{
        'version':'1.0','action':{'surfaceId':surface,'sourceComponentId':'action-button',
          'name':event_name,'timestamp':datetime.now(timezone.utc).isoformat(),'context':context}}})
    assert response.status_code==200,response.text
    return response.json()


def next_surface(data):
    turn=data['turn']
    assert turn['role']=='assistant'
    assert turn['a2ui'] and len(turn['a2ui'])==1
    wire=turn['a2ui'][0]
    assert wire['version']=='1.0'
    assert 'createSurface' in wire
    assert wire['createSurface']['surfaceId']==turn['surface_id']
    nodes=wire['createSurface']['components']
    ids={x['id'] for x in nodes}
    assert 'root' in ids and len(ids)==len(nodes)
    for item in nodes:
        if item['component'] in ('Column','Row'):
            assert all(child in ids for child in item['children'])
        if item['component'] in ('Card','Button'):
            assert item['child'] in ids
    return turn['surface_id']


def checkout_data(method='pix',**overrides):
    data={'name':'Pessoa Demo','email':'demo@example.com','zip':'24220000',
          'address':'Rua Exemplo','number':'22','complement':'',
          'city':'Niterói','state':'RJ','coupon':'BEMVINDO10','payment':[method]}
    data.update(overrides)
    return data


def test_welcome_history_and_product_assets(client):
    sid=session(client)
    data=client.post('/api/session',json={'session_id':sid}).json()
    assert len(data['history'])==1
    assert client.get('/api/health').json()=={'ok':True}
    assert len(client.get('/api/products').json())==12
    assert client.get('/images/headphones.webp').status_code==200


def test_category_and_cart_in_chat(client):
    sid=session(client); src=attach(client,sid)
    cat=event(client,sid,src,'categories')
    src=next_surface(cat)
    assert 'categoria' in cat['turn']['content'].lower()
    p=event(client,sid,src,'category',category='Áudio')
    src=next_surface(p)
    assert 'Fone Studio' in json.dumps(p['turn']['a2ui'],ensure_ascii=False)
    add=event(client,sid,src,'add',id='fone-studio')
    src=next_surface(add)
    assert add['cart_count']==1
    assert '699,00' in json.dumps(add['turn']['a2ui'],ensure_ascii=False)
    qty=event(client,sid,src,'set_qty',id='fone-studio',qty=2)
    assert qty['cart_count']==2
    assert len(db.chat_history(sid))>=9
    assert not any(m['role']=='user' for m in db.chat_history(sid))


def test_checkout_pix_then_pay(client):
    sid=session(client); src=attach(client,sid)
    before=db.get_product('fone-studio')['stock']
    src=next_surface(event(client,sid,src,'add',id='fone-studio'))
    src=next_surface(event(client,sid,src,'checkout'))
    placed=event(client,sid,src,'place_order',**checkout_data())
    src=next_surface(placed)
    oid=db.session(sid)['arg']
    order=db.get_order(oid,sid)
    assert order['status']=='pending'
    assert order['subtotal_cents']==69900
    assert order['total_cents']==62910
    qr=client.get(f'/api/demo-qr/{oid}?session_id={sid}')
    assert qr.status_code==200 and qr.content.startswith(b'\x89PNG')
    assert db.cart_count(sid)==0 and db.get_product('fone-studio')['stock']==before-1
    paid=event(client,sid,src,'approve_payment',order_id=oid)
    next_surface(paid)
    assert db.get_order(oid,sid)['status']=='paid'
    db.approve_demo_payment(oid,sid)
    assert db.get_product('fone-studio')['stock']==before-1


@pytest.mark.parametrize('method',['card','boleto'])
def test_other_payment_methods(client,method):
    sid=session(client); src=attach(client,sid)
    src=next_surface(event(client,sid,src,'add',id='garrafa-pure'))
    src=next_surface(event(client,sid,src,'checkout'))
    src=next_surface(event(client,sid,src,'place_order',**checkout_data(method,coupon='')))
    order=db.get_order(db.session(sid)['arg'],sid)
    assert order['method']==method and order['shipping_cents']==1990
    event(client,sid,src,'approve_payment',order_id=order['id'])
    assert db.get_order(order['id'],sid)['status']=='paid'


def test_invalid_checkout_preserves_values(client):
    sid=session(client); src=attach(client,sid)
    src=next_surface(event(client,sid,src,'add',id='teclado-type'))
    src=next_surface(event(client,sid,src,'checkout'))
    out=event(client,sid,src,'place_order',**checkout_data(coupon='INVALID',email='bad',name='<script>'))
    assert 'Não consegui concluir' in out['turn']['content']
    assert out['turn']['a2ui'][0]['createSurface']['dataModel']['form']['name']=='<script>'
    assert db.cart_count(sid)==1 and not db.get_orders(sid)


def test_cannot_forge_surface_or_cross_session(client):
    sid=session(client); another=session(client)
    src=attach(client,sid)
    response=client.post('/api/action',json={'session_id':another,
      'message':{'version':'1.0','action':{'surfaceId':src,'name':'add','timestamp':'2026-11-12T12:00:00Z','context':{'id':'fone-studio'}}}})
    assert response.status_code==403
    malformed=client.post('/api/action',json={'session_id':sid,
      'message':{'version':'0.9','action':{'surfaceId':src,'name':'cart','context':{}}}})
    assert malformed.status_code==422
    assert db.cart_count(another)==0


def test_no_key_is_explicit_error_not_fake_ai(client,monkeypatch):
    sid=session(client)
    response=client.post('/api/message',json={'session_id':sid,'text':'Qual notebook devo comprar?'})
    assert response.status_code==503
    assert 'indisponível' in response.json()['detail']
    assert len(db.chat_history(sid))==1


def test_real_pydantic_path_invokes_agent_and_tools(client,monkeypatch):
    """A fake Agent proves the API goes through Agent.run & tool, not a regex router."""
    sid=session(client)
    monkeypatch.setenv('OPENAI_API_KEY','sk-test-not-a-real-key')
    received=[]
    class FakeRunContext:
        def __init__(self,deps): self.deps=deps
        @classmethod
        def __class_getitem__(cls,item): return cls
    class FakeAgent:
        def __init__(self,model,**kwargs):
            received.append(('init',getattr(model,'model_name',model)));self.tools={}
        def tool(self,fn): self.tools[fn.__name__]=fn;return fn
        async def run(self,message,**kwargs):
            received.append(('run',message))
            self.tools['find_products'](FakeRunContext(kwargs['deps']),query='fone')
            return types.SimpleNamespace(output='Achei um fone com ANC por R$ 699.',
              all_messages_json=lambda: b'[]')
    fake=types.ModuleType('pydantic_ai')
    fake.Agent=FakeAgent
    fake.RunContext=FakeRunContext
    model_module=types.ModuleType('pydantic_ai.models')
    openai_module=types.ModuleType('pydantic_ai.models.openai')
    class FakeResponsesModel:
        def __init__(self,model_name): self.model_name=model_name
    openai_module.OpenAIResponsesModel=FakeResponsesModel
    monkeypatch.setitem(sys.modules,'pydantic_ai.models',model_module)
    monkeypatch.setitem(sys.modules,'pydantic_ai.models.openai',openai_module)
    messages=types.ModuleType('pydantic_ai.messages')
    messages.ModelMessagesTypeAdapter=types.SimpleNamespace(validate_json=lambda x: [])
    monkeypatch.setitem(sys.modules,'pydantic_ai',fake)
    monkeypatch.setitem(sys.modules,'pydantic_ai.messages',messages)
    response=client.post('/api/message',json={'session_id':sid,'text':'Me indica um fone?'})
    assert response.status_code==200,response.text
    payload=response.json()
    assert payload['used_real_ai'] is True
    assert payload['tools_called']==['find_products']
    assert received==[('init','gpt-5'),('run','Me indica um fone?')]
    assert 'Fone Studio' in json.dumps(payload['turn']['a2ui'],ensure_ascii=False)
    next_surface(payload)
    # Subsequent requests must load the PydanticAI history from SQLite.
    assert db.load_ai_history(sid)=='[]'
    assert len(db.chat_history(sid))==3


def test_model_failures_are_not_silenced(client,monkeypatch):
    sid=session(client)
    monkeypatch.setenv('OPENAI_API_KEY','sk-test')
    async def crash(message,sid):
        from app.ai import AIServiceError
        raise AIServiceError('Falha na OpenAI/PydanticAI (AuthenticationError): invalid key')
    monkeypatch.setattr('app.main.reply_with_ai',crash)
    response=client.post('/api/message',json={'session_id':sid,'text':'Quero produtos'})
    assert response.status_code==502
    assert 'Não consegui responder' in response.json()['detail']
    assert len(db.chat_history(sid))==1


def test_cancel_restores_stock(client):
    sid=session(client);src=attach(client,sid)
    before=db.get_product('camera-frame')['stock']
    src=next_surface(event(client,sid,src,'add',id='camera-frame'))
    src=next_surface(event(client,sid,src,'checkout'))
    src=next_surface(event(client,sid,src,'place_order',**checkout_data(coupon='')))
    oid=db.session(sid)['arg']
    assert db.get_product('camera-frame')['stock']==before-1
    src=next_surface(event(client,sid,src,'cancel_order',order_id=oid))
    assert db.get_order(oid,sid)['status']=='cancelled'
    assert db.get_product('camera-frame')['stock']==before
    assert 'Não consegui concluir' in event(client,sid,src,'approve_payment',order_id=oid)['turn']['content']


def test_duplicate_order_and_paid_cancellation_guard(client):
    sid=session(client);src=attach(client,sid)
    src=next_surface(event(client,sid,src,'add',id='garrafa-pure'))
    src=next_surface(event(client,sid,src,'checkout'))
    src=next_surface(event(client,sid,src,'place_order',**checkout_data(coupon='')))
    assert len(db.get_orders(sid))==1
    assert 'Não consegui concluir' in event(client,sid,src,'place_order',**checkout_data())['turn']['content']
    oid=db.session(sid)['arg']
    src=next_surface(event(client,sid,src,'approve_payment',order_id=oid))
    assert 'Não consegui concluir' in event(client,sid,src,'cancel_order',order_id=oid)['turn']['content']


def test_search_filters_accents_and_price(client):
    assert any(p['id']=='fone-studio' for p in db.get_products(query='fone de ouvido'))
    assert any(p['id']=='notebook-orbit' for p in db.get_products(query='notebooks'))
    assert any(p['id']=='camera-frame' for p in db.get_products(query='câmera'))
    assert all(p['price_cents']<=50000 for p in db.get_products(max_cents=50000))


def test_race_orders_cannot_oversell(client):
    customers={'name':'Demo','email':'demo@example.com','zip':'20000000','address':'Rua A',
               'number':'1','city':'Rio','state':'RJ'}
    a=session(client);b=session(client)
    db.set_qty(a,'camera-frame',6);db.set_qty(b,'camera-frame',6)
    barrier=Barrier(2)
    def create(sid):
        barrier.wait(timeout=5)
        try:return db.create_order(sid,customers,'pix')
        except ValueError as exc:return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(create,sid) for sid in (a,b)]
        results=[f.result(timeout=10) for f in futures]
    assert sum(r.startswith('PED-') for r in results)==1
    assert 'Estoque insuficiente' in str(results)


def test_ui_messages_replay_after_new_session(client):
    sid=session(client);src=attach(client,sid)
    out=event(client,sid,src,'categories')
    sid2=client.post('/api/session',json={'session_id':sid}).json()
    assert len(sid2['history'])>=4
    assert any(entry['surface_id']==out['turn']['surface_id'] for entry in sid2['history'])
    assert all(entry.get('a2ui') is None or isinstance(entry['a2ui'],list) for entry in sid2['history'])


def test_sqlite_chat_history_restores_in_order(client):
    sid=session(client)
    db.save_chat_message(sid,'user','Primeira pergunta')
    db.save_chat_message(sid,'assistant','Primeira resposta')
    db.save_chat_message(sid,'user','Segunda pergunta')
    data=client.post('/api/session',json={'session_id':sid})
    assert data.status_code==200,data.text
    messages=data.json()['history']
    assert [m['content'] for m in messages[-3:]] == [
        'Primeira pergunta', 'Primeira resposta', 'Segunda pergunta',
    ]
    assert len({m['id'] for m in messages})==len(messages)


def test_sqlite_chat_history_limit_keeps_latest_80(client):
    sid=session(client)
    for i in range(95):
        db.save_chat_message(sid,'user',f'Linha {i:03d}')
    history=client.post('/api/session',json={'session_id':sid}).json()['history']
    assert len(history)==80
    assert history[0]['content']=='Linha 015'
    assert history[-1]['content']=='Linha 094'


def test_exact_gpt5_responses_model_config(client,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','sk-test')
    from app.ai import ai_config
    assert ai_config()['model']=='gpt-5'
    assert ai_config()['configured'] is True
    api=client.post('/api/session',json={}).json()
    assert 'ai' not in api and 'model' not in api
    assert ai_config()['model']=='gpt-5'


def test_action_does_not_fabricate_user_message(client):
    sid=session(client)
    initial_users=[t for t in db.chat_history(sid) if t['role']=='user']
    event(client,sid,'unused','categories')
    assert [t for t in db.chat_history(sid) if t['role']=='user']==initial_users
    assert db.recent_actions(sid)[0]['event_name']=='categories'


def test_rejects_forged_component_and_tampered_static_product(client):
    from app.ui import render
    sid=session(client)
    db.navigate(sid,'product','fone-studio')
    surface='ui_verified'
    wire=render(sid,surface)
    db.save_chat_message(sid,'assistant','',wire,surface)
    button=next(node for node in wire[0]['createSurface']['components']
                if node['component']=='Button' and node['action']['event']['name']=='add')
    payload={'version':'1.0','action':{'surfaceId':surface,'sourceComponentId':button['id'],
             'name':'add','timestamp':'2026-11-12T12:00:00Z','context':{'id':'garrafa-pure'}}}
    response=client.post('/api/action',json={'session_id':sid,'message':payload})
    assert response.status_code==403
    payload['action']['sourceComponentId']='not_a_button'
    response=client.post('/api/action',json={'session_id':sid,'message':payload})
    assert response.status_code==403
    assert db.cart_count(sid)==0


def test_real_button_provenance_and_schema(client):
    from app.ui import render
    sid=session(client)
    db.navigate(sid,'product','fone-studio')
    surface='ui_verified_add'
    wire=render(sid,surface)
    db.save_chat_message(sid,'assistant','',wire,surface)
    button=next(node for node in wire[0]['createSurface']['components']
                if node['component']=='Button' and node['action']['event']['name']=='add')
    assert 'userMessage' not in button['action']['event']
    result=client.post('/api/action',json={'session_id':sid,'message':{
        'version':'1.0','action':{'surfaceId':surface,
        'sourceComponentId':button['id'],'name':'add','timestamp':'2026-11-12T12:00:00Z','context':{'id':'fone-studio'}}}})
    assert result.status_code==200, result.text
    assert result.json()['cart_count']==1
    assert not any(item['role']=='user' for item in db.chat_history(sid))


def test_click_uses_model_for_natural_followup_without_fake_user_turn(client,monkeypatch):
    sid=session(client)
    monkeypatch.setenv('OPENAI_API_KEY','sk-test')
    calls=[]
    async def fake_ai(sid,event_name,outcome):
        calls.append((event_name,outcome))
        return 'Claro! Separei as opções por categoria. Qual te interessa mais?'
    monkeypatch.setattr('app.main.reply_after_action',fake_ai)
    out=event(client,sid,'unused','categories')
    assert out['used_real_ai'] is True
    assert out['turn']['via']=='pydantic-ai'
    assert out['turn']['content'].startswith('Claro!')
    assert calls[0][0]=='categories'
    assert not [turn for turn in db.chat_history(sid) if turn['role']=='user']


def test_duplicate_button_event_is_not_applied_twice(client):
    from app.ui import render
    sid=session(client)
    db.navigate(sid,'product','fone-studio')
    surface='ui_exactly_once'
    wire=render(sid,surface)
    db.save_chat_message(sid,'assistant','',wire,surface)
    button=next(node for node in wire[0]['createSurface']['components']
                if node['component']=='Button' and node['action']['event']['name']=='add')
    payload={'session_id':sid,'message':{'version':'1.0','action':{
        'surfaceId':surface,'sourceComponentId':button['id'],
        'name':'add','timestamp':'2026-11-12T18:00:00Z','context':{'id':'fone-studio'}}}}
    first=client.post('/api/action',json=payload)
    second=client.post('/api/action',json=payload)
    assert first.status_code==200,first.text
    assert second.status_code==409
    assert db.cart_count(sid)==1


def test_search_aliases_do_not_mix_headphones_and_speakers(client):
    found=db.get_products(query='fone')
    assert {'fone-studio','buds-cloud'} <= {p['id'] for p in found}
    assert 'caixa-sound' not in {p['id'] for p in found}


def test_real_checkout_form_button_with_data_binding(client):
    from app.ui import render
    sid=session(client)
    db.add_to_cart(sid,'buds-cloud')
    db.navigate(sid,'checkout')
    surface='ui_real_checkout'
    wire=render(sid,surface)
    db.save_chat_message(sid,'assistant','',wire,surface)
    button=next(node for node in wire[0]['createSurface']['components']
                if node['component']=='Button' and node['action']['event']['name']=='place_order')
    data=checkout_data()
    result=client.post('/api/action',json={'session_id':sid,'message':{'version':'1.0','action':{
        'surfaceId':surface,'sourceComponentId':button['id'],'name':'place_order',
        'timestamp':'2026-11-12T18:30:00Z','context':data}}})
    assert result.status_code==200,result.text
    assert db.get_orders(sid)[0]['status']=='pending'


def test_welcome_and_agent_origin_survive_reopening_session(client):
    sid=session(client)
    original=db.chat_history(sid)
    assert original[0]['via']=='welcome'
    restored=client.post('/api/session',json={'session_id':sid})
    assert restored.status_code==200
    assert restored.json()['history'][0]['via']=='welcome'
    message=db.save_chat_message(sid,'assistant','Confirmado.',via='pydantic-ai')
    assert message['via']=='pydantic-ai'
    assert db.chat_history(sid)[-1]['via']=='pydantic-ai'


def test_header_cart_navigation_does_not_send_keyword_message(client):
    sid=session(client)
    result=client.post('/api/cart/view',json={'session_id':sid})
    assert result.status_code==200,result.text
    assert result.json()['turn']['a2ui']
    assert not any(turn['role']=='user' for turn in db.chat_history(sid))
    assert db.recent_actions(sid)[0]['event_name']=='cart'
