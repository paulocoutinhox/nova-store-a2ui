import React, { useRef } from 'react';
import { ArrowUp } from 'lucide-react';

export function ChatComposer({ value, onChange, onSend, disabled }) {
  const ref = useRef(null);
  const submit = event => { event.preventDefault(); onSend(value); if (ref.current) ref.current.style.height = 'auto'; };
  return <footer className="shrink-0 border-t border-slate-200 bg-white px-3 pb-[max(14px,env(safe-area-inset-bottom))] pt-3 sm:px-6 sm:pb-5">
    <form onSubmit={submit} className="mx-auto flex w-full max-w-[830px] items-end gap-3 rounded-2xl border border-slate-300 bg-white p-[7px] pl-4 shadow-[0_2px_20px_rgba(15,23,42,.055)] transition focus-within:border-blue-500 focus-within:ring-[3px] focus-within:ring-blue-100">
      <textarea ref={ref} value={value} onChange={e => onChange(e.target.value)} rows={1} maxLength={1200} disabled={disabled}
        onInput={e => { e.currentTarget.style.height = 'auto'; e.currentTarget.style.height = `${Math.min(e.currentTarget.scrollHeight, 138)}px`; }}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); onSend(value); if (ref.current) ref.current.style.height = 'auto'; } }}
        className="max-h-[138px] min-h-[43px] min-w-0 flex-1 resize-none border-0 bg-transparent py-[11px] text-[14px] leading-[1.5] text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60"
        placeholder="What are you looking for?" aria-label="Type a message"/>
      <button type="submit" disabled={!value.trim() || disabled} aria-label="Send message" className="btn btn-square flex size-10 min-h-10 shrink-0 items-center justify-center rounded-xl border-blue-700 bg-blue-700 text-white hover:border-blue-800 hover:bg-blue-800 disabled:border-slate-100 disabled:bg-slate-100 disabled:text-slate-400"><ArrowUp size={20}/></button>
    </form>
  </footer>;
}
