"""Compact A2UI 1.0 Basic Catalog surfaces embedded in assistant chat bubbles.

These are REAL A2UI JSON envelopes, not HTML pretending to be A2UI.
Each message gets its own immutable surface id for chat history and replay.
"""
from __future__ import annotations

import json
import re
from . import db

CATALOG_ID = 'https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json'


def brl(cents: int) -> str:
    return f'R$ {cents / 100:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def escape(value):
    return re.sub(r'([\\`*_{}\[\]<>!])', r'\\\1', str(value))


class UI:
    def __init__(self):
        self.nodes=[]
        self.n=0
        self.data={'form':{}}

    def node(self, kind, **props):
        self.n+=1
        name=f'c{self.n}'
        self.nodes.append({'id':name,'component':kind,**props})
        return name

    def text(self, text, variant='body'):
        return self.node('Text', text=str(text), variant=variant)

    def column(self,*items):
        return self.node('Column',children=[v for v in items if v])

    def row(self,*items):
        return self.node('Row',children=[v for v in items if v],align='center')

    def card(self,*items):
        return self.node('Card',child=self.column(*items))

    def button(self,label,event,context=None,primary=False):
        return self.node('Button',child=self.text(label),variant='primary' if primary else 'default',
            action={'event':{'name':event,'context':context or {}}})

    def image(self,url,name):
        return self.node('Image',url=url,description=name,variant='smallFeature',fit='contain')

    def textfield(self,label,key,initial='',placeholder=''):
        self.data['form'][key]=initial
        return self.node('TextField',label=label,value={'@path':f'/form/{key}'},placeholder=placeholder,variant='shortText')

    def payment_choice(self,method='pix'):
        self.data['form']['payment']=[method]
        return self.node('ChoicePicker',label='How would you like to pay?',
            options=[{'label':'Pix','value':'pix'},{'label':'Test card','value':'card'},{'label':'Test bank slip','value':'boleto'}],
            value={'@path':'/form/payment'},variant='mutuallyExclusive',displayStyle='chips')

    def product_row(self,p):
        return self.card(
            self.row(self.image(p['image'],p['name']),self.column(
                self.text(f'**{escape(p["name"])}**'),
                self.text(escape(p['specs']),'caption'),
                self.text(f'**{brl(p["price_cents"])}**'),
            )),
            self.row(self.button('Details','product',{'id':p['id']}),
                     self.button('Add to cart','add',{'id':p['id']},True)),
        )

    def products(self,products,empty='No products available.'):
        if not products:
            return self.column(self.text(empty),self.button('Browse products','home'))
        visible=products[:3]
        parts=[self.product_row(p) for p in visible]
        if len(products)>3:
            parts.append(self.text(f'Showing 3 of {len(products)} products. Ask me to narrow your search or see details.','caption'))
        return self.column(*parts)

    def categories(self):
        cats=db.categories()
        return self.column(self.text('Choose a category:'),
            *(self.button(f'{c["name"]} ({c["count"]})','category',{'category':c['name']}) for c in cats))

    def product_detail(self,p):
        if not p: return self.text('Product not found.')
        return self.card(self.row(self.image(p['image'],p['name']),self.column(
            self.text(f'**{escape(p["name"])}**'),
            self.text(escape(p['description'])),
            self.text(escape(p['specs']),'caption'),
            self.text(f'**{brl(p["price_cents"])}**'),
            self.text(f'{p["stock"]} available','caption'))),
            self.row(self.button('Add to cart','add',{'id':p['id']},True),
                     self.button('Buy now','buy_now',{'id':p['id']})))

    def compare(self,ids):
        cards=[]
        for pid in ids[:3]:
            p=db.get_product(pid)
            if p: cards.append(self.product_detail(p))
        return self.column(self.text('Product comparison'),*cards)

    def cart(self,sid):
        q=db.quote(sid)
        if not q['items']:
            return self.column(self.text('Your cart is empty.'),self.button('Browse products','home',primary=True))
        rows=[]
        for item in q['items']:
            rows.append(self.card(
                self.row(self.image(item['image'],item['name']),self.column(
                    self.text(f'**{escape(item["name"])}**'),
                    self.text(f'{item["qty"]} × {brl(item["price_cents"])}'),
                    self.text(f'Item total: {brl(item["price_cents"]*item["qty"])}','caption'))),
                self.row(self.button('−','set_qty',{'id':item['id'],'qty':item['qty']-1}),
                         self.text(str(item['qty'])),
                         self.button('+','set_qty',{'id':item['id'],'qty':item['qty']+1}),
                         self.button('Remove','set_qty',{'id':item['id'],'qty':0}))
            ))
        return self.column(*rows,
            self.card(self.text(f'Subtotal: {brl(q["subtotal_cents"])}'),
                      self.text(f'Shipping: {brl(q["shipping_cents"])}'),
                      self.text(f'**Total: {brl(q["total_cents"])}**'),
                      self.button('Checkout','checkout',primary=True)))

    def checkout(self,sid,draft=None,error=''):
        draft=draft or {}
        q=db.quote(sid,draft.get('coupon',''))
        if not q['items']: return self.cart(sid)
        entries=[('name','Full name','Your name'),('email','Email','name@example.com'),
                 ('zip','Postal code','00000-000'),('address','Street address','Street name and address'),
                 ('number','Street number','Street number'),('complement','Apartment / suite (optional)','Apartment, suite, etc.'),
                 ('city','City','City'),('state','State','RJ'),('coupon','Coupon (optional)','BEMVINDO10')]
        fields=[self.textfield(label,key,draft.get(key,''),hint) for key,label,hint in entries]
        context={key:{'@path':f'/form/{key}'} for key,_,_ in entries}
        context['payment']={'@path':'/form/payment'}
        return self.column(
            self.text('**Complete your order**'),
            self.text(f'{len(q["items"])} produto(s) • Total estimado {brl(q["total_cents"])}','caption'),
            self.text('Enter your delivery details to continue.','caption'),
            self.text(f'⚠ {escape(error)}') if error else None,
            self.card(fields[0],fields[1],fields[2],
                      self.row(fields[3],fields[4]),fields[5],
                      self.row(fields[6],fields[7]),fields[8],
                      self.payment_choice(draft.get('payment','pix')),
                      self.button('Place order','place_order',context,True)),
            self.text('Demo checkout: no real charge will be made.','caption')
        )

    def payment(self,order):
        if not order: return self.text('Order not found.')
        if order['status']=='paid': return self.completed(order)
        if order['status']=='cancelled': return self.cancelled(order)
        method=order['method']
        if method=='pix':
            msg='Demo Pix: this QR code cannot accept payments.'
            img=self.image(f'/api/demo-qr/{order["id"]}?session_id={order["session_id"]}','Demo QR code')
        elif method=='card':
            msg='Demo payment: no card number is required.'
            img=None
        else:
            msg='Demo bank slip: no bank payment is required.'
            img=None
        return self.card(self.text(f'**Order {order["id"]}**'),
            self.text(f'**Total: {brl(order["total_cents"])}**'),self.text(msg),img,
            self.button('Confirm demo payment','approve_payment',{'order_id':order['id']},True),
            self.button('Cancel order','cancel_order',{'order_id':order['id']}))

    def completed(self,order):
        return self.card(self.text('**Payment confirmed**'),
            self.text(f'Order: {order["id"]}'),self.text(f'Total: {brl(order["total_cents"])}'),
            self.text('Order recorded. No real payment was processed.','caption'),
            self.button('View my orders','orders',primary=True))

    def cancelled(self,order):
        return self.card(self.text('**Order cancelled**'),
            self.text(f'Order {order["id"]} · items returned to stock'),
            self.button('Keep shopping','home',primary=True))

    def orders(self,sid):
        found=db.get_orders(sid)
        if not found:
            return self.column(self.text('You have no orders yet.'),self.button('Browse products','home'))
        labels={'paid':'Paid','pending':'Pending payment','cancelled':'Cancelled'}
        return self.column(*(self.card(self.text(f'**{order["id"]}**'),
            self.text(f'{brl(order["total_cents"])} · {labels.get(order["status"], order["status"])}'),
            self.button('Details','order',{'order_id':order['id']})) for order in found[:8]))


def render(sid,surface_id,error=''):
    """Produce a SINGLE official A2UI 1.0 createSurface message for this chat turn."""
    info=db.session(sid)
    if not info: return []
    view=info['view']; arg=info['arg']; u=UI()
    if view=='home':
        content=u.column(u.text('A few ideas to get started:'),
                         u.products(db.get_products(limit=3)),
                         u.button('Browse categories','categories'))
    elif view=='categories': content=u.categories()
    elif view=='category': content=u.column(u.text(f'Category: {escape(arg)}'),u.products(db.get_products(category=arg)))
    elif view=='search':
        try: spec=json.loads(arg)
        except (ValueError,TypeError): spec={'query':arg}
        items=db.get_products(category=spec.get('category'),query=spec.get('query'),max_cents=spec.get('max_cents'))
        content=u.products(items,'No matching products found. Try another search.')
    elif view=='product': content=u.product_detail(db.get_product(arg))
    elif view=='compare': content=u.compare(arg.split(','))
    elif view=='cart': content=u.cart(sid)
    elif view=='checkout': content=u.checkout(sid,json.loads(info['draft_json']),error)
    elif view in ('payment','order'):
        order=db.get_order(arg,sid)
        content=u.payment(order) if order else u.orders(sid)
    elif view=='orders': content=u.orders(sid)
    else: content=u.text('What are you shopping for today?')
    u.nodes.append({'id':'root','component':'Column','children':[content]})
    return [{'version':'1.0','createSurface':{
        'surfaceId':surface_id,'catalogId':CATALOG_ID,'components':u.nodes,'dataModel':u.data,
    }}]
