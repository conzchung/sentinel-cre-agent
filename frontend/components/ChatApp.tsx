'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Sidebar from './Sidebar';
import UserMessage from './UserMessage';
import AssistantTurn from './AssistantTurn';
import Suggestions from './Suggestions';
import Composer from './Composer';
import { useChat } from './useChat';

const SIDEBAR_KEY = 'sentinel.sidebarCollapsed';
const WIDTH_KEY = 'sentinel.sidebarWidth';
const MIN_W = 200;
const MAX_W = 460;
const DEFAULT_W = 264;

export default function ChatApp({ user }: { user: string }) {
  const chat = useChat();
  const endRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<HTMLDivElement>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_W);

  // Restore the collapse + width preferences once on mount (client-only; avoids
  // an SSR hydration mismatch by starting at defaults and correcting after).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (localStorage.getItem(SIDEBAR_KEY) === '1') setSidebarCollapsed(true);
    const w = Number(localStorage.getItem(WIDTH_KEY));
    if (w >= MIN_W && w <= MAX_W) setSidebarWidth(w);
  }, []);

  // Plotly only re-fits on a WINDOW resize (not a container one), so after the
  // grid relayouts we nudge it once on the next frame to re-fit at the new
  // width — a single relayout, not one per animation frame.
  const refitCharts = useCallback(() => {
    if (typeof window === 'undefined') return;
    requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((c) => {
      const next = !c;
      if (typeof window !== 'undefined') localStorage.setItem(SIDEBAR_KEY, next ? '1' : '0');
      return next;
    });
    refitCharts();
  }, [refitCharts]);

  // Drag-to-resize. We mutate the CSS variable straight on the DOM during the
  // drag so the grid reflows WITHOUT a React re-render per pointer move, then
  // commit the final width to state + localStorage on release. The .is-dragging
  // class suppresses text selection and any width transition while dragging.
  const startResize = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    const app = appRef.current;
    if (!app) return;
    app.classList.add('is-dragging');

    const onMove = (ev: PointerEvent) => {
      const w = Math.min(MAX_W, Math.max(MIN_W, ev.clientX));
      app.style.setProperty('--side-w', `${w}px`);
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      app.classList.remove('is-dragging');
      const finalW = Math.min(
        MAX_W,
        Math.max(MIN_W, parseInt(app.style.getPropertyValue('--side-w'), 10) || DEFAULT_W),
      );
      setSidebarWidth(finalW);
      if (typeof window !== 'undefined') localStorage.setItem(WIDTH_KEY, String(finalW));
      refitCharts();
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [refitCharts]);

  // ⌘\ (macOS) / Ctrl+\ (Windows/Linux) toggles the sidebar — the de facto
  // shortcut for this in chat apps.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
        e.preventDefault();
        toggleSidebar();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [toggleSidebar]);

  useEffect(() => {
    chat.refreshConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat.turns, chat.liveTurn]);

  // Suggestions sit above the composer and only show for the most recent
  // assistant turn, once streaming has finished (i.e. before the next send).
  const lastTurn = chat.turns[chat.turns.length - 1];
  const dockSuggestions =
    !chat.streaming && lastTurn?.role === 'assistant' ? lastTurn.suggestions : [];

  return (
    <div
      ref={appRef}
      className={`app ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}
      style={{ '--side-w': `${sidebarWidth}px` } as React.CSSProperties}
    >
      <Sidebar
        user={user}
        conversations={chat.conversations}
        activeId={chat.threadId}
        collapsed={sidebarCollapsed}
        onToggle={toggleSidebar}
        onNewChat={chat.newChat}
        onResume={chat.resume}
        onDelete={chat.remove}
      />
      {!sidebarCollapsed && (
        <div
          className="side-resizer"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          onPointerDown={startResize}
          onDoubleClick={() => {
            setSidebarWidth(DEFAULT_W);
            if (typeof window !== 'undefined') localStorage.setItem(WIDTH_KEY, String(DEFAULT_W));
            refitCharts();
          }}
        />
      )}
      <div className="main">
        <div className="header">
          <div>
            <span className="h-title">London Office</span>
            <span className="h-sub">Commercial real estate monitor</span>
          </div>
          <div className="h-right">
            <span className="live">●</span> illustrative data
          </div>
        </div>

        <div className="transcript">
          {chat.turns.map((t, i) =>
            t.role === 'user' ? (
              <UserMessage key={i} text={t.text} />
            ) : (
              <AssistantTurn key={i} turn={t} />
            ),
          )}
          {chat.liveTurn && <AssistantTurn turn={chat.liveTurn} streaming />}
          {chat.error && <div className="turn stream-error">{chat.error}</div>}
          <div ref={endRef} />
        </div>

        <div className="dock">
          <Suggestions suggestions={dockSuggestions} disabled={chat.streaming} onPick={chat.send} />
          <Composer disabled={chat.streaming} onSend={chat.send} />
        </div>
      </div>
    </div>
  );
}
