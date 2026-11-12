import React, { useMemo, useState } from 'react';
import { ArrowRight, ShoppingCart } from 'lucide-react';
import { buildAction, getPath, parseA2UI, setPath } from '../lib/a2ui.js';

function RichText({ value }) {
  const text = String(value ?? '');
  const chunks = text.split(/(\*\*[^*]+\*\*)/g);
  return <>{chunks.map((chunk, i) => chunk.startsWith('**') && chunk.endsWith('**')
    ? <strong key={i} className="font-semibold text-slate-900">{chunk.slice(2, -2)}</strong>
    : <React.Fragment key={i}>{chunk}</React.Fragment>)}</>;
}

function Widget({ id, surface, data, setData, onAction, disabled, depth = 0 }) {
  if (depth > 24) return null;
  const node = surface.components.get(id);
  if (!node) return null;
  const children = (ids) => (ids || []).map(childId =>
    <Widget key={childId} id={childId} surface={surface} data={data} setData={setData} onAction={onAction} disabled={disabled} depth={depth + 1} />);
  switch (node.component) {
    case 'Column':
      return <div className="flex min-w-0 flex-col gap-3">{children(node.children)}</div>;
    case 'Row': {
      const formRow = (node.children || []).every(childId => surface.components.get(childId)?.component === 'TextField');
      return <div className={formRow ? 'grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2' : 'flex min-w-0 flex-wrap items-center gap-3'}>{children(node.children)}</div>;
    }
    case 'Card':
      return <section className="w-full min-w-0 rounded-2xl border border-slate-200 bg-white p-3.5 shadow-[0_2px_8px_rgba(15,23,42,.025)] sm:p-4">
        <Widget id={node.child} surface={surface} data={data} setData={setData} onAction={onAction} disabled={disabled} depth={depth + 1} />
      </section>;
    case 'Text':
      return <p className={`${node.variant === 'caption' ? 'text-[12px] leading-5 text-slate-500' : 'text-[13px] leading-[1.55] text-slate-700'} min-w-0 break-words`}>
        <RichText value={node.text}/>
      </p>;
    case 'Image': {
      const isQR = typeof node.url === 'string' && node.url.includes('/api/demo-qr/');
      return <img src={node.url} alt={node.description || 'Product'} loading="lazy"
        className={`${isQR ? 'h-40 w-40 object-contain' : 'h-[84px] w-[84px] object-cover'} shrink-0 rounded-xl border border-slate-100 bg-[#f7f7f7]`}/>;
    }
    case 'Button': {
      const titleNode = surface.components.get(node.child);
      const label = titleNode?.text || 'Continue';
      const primary = node.variant === 'primary';
      return <button type="button" disabled={disabled} onClick={() => onAction(buildAction(surface.id, id, node.action?.event, data))}
        className={`btn btn-sm h-9 min-h-9 rounded-xl px-3.5 text-[12px] font-semibold normal-case shadow-none transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${primary
          ? 'border-blue-700 bg-blue-700 text-white hover:border-blue-800 hover:bg-blue-800 disabled:border-blue-200 disabled:bg-blue-200 disabled:text-slate-500'
          : 'border-slate-200 bg-white text-slate-800 hover:border-blue-200 hover:bg-blue-50 disabled:bg-slate-50 disabled:text-slate-400'}`}>
        {label === 'Add +' && <ShoppingCart size={14}/>}<RichText value={label}/>{primary && label === 'Checkout' && <ArrowRight size={14}/>}
      </button>;
    }
    case 'TextField': {
      const pointer = node.value?.['@path'];
      const value = getPath(data, pointer) ?? '';
      const type = /email|e-mail/i.test(node.label) ? 'email' : 'text';
      return <label className="form-control flex w-full min-w-0 flex-col gap-1.5">
        <span className="text-[12px] font-medium text-slate-700">{node.label}</span>
        <input className="input input-bordered h-10 min-h-10 w-full rounded-xl border-slate-300 bg-white px-3 text-[13px] text-slate-900 placeholder:text-slate-400 focus:border-blue-600 focus:outline-2 focus:outline-blue-100"
          name={pointer} type={type} autoComplete="off" value={value} placeholder={node.placeholder || ''}
          onChange={event => setData(prev => setPath(prev, pointer, event.target.value))} disabled={disabled}/>
      </label>;
    }
    case 'ChoicePicker': {
      const pointer = node.value?.['@path'];
      const value = getPath(data, pointer) || [];
      return <fieldset className="flex w-full min-w-0 flex-col gap-2">
        <legend className="mb-2 text-[12px] font-medium text-slate-700">{node.label}</legend>
        <div className="flex flex-wrap gap-2">
          {(node.options || []).map(option => {
            const selected = value.includes(option.value);
            return <label key={option.value} className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-[12px] font-medium transition ${selected ? 'border-blue-600 bg-blue-50 text-blue-800' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-400'}`}>
              <input type="radio" name={`${surface.id}-${id}`} value={option.value} checked={selected} disabled={disabled}
                className="radio radio-xs border-slate-400 text-blue-700" onChange={() => setData(prev => setPath(prev, pointer, [option.value]))}/>
              {option.label}
            </label>;
          })}
        </div>
      </fieldset>;
    }
    default:
      return null;
  }
}

function RenderedSurface({ surface, onAction, disabled }) {
  const [data, setData] = useState(surface.data || {});
  return <div className="a2ui-content min-w-0" aria-label="Shopping options">
    <Widget id="root" surface={surface} data={data} setData={setData} onAction={onAction} disabled={disabled}/>
  </div>;
}

export function A2UISurface({ messages, onAction, disabled = false }) {
  const { surfaces, error } = useMemo(() => {
    try { return { surfaces: parseA2UI(messages), error: '' }; }
    catch (err) { return { surfaces: [], error: err.message }; }
  }, [messages]);
  if (error) return <p role="alert" className="text-sm text-rose-700">Shopping options could not be loaded.</p>;
  return <div className="mt-3 flex min-w-0 flex-col gap-3">{surfaces.map(surface =>
    <RenderedSurface key={surface.id} surface={surface} onAction={onAction} disabled={disabled}/>)}</div>;
}
