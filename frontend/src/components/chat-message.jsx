import React from 'react';
import { CheckCheck, ShoppingBag } from 'lucide-react';
import { A2UISurface } from './a2ui-surface.jsx';

function formatClock(value) {
  const time = new Date(value || Date.now());
  return Number.isNaN(time.getTime()) ? '' : time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

export function ChatMessage({ turn, onAction, disabled }) {
  const own = turn.role === 'user';
  const error = turn.role === 'error';
  const isSystem = turn.via === 'system';
  const surface = Array.isArray(turn.a2ui) && turn.a2ui.length > 0;

  if (isSystem) return <div className="ml-10 w-full max-w-[600px] min-w-0">
    {turn.content && <div role="status" className="mb-2 rounded-xl bg-slate-100 px-3 py-2 text-xs leading-5 text-slate-600">{turn.content}</div>}
    {surface && <A2UISurface messages={turn.a2ui} onAction={onAction} disabled={disabled}/>}
  </div>;
  return <div className={`flex w-full ${own ? 'justify-end' : 'justify-start'} gap-2.5`}>
    {!own && <div aria-hidden="true" className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white"><ShoppingBag size={15}/></div>}
    <div className={`min-w-0 ${surface ? 'w-full max-w-[600px]' : 'max-w-[min(570px,88%)]'}`}>
      <div className={`min-w-0 rounded-[20px] px-4 py-3 ${own
        ? 'rounded-br-[6px] bg-blue-700 text-white shadow-[0_2px_8px_rgba(29,78,216,.12)]'
        : error
          ? 'rounded-bl-[6px] border border-red-200 bg-red-50 text-red-800'
          : 'rounded-bl-[6px] border border-slate-200 bg-white text-slate-800 shadow-[0_2px_10px_rgba(15,23,42,.025)]'}`}>
        {turn.content && <p className="whitespace-pre-wrap break-words text-[13.5px] leading-[1.7] sm:text-[14px]">{turn.content}</p>}
        {surface && <A2UISurface messages={turn.a2ui} onAction={onAction} disabled={disabled}/>}
        <div className={`mt-2 flex items-center justify-end gap-1 text-[10px] ${own ? 'text-blue-100' : 'text-slate-400'}`}><time>{formatClock(turn.created_at)}</time>{own && <CheckCheck size={14}/>}</div>
      </div>
    </div>
  </div>;
}
