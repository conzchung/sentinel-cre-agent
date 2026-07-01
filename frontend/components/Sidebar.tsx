'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { Conversation } from '@/lib/types';
import { TrashIcon, LogoutIcon, CheckIcon, CloseIcon } from './Icons';

export default function Sidebar({
  user,
  conversations,
  activeId,
  open,
  onClose,
  onNewChat,
  onResume,
  onDelete,
}: {
  user: string;
  conversations: Conversation[];
  activeId: string;
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onResume: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const router = useRouter();
  const [confirmId, setConfirmId] = useState<string | null>(null);

  async function logout() {
    onClose();
    await fetch('/api/logout', { method: 'POST' });
    router.replace('/login');
    router.refresh();
  }

  // Each nav action also dismisses the mobile drawer (no-op visually on desktop,
  // where the sidebar is always in the grid).
  function handleNewChat() {
    onNewChat();
    onClose();
  }
  function handleResume(id: string) {
    onResume(id);
    onClose();
  }
  function handleDelete(id: string) {
    onDelete(id);
    setConfirmId(null);
    onClose();
  }

  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="side-top">
        <div className="brand">
          <span className="brand-mark">S</span>
          <span className="brand-name">SENTINEL</span>
        </div>
        <button className="btn-ghost newchat" onClick={handleNewChat}>
          New Chat
        </button>
      </div>

      <div className="side-list">
        <div className="side-cap">Conversations</div>
        {conversations.length === 0 && <div className="side-empty">No conversations yet.</div>}
        {conversations.map((c) => {
          const confirming = confirmId === c.thread_id;
          return (
            <div
              key={c.thread_id}
              className={`convo-row ${c.thread_id === activeId ? 'active' : ''} ${
                confirming ? 'confirming' : ''
              }`}
            >
              {confirming ? (
                <>
                  <span className="confirm-label">Delete?</span>
                  <button
                    className="confirm-yes"
                    title="Confirm delete"
                    aria-label="Confirm delete"
                    onClick={() => handleDelete(c.thread_id)}
                  >
                    <CheckIcon size={14} />
                  </button>
                  <button
                    className="confirm-no"
                    title="Cancel"
                    aria-label="Cancel delete"
                    onClick={() => setConfirmId(null)}
                  >
                    <CloseIcon size={14} />
                  </button>
                </>
              ) : (
                <>
                  <button
                    className="title"
                    title={c.convo_title || 'Untitled'}
                    onClick={() => handleResume(c.thread_id)}
                  >
                    {c.convo_title || 'Untitled conversation'}
                  </button>
                  <button
                    className="del"
                    title="Delete"
                    aria-label="Delete conversation"
                    onClick={() => setConfirmId(c.thread_id)}
                  >
                    <TrashIcon size={14} />
                  </button>
                </>
              )}
            </div>
          );
        })}
      </div>

      <div className="side-foot">
        <div className="side-who">
          <span className="avatar">{user.charAt(0).toUpperCase()}</span>
          <span>{user}</span>
        </div>
        <button className="logout" title="Log out" aria-label="Log out" onClick={logout}>
          <LogoutIcon size={15} />
        </button>
      </div>
    </aside>
  );
}
