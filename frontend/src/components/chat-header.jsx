import React from 'react';
import { Plus, ShoppingBag } from 'lucide-react';

export function ChatHeader({ cartCount, onNewChat, onCart, busy }) {
  return <header className="z-10 shrink-0 border-b border-slate-200/90 bg-white/95 px-4 py-3 backdrop-blur-xl sm:px-7">
    <div className="mx-auto flex h-11 w-full max-w-[920px] items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-[0_4px_12px_rgba(15,23,42,.12)]"><ShoppingBag size={21} strokeWidth={1.8}/></div>
        <div className="min-w-0">
          <h1 className="text-[15px] font-bold tracking-[-.035em] text-slate-950">nova<span className="text-blue-600">.</span></h1>
          <p className="text-[11px] text-slate-500">Your shopping assistant</p>
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <button type="button" className="btn btn-ghost btn-square btn-sm size-10 rounded-xl text-slate-600 hover:bg-slate-100" onClick={onNewChat} title="New conversation" aria-label="New conversation" disabled={busy}><Plus size={19}/></button>
        <button type="button" className="btn btn-ghost btn-square btn-sm relative size-10 rounded-xl text-slate-600 hover:bg-slate-100" onClick={onCart} title="Cart" aria-label="View cart" disabled={busy}>
          <ShoppingBag size={19}/>{cartCount > 0 && <span className="absolute -right-0.5 -top-0.5 flex min-h-5 min-w-5 items-center justify-center rounded-full bg-blue-700 px-1 text-[10px] font-bold text-white">{cartCount}</span>}
        </button>
      </div>
    </div>
  </header>;
}
