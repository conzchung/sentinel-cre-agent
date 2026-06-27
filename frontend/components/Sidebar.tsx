'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { Conversation } from '@/lib/types';
import { PlusIcon, TrashIcon, LogoutIcon, CheckIcon, CloseIcon, SidebarIcon } from './Icons';

export default function Sidebar({
  user,
  conversations,
  activeId,
  collapsed,
  onToggle,
  onNewChat,
  onResume,
  onDelete,
}: {
  user: string;
  conversations: Conversation[];
  activeId: string;
  collapsed: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  onResume: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const router = useRouter();
  const [confirmId, setConfirmId] = useState<string | null>(null);

  async function logout() {
    await fetch('/api/logout', { method: 'POST' });
    router.replace('/login');
    router.refresh();
  }

  // Collapsed rail: icon-only affordances, no conversation list.
  if (collapsed) {
    return (
      <aside className="sidebar is-collapsed">
        <div className="side-top">
          <button
            className="rail-btn brand-mark-btn"
            title="Expand sidebar (⌘\)"
            aria-label="Expand sidebar"
            onClick={onToggle}
          >
            <span className="brand-mark">S</span>
          </button>
          <button
            className="rail-btn"
            title="New chat"
            aria-label="New chat"
            onClick={onNewChat}
          >
            <PlusIcon size={17} />
          </button>
        </div>
        <div className="side-list" />
        <div className="side-foot">
          <button className="rail-btn" title="Log out" aria-label="Log out" onClick={logout}>
            <LogoutIcon size={16} />
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="sidebar">
      <div className="side-top">
        <div className="brand">
          <span className="brand-mark">S</span>
          <span className="brand-name">SENTINEL</span>
          <button
            className="side-collapse"
            title="Collapse sidebar (⌘\)"
            aria-label="Collapse sidebar"
            onClick={onToggle}
          >
            <SidebarIcon size={16} />
          </button>
        </div>
        <button className="btn-ghost newchat" onClick={onNewChat}>
          <PlusIcon size={16} />
          New chat
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
                    onClick={() => {
                      onDelete(c.thread_id);
                      setConfirmId(null);
                    }}
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
                    onClick={() => onResume(c.thread_id)}
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
