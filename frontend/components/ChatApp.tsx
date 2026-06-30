'use client';

import { useEffect, useRef, useState } from 'react';
import Sidebar from './Sidebar';
import UserMessage from './UserMessage';
import AssistantTurn from './AssistantTurn';
import Suggestions from './Suggestions';
import Composer from './Composer';
import { MenuIcon } from './Icons';
import { useChat } from './useChat';

export default function ChatApp({ user }: { user: string }) {
  const chat = useChat();
  const endRef = useRef<HTMLDivElement>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const closeDrawer = () => setDrawerOpen(false);

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
    <div className="app">
      {drawerOpen && <div className="scrim" onClick={closeDrawer} />}
      <Sidebar
        user={user}
        conversations={chat.conversations}
        activeId={chat.threadId}
        open={drawerOpen}
        onClose={closeDrawer}
        onNewChat={chat.newChat}
        onResume={chat.resume}
        onDelete={chat.remove}
      />
      <div className="main">
        <div className="header">
          <div className="h-left">
            <button
              className="mobile-menu"
              aria-label="Open menu"
              onClick={() => setDrawerOpen((o) => !o)}
            >
              <MenuIcon size={18} />
            </button>
            <div>
              <span className="h-title">London Office</span>
              <span className="h-sub">Commercial real estate monitor</span>
            </div>
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
