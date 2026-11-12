import React from 'react';
import { ArrowUpRight, Headphones, Laptop, ShoppingBag, Sparkles } from 'lucide-react';

const suggestions = [
  { label: 'Me ajude a escolher um notebook', icon: Laptop },
  { label: 'Quero um fone de ouvido até R$ 700', icon: Headphones },
  { label: 'Quais produtos vocês têm?', icon: ShoppingBag },
  { label: 'Me surpreenda com uma sugestão', icon: Sparkles },
];

export function WelcomeScreen({ onPrompt, disabled }) {
  return <div className="mx-auto mt-auto mb-auto flex w-full max-w-[570px] flex-col items-start px-2 py-12 sm:py-20">
    <span className="mb-5 flex size-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-700"><Sparkles size={23}/></span>
    <h2 className="max-w-[450px] text-[28px] font-semibold tracking-[-.055em] text-slate-950 sm:text-[34px]">Encontre o que combina com você.</h2>
    <p className="mt-3 max-w-[450px] text-[14px] leading-6 text-slate-500">Me conta o que você procura. Eu te ajudo a comparar opções, escolher e comprar por aqui.</p>
    <div className="mt-8 grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
      {suggestions.map(({ label, icon: Icon }) => <button key={label} type="button" disabled={disabled} onClick={() => onPrompt(label)}
        className="group flex min-h-14 items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3.5 py-3 text-left text-[12px] font-medium text-slate-700 shadow-[0_2px_12px_rgba(15,23,42,.02)] transition hover:border-blue-300 hover:shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-40">
        <Icon size={17} className="shrink-0 text-blue-700"/><span className="flex-1">{label}</span><ArrowUpRight size={14} className="text-slate-400 group-hover:text-blue-700"/>
      </button>)}
    </div>
  </div>;
}
