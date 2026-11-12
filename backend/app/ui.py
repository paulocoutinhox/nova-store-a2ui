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
        return self.node('ChoicePicker',label='Como deseja pagar?',
            options=[{'label':'Pix','value':'pix'},{'label':'Cartão teste','value':'card'},{'label':'Boleto teste','value':'boleto'}],
            value={'@path':'/form/payment'},variant='mutuallyExclusive',displayStyle='chips')

    def product_row(self,p):
        return self.card(
            self.row(self.image(p['image'],p['name']),self.column(
                self.text(f'**{escape(p["name"])}**'),
                self.text(escape(p['specs']),'caption'),
                self.text(f'**{brl(p["price_cents"])}**'),
            )),
            self.row(self.button('Detalhes','product',{'id':p['id']}),
                     self.button('Adicionar','add',{'id':p['id']},True)),
        )

    def products(self,products,empty='Nenhum produto disponível.'):
        if not products:
            return self.column(self.text(empty),self.button('Ver todos','home'))
        visible=products[:3]
        parts=[self.product_row(p) for p in visible]
        if len(products)>3:
            parts.append(self.text(f'Mostrando 3 de {len(products)} produtos. Peça para filtrar ou ver detalhes.','caption'))
        return self.column(*parts)

    def categories(self):
        cats=db.categories()
        return self.column(self.text('Escolha uma categoria:'),
            *(self.button(f'{c["name"]} ({c["count"]})','category',{'category':c['name']}) for c in cats))

    def product_detail(self,p):
        if not p: return self.text('Produto não encontrado.')
        return self.card(self.row(self.image(p['image'],p['name']),self.column(
            self.text(f'**{escape(p["name"])}**'),
            self.text(escape(p['description'])),
            self.text(escape(p['specs']),'caption'),
            self.text(f'**{brl(p["price_cents"])}**'),
            self.text(f'{p["stock"]} disponíveis','caption'))),
            self.row(self.button('Adicionar ao carrinho','add',{'id':p['id']},True),
                     self.button('Comprar agora','buy_now',{'id':p['id']})))

    def compare(self,ids):
        cards=[]
        for pid in ids[:3]:
            p=db.get_product(pid)
            if p: cards.append(self.product_detail(p))
        return self.column(self.text('Comparação de produtos'),*cards)

    def cart(self,sid):
        q=db.quote(sid)
        if not q['items']:
            return self.column(self.text('Seu carrinho está vazio.'),self.button('Ver produtos','home',primary=True))
        rows=[]
        for item in q['items']:
            rows.append(self.card(
                self.row(self.image(item['image'],item['name']),self.column(
                    self.text(f'**{escape(item["name"])}**'),
                    self.text(f'{item["qty"]} × {brl(item["price_cents"])}'),
                    self.text(f'Subtotal {brl(item["price_cents"]*item["qty"])}','caption'))),
                self.row(self.button('−','set_qty',{'id':item['id'],'qty':item['qty']-1}),
                         self.text(str(item['qty'])),
                         self.button('+','set_qty',{'id':item['id'],'qty':item['qty']+1}),
                         self.button('Remover','set_qty',{'id':item['id'],'qty':0}))
            ))
        return self.column(*rows,
            self.card(self.text(f'Subtotal: {brl(q["subtotal_cents"])}'),
                      self.text(f'Frete: {brl(q["shipping_cents"])}'),
                      self.text(f'**Total: {brl(q["total_cents"])}**'),
                      self.button('Finalizar compra','checkout',primary=True)))

    def checkout(self,sid,draft=None,error=''):
        draft=draft or {}
        q=db.quote(sid,draft.get('coupon',''))
        if not q['items']: return self.cart(sid)
        entries=[('name','Nome completo','Seu nome'),('email','E-mail','nome@exemplo.com'),
                 ('zip','CEP','00000-000'),('address','Endereço','Rua / Avenida'),
                 ('number','Número','Número'),('complement','Complemento (opcional)','Apartamento etc.'),
                 ('city','Cidade','Cidade'),('state','UF','RJ'),('coupon','Cupom (opcional)','BEMVINDO10')]
        fields=[self.textfield(label,key,draft.get(key,''),hint) for key,label,hint in entries]
        context={key:{'@path':f'/form/{key}'} for key,_,_ in entries}
        context['payment']={'@path':'/form/payment'}
        return self.column(
            self.text('**Finalizar pedido**'),
            self.text(f'{len(q["items"])} produto(s) • Total estimado {brl(q["total_cents"])}','caption'),
            self.text('Informe os dados de entrega para continuar.','caption'),
            self.text(f'⚠ {escape(error)}') if error else None,
            self.card(fields[0],fields[1],fields[2],
                      self.row(fields[3],fields[4]),fields[5],
                      self.row(fields[6],fields[7]),fields[8],
                      self.payment_choice(draft.get('payment','pix')),
                      self.button('Continuar com pedido','place_order',context,True)),
            self.text('Ambiente de testes: nenhuma cobrança será feita.','caption')
        )

    def payment(self,order):
        if not order: return self.text('Pedido não encontrado.')
        if order['status']=='paid': return self.completed(order)
        if order['status']=='cancelled': return self.cancelled(order)
        method=order['method']
        if method=='pix':
            msg='Pix de demonstração: este QR Code não recebe pagamentos.'
            img=self.image(f'/api/demo-qr/{order["id"]}?session_id={order["session_id"]}','QR Code de teste')
        elif method=='card':
            msg='Pagamento demonstrativo. Nenhum número de cartão é necessário.'
            img=None
        else:
            msg='Boleto de demonstração, sem valor bancário.'
            img=None
        return self.card(self.text(f'**Pedido {order["id"]}**'),
            self.text(f'**Total: {brl(order["total_cents"])}**'),self.text(msg),img,
            self.button('Confirmar pagamento de teste','approve_payment',{'order_id':order['id']},True),
            self.button('Cancelar pedido','cancel_order',{'order_id':order['id']}))

    def completed(self,order):
        return self.card(self.text('**Pagamento confirmado**'),
            self.text(f'Pedido: {order["id"]}'),self.text(f'Total: {brl(order["total_cents"])}'),
            self.text('Pedido registrado. Nenhuma cobrança real ocorreu.','caption'),
            self.button('Ver meus pedidos','orders',primary=True))

    def cancelled(self,order):
        return self.card(self.text('**Pedido cancelado**'),
            self.text(f'Pedido {order["id"]} · estoque devolvido'),
            self.button('Continuar comprando','home',primary=True))

    def orders(self,sid):
        found=db.get_orders(sid)
        if not found:
            return self.column(self.text('Você ainda não possui pedidos.'),self.button('Ver produtos','home'))
        labels={'paid':'Pago','pending':'Aguardando pagamento','cancelled':'Cancelado'}
        return self.column(*(self.card(self.text(f'**{order["id"]}**'),
            self.text(f'{brl(order["total_cents"])} · {labels.get(order["status"], order["status"])}'),
            self.button('Detalhes','order',{'order_id':order['id']})) for order in found[:8]))


def render(sid,surface_id,error=''):
    """Produce a SINGLE official A2UI 1.0 createSurface message for this chat turn."""
    info=db.session(sid)
    if not info: return []
    view=info['view']; arg=info['arg']; u=UI()
    if view=='home':
        content=u.column(u.text('Algumas sugestões para começar:'),
                         u.products(db.get_products(limit=3)),
                         u.button('Explorar categorias','categories'))
    elif view=='categories': content=u.categories()
    elif view=='category': content=u.column(u.text(f'Categoria {escape(arg)}'),u.products(db.get_products(category=arg)))
    elif view=='search':
        try: spec=json.loads(arg)
        except (ValueError,TypeError): spec={'query':arg}
        items=db.get_products(category=spec.get('category'),query=spec.get('query'),max_cents=spec.get('max_cents'))
        content=u.products(items,'Não encontrei resultados no catálogo para esses filtros.')
    elif view=='product': content=u.product_detail(db.get_product(arg))
    elif view=='compare': content=u.compare(arg.split(','))
    elif view=='cart': content=u.cart(sid)
    elif view=='checkout': content=u.checkout(sid,json.loads(info['draft_json']),error)
    elif view in ('payment','order'):
        order=db.get_order(arg,sid)
        content=u.payment(order) if order else u.orders(sid)
    elif view=='orders': content=u.orders(sid)
    else: content=u.text('O que você procura hoje?')
    u.nodes.append({'id':'root','component':'Column','children':[content]})
    return [{'version':'1.0','createSurface':{
        'surfaceId':surface_id,'catalogId':CATALOG_ID,'components':u.nodes,'dataModel':u.data,
    }}]
