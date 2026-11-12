"""WhatsApp-style conversational commerce backed by REAL PydanticAI tools + A2UI 1.0.

Every assistant UI attachment is a separate A2UI surface. Commerce execution,
payment approval and prices are deterministic and stored in local SQLite.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)

from . import db
from .ai import AIServiceError, ai_config, reply_with_ai, reply_after_action
from .ui import render

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.initialize()
    yield


app=FastAPI(title='NOVA — Chat Commerce',version='3.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],
                   allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Content-Type'])
app.mount('/images',StaticFiles(directory=str(Path(__file__).resolve().parents[1]/'assets')),name='images')


class SessionIn(BaseModel):
    session_id: str | None = Field(default=None,max_length=80)


class ChatIn(BaseModel):
    session_id: str = Field(min_length=1,max_length=80)
    text: str = Field(min_length=1,max_length=1200)


class ActionIn(BaseModel):
    session_id: str = Field(min_length=1,max_length=80)
    message: dict


def session_or_422(sid):
    try: db.ensure_session(sid)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


def create_assistant(sid,reply,with_ui=False,via='action',error=''):
    surface_id=f'ui_{uuid.uuid4().hex}' if with_ui else None
    message=render(sid,surface_id,error) if surface_id else None
    turn=db.save_chat_message(sid,'assistant',reply,message,surface_id,via=via)
    return turn


def meta(sid):
    # Internal provider/model details are intentionally excluded from public responses.
    return {'session_id':sid, 'cart_count':db.cart_count(sid)}


@app.get('/api/health')
def health():
    return {'ok':True}


@app.post('/api/session')
def session(body:SessionIn):
    sid=body.session_id or uuid.uuid4().hex
    session_or_422(sid)
    history=db.chat_history(sid)
    if not history:
        create_assistant(sid,
            'Hi! 👋 I’m NOVA. What can I help you find today? I can help you discover, '
            'compare, and buy products—all in this chat.',with_ui=False,via='welcome')
        history=db.chat_history(sid)
    return {**meta(sid),'history':history}


@app.post('/api/message')
async def message(body:ChatIn):
    session_or_422(body.session_id)
    sid=body.session_id
    prompt=body.text.strip()
    if not prompt: raise HTTPException(status_code=422,detail='Type a message.')
    if not ai_config()['configured']:
        config=ai_config()
        raise HTTPException(status_code=503,detail='The shopping assistant is temporarily unavailable.')
    try:
        reply,tools=await reply_with_ai(prompt,sid)
    except AIServiceError as exc:
        logger.exception('PydanticAI message failed')
        # Surface a real error — never return a fabricated, supposedly AI-generated reply.
        raise HTTPException(status_code=502,detail='I could not respond right now. Please try again shortly.') from exc
    # UI only when the agent actually used a tool to display or mutate commerce state.
    db.save_chat_message(sid,'user',prompt)
    attach=bool(tools)
    turn=create_assistant(sid,reply,with_ui=attach,via='pydantic-ai')
    return {**meta(sid),'turn':turn,'used_real_ai':True,'tools_called':tools}


def text_value(context,key,max_len=220):
    value=context.get(key,'')
    return str(value).strip()[:max_len] if not isinstance(value,dict) else ''


def handle_action(sid,name,context):
    if name in ('home','categories','cart','orders'):
        db.navigate(sid,name)
        return {'home':'Here are a few suggestions to get you started.',
                'categories':'Here are the available categories.',
                'cart':'Here is your cart.',
                'orders':'Here are your orders.'}[name]
    if name=='category':
        category=text_value(context,'category',100)
        if category not in [c['name'] for c in db.categories()]:
            raise ValueError('Category not found.')
        db.navigate(sid,'category',category)
        return f'Products in {category}:'
    if name=='product':
        product=db.get_product(text_value(context,'id',100))
        if not product: raise ValueError('Product not found.')
        db.navigate(sid,'product',product['id'])
        return f'Here are the details for {product["name"]}:'
    if name in ('add','buy_now'):
        pid=text_value(context,'id',100)
        item=db.get_product(pid)
        if not item: raise ValueError('Product not found.')
        db.add_to_cart(sid,pid)
        db.navigate(sid,'checkout' if name=='buy_now' else 'cart')
        return f'Added {item["name"]} to your cart. 🛒'
    if name=='set_qty':
        pid=text_value(context,'id',100)
        qty=context.get('qty')
        if type(qty) is not int: raise ValueError('Invalid quantity.')
        db.set_qty(sid,pid,qty)
        db.navigate(sid,'cart')
        return 'Your cart has been updated.'
    if name=='checkout':
        if not db.cart(sid): raise ValueError('Your cart is empty.')
        db.navigate(sid,'checkout')
        return 'Ready to check out? Enter your delivery details below.'
    if name=='place_order':
        if db.session(sid)['view']!='checkout':
            raise ValueError('Open checkout before placing an order.')
        allowed=('name','email','zip','address','number','complement','city','state')
        customer={k:text_value(context,k,240) for k in allowed}
        raw_method=context.get('payment',['pix'])
        method=raw_method[0] if isinstance(raw_method,list) and raw_method else str(raw_method)
        coupon=text_value(context,'coupon',40)
        db.navigate(sid,'checkout',draft={**customer,'payment':method,'coupon':coupon})
        oid=db.create_order(sid,customer,method,coupon)
        db.navigate(sid,'payment',oid)
        return f'Order {oid} is ready. Continue to the demo payment.'
    if name=='approve_payment':
        oid=text_value(context,'order_id',100)
        info=db.session(sid)
        if info['view'] not in ('payment','order') or info['arg']!=oid:
            raise ValueError('Open your order before confirming payment.')
        db.approve_demo_payment(oid,sid)
        db.navigate(sid,'order',oid)
        return 'Done! ✅ Your demo payment was confirmed. No real charge was made.'
    if name=='cancel_order':
        oid=text_value(context,'order_id',100)
        db.cancel_demo_order(oid,sid)
        db.navigate(sid,'order',oid)
        return 'Order cancelled and items returned to stock.'
    if name=='order':
        oid=text_value(context,'order_id',100)
        if not db.get_order(oid,sid): raise ValueError('Order not found in this session.')
        db.navigate(sid,'order',oid)
        return 'Here are your order details.'
    raise ValueError('This action is not supported.')


@app.post('/api/action')
async def action(body:ActionIn):
    session_or_422(body.session_id)
    wire=body.message
    if wire.get('version')!='1.0' or not isinstance(wire.get('action'),dict):
        raise HTTPException(status_code=422,detail='Invalid A2UI 1.0 action.')
    event=wire['action']
    surface_id=event.get('surfaceId','')
    component_id=event.get('sourceComponentId','')
    if not isinstance(surface_id,str) or not db.surface_belongs_to(body.session_id,surface_id):
        raise HTTPException(status_code=403,detail='This interface does not belong to your session.')
    context=event.get('context') or {}
    if not isinstance(context,dict) or not isinstance(event.get('name'),str):
        raise HTTPException(status_code=422,detail='Invalid event.')
    name=event['name']
    timestamp=event.get('timestamp')
    try:
        if not isinstance(timestamp, str):
            raise ValueError('Missing timestamp')
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=422, detail='Invalid event.')
    if not db.authorize_surface_action(body.session_id,surface_id,component_id,name,context):
        raise HTTPException(status_code=403,detail='This action is not available in the current interface.')
    if not db.claim_action(body.session_id,surface_id,component_id,timestamp):
        raise HTTPException(status_code=409,detail='This action has already been processed.')
    try:
        confirmed=handle_action(body.session_id,name,context)
        error=''
    except ValueError as exc:
        confirmed=f'Could not complete the action: {exc}'
        error=str(exc)
    db.record_action(body.session_id,name,confirmed)
    reply=confirmed
    via='system'
    if not error and ai_config()['configured']:
        try:
            reply=await reply_after_action(body.session_id,name,confirmed)
            via='pydantic-ai'
        except AIServiceError:
            # The operation already committed: do not pretend it failed or retry it.
            reply=confirmed
    turn=create_assistant(body.session_id,reply,with_ui=True,via=via,error=error)
    return {**meta(body.session_id),'turn':turn,'used_real_ai':via=='pydantic-ai'}



class CartViewIn(BaseModel):
    session_id: str = Field(min_length=1,max_length=80)


@app.post('/api/cart/view')
async def cart_view(body:CartViewIn):
    """A shell navigation event, not an invented user chat message."""
    session_or_422(body.session_id)
    confirmed=handle_action(body.session_id,'cart',{})
    db.record_action(body.session_id,'cart',confirmed)
    reply=confirmed
    via='system'
    if ai_config()['configured']:
        try:
            reply=await reply_after_action(body.session_id,'cart',confirmed)
            via='pydantic-ai'
        except AIServiceError:
            logger.exception('PydanticAI cart follow-up failed')
    turn=create_assistant(body.session_id,reply,with_ui=True,via=via)
    return {**meta(body.session_id),'turn':turn,'used_real_ai':via=='pydantic-ai'}


@app.get('/api/orders/{order_id}')
def order_detail(order_id:str,session_id:str):
    order=db.get_order(order_id,session_id)
    if not order: raise HTTPException(status_code=404,detail='Order not found.')
    return order


@app.get('/api/products')
def products(): return db.get_products()


@app.get('/api/demo-qr/{order_id}')
def qr(order_id:str,session_id:str):
    order=db.get_order(order_id,session_id)
    if not order or order['method']!='pix':
        raise HTTPException(status_code=404,detail='QR code not found.')
    import qrcode
    buffer=io.BytesIO()
    qrcode.make(f'DEMO-SEM-VALOR-{order_id}').save(buffer,format='PNG')
    buffer.seek(0)
    return StreamingResponse(buffer,media_type='image/png',headers={'Cache-Control':'no-store'})


WEB_DIST=Path(__file__).resolve().parents[2]/'frontend'/'dist'
app.mount('/assets',StaticFiles(directory=str(WEB_DIST/'assets'),check_dir=False),name='web-assets')


@app.get('/',include_in_schema=False)
def index():
    path=WEB_DIST/'index.html'
    return FileResponse(path) if path.is_file() else JSONResponse(
        {'detail':'Build the frontend with make start or run make dev.'},status_code=503)
