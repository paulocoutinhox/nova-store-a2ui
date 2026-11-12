import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ChatComposer } from './components/chat-composer.jsx';
import { ChatHeader } from './components/chat-header.jsx';
import { ChatMessage } from './components/chat-message.jsx';
import { WelcomeScreen } from './components/welcome-screen.jsx';
import './styles.css';

const KEY = 'nova-shop-session-v4';
const localTurn = (role, content) => ({ id: crypto.randomUUID(), role, content, created_at: new Date().toISOString() });

async function request(path, payload) {
  let response;
  try {
    response = await fetch(`/api/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  } catch {
    throw new Error('Não foi possível conectar à loja. Tente novamente.');
  }
  if (!response.ok) {
    let message = 'Não foi possível concluir sua solicitação. Tente novamente.';
    try { const error = await response.json(); if (typeof error.detail === 'string') message = error.detail; } catch { /* Keep generic user-facing error. */ }
    throw new Error(message);
  }
  return response.json();
}

function App() {
  const [id, setId] = useState('');
  const session = useRef('');
  const [turns, setTurns] = useState([]);
  const [input, setInput] = useState('');
  const [cartCount, setCartCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState('');
  const scrolling = useRef(null);
  const generation = useRef(0);

  const loadSession = useCallback(async (restore = true) => {
    if (lock.current) return;
    const sequence = ++generation.current;
    lock.current = true; setBusy(true); setLoading(true); setNotice('');
    try {
      const data = await request('session', { session_id: restore ? localStorage.getItem(KEY) || undefined : undefined });
      if (sequence !== generation.current) return;
      session.current = data.session_id; setId(data.session_id);
      localStorage.setItem(KEY, data.session_id);
      setTurns(data.history || []); setCartCount(data.cart_count || 0);
    } catch (err) {
      if (sequence === generation.current) { setNotice(err.message); session.current = ''; setId(''); }
    } finally {
      if (sequence === generation.current) { lock.current = false; setBusy(false); setLoading(false); }
    }
  }, []);

  useEffect(() => { loadSession(); }, [loadSession]);
  useLayoutEffect(() => { if (scrolling.current) scrolling.current.scrollTop = scrolling.current.scrollHeight; }, [turns.length, busy]);

  const send = useCallback(async message => {
    const text = String(message || '').trim();
    if (!text || !session.current || lock.current) return;
    setNotice(''); setInput('');
    setTurns(list => [...list, localTurn('user', text)]);
    lock.current = true; setBusy(true);
    try {
      const result = await request('message', { session_id: session.current, text });
      setCartCount(result.cart_count || 0);
      setTurns(list => [...list, result.turn]);
    } catch (err) {
      setInput(text);
      setTurns(list => [...list, localTurn('error', err.message)]);
    } finally { lock.current = false; setBusy(false); }
  }, []);

  const action = useCallback(async event => {
    if (lock.current || !session.current) return;
    lock.current = true; setBusy(true); setNotice('');
    try {
      const data = await request('action', { session_id: session.current, message: event });
      setCartCount(data.cart_count || 0);
      // A2UI actions are *not* user-written chat messages.
      setTurns(list => [...list, data.turn]);
    } catch (err) { setNotice(err.message); }
    finally { lock.current = false; setBusy(false); }
  }, []);

  const newChat = () => { if (!lock.current) { localStorage.removeItem(KEY); loadSession(false); } };
  const openCart = useCallback(async () => {
    if (lock.current || !session.current) return;
    lock.current = true; setBusy(true); setNotice('');
    try {
      const data = await request('cart/view', { session_id: session.current });
      setCartCount(data.cart_count || 0);
      setTurns(list => [...list, data.turn]);
    } catch (error) { setNotice(error.message); }
    finally { lock.current = false; setBusy(false); }
  }, []);
  const visible = turns.filter(turn => turn.via !== 'welcome');

  return <div className="flex h-dvh min-h-[450px] flex-col bg-slate-50 text-slate-900" data-theme="nova">
    <ChatHeader cartCount={cartCount} onCart={openCart} onNewChat={newChat} busy={busy || loading}/>
    <main ref={scrolling} className="chat-scroll flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain" aria-label="Conversa com a loja">
      <div className="mx-auto flex w-full max-w-[920px] flex-1 flex-col gap-5 px-4 pb-9 pt-7 sm:px-7 sm:pt-9">
        {notice && <div role="alert" className="alert alert-error mx-auto w-full max-w-[640px] rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-800 shadow-none">{notice}</div>}
        {!loading && visible.length === 0 && <WelcomeScreen onPrompt={send} disabled={busy || !id}/>}
        {visible.map(turn => <ChatMessage key={turn.id} turn={turn} onAction={action} disabled={busy}/>)}
        {loading && <p className="py-10 text-center text-sm text-slate-500">Abrindo conversa...</p>}
        {busy && !loading && <div aria-label="Assistente escrevendo" className="flex gap-2.5"><span className="flex size-8 items-center justify-center rounded-xl bg-slate-900 text-white">•</span><div className="flex items-center gap-1 rounded-2xl border border-slate-200 bg-white px-4 py-2"><span className="typing-dot"/><span className="typing-dot"/><span className="typing-dot"/></div></div>}
      </div>
    </main>
    <ChatComposer value={input} onChange={setInput} onSend={send} disabled={!id || busy || loading}/>
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
