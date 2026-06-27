'use client';

import { useCallback, useRef, useState } from 'react';
import { createStreamParser, emptyAssistantTurn } from '@/lib/streamParser';
import { rebuildHistory } from '@/lib/rebuildHistory';
import type { Turn, Conversation } from '@/lib/types';

function newId(): string {
  return crypto.randomUUID();
}

export function useChat() {
  const [threadId, setThreadId] = useState<string>(() => newId());
  const [turns, setTurns] = useState<Turn[]>([]);
  const [liveTurn, setLiveTurn] = useState<Turn | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Coalesce the many tiny stream chunks into at most one render per animation
  // frame: the parser keeps the authoritative turn, and a queued rAF flushes
  // the latest snapshot to React. This keeps streaming visually smooth instead
  // of thrashing on every token.
  const pendingTurn = useRef<Turn | null>(null);
  const rafId = useRef<number | null>(null);

  const flush = useCallback(() => {
    rafId.current = null;
    if (pendingTurn.current) setLiveTurn(pendingTurn.current);
  }, []);

  const scheduleFlush = useCallback(
    (turn: Turn) => {
      pendingTurn.current = turn;
      if (rafId.current == null) {
        rafId.current =
          typeof requestAnimationFrame === 'function'
            ? requestAnimationFrame(flush)
            : (setTimeout(flush, 16) as unknown as number);
      }
    },
    [flush],
  );

  const cancelFlush = useCallback(() => {
    if (rafId.current != null) {
      if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(rafId.current);
      else clearTimeout(rafId.current);
      rafId.current = null;
    }
    pendingTurn.current = null;
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const r = await fetch('/api/conversations');
      if (r.ok) setConversations(await r.json());
    } catch {
      /* leave the existing list in place */
    }
  }, []);

  const send = useCallback(
    async (message: string) => {
      const text = message.trim();
      if (!text || streaming) return;
      setError(null);
      setTurns((t) => [
        ...t,
        { role: 'user', text, plan: [], actions: [], charts: [], suggestions: [] },
      ]);
      setStreaming(true);
      setLiveTurn(emptyAssistantTurn());
      const parser = createStreamParser();
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, thread_id: threadId }),
        });
        if (!res.ok || !res.body) throw new Error(`bad response ${res.status}`);
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          const turn = parser.feed(decoder.decode(value, { stream: true }));
          scheduleFlush({ ...turn });
        }
        cancelFlush();
        setTurns((t) => [...t, parser.end()]);
      } catch {
        cancelFlush();
        setTurns((t) => [...t, parser.current()]);
        setError('Stream interrupted — please retry.');
      } finally {
        setLiveTurn(null);
        setStreaming(false);
        refreshConversations();
      }
    },
    [threadId, streaming, refreshConversations, scheduleFlush, cancelFlush],
  );

  const newChat = useCallback(() => {
    setThreadId(newId());
    setTurns([]);
    setLiveTurn(null);
    setError(null);
  }, []);

  const resume = useCallback(async (id: string) => {
    setError(null);
    setThreadId(id);
    setLiveTurn(null);
    try {
      const r = await fetch(`/api/conversations/${id}`);
      const doc = r.ok ? await r.json() : { dialog: [] };
      setTurns(rebuildHistory(doc.dialog || []));
    } catch {
      setTurns([]);
    }
  }, []);

  const remove = useCallback(
    async (id: string) => {
      try {
        await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
      } catch {
        /* ignore */
      }
      setConversations((c) => c.filter((x) => x.thread_id !== id));
      if (id === threadId) newChat();
    },
    [threadId, newChat],
  );

  return {
    threadId,
    turns,
    liveTurn,
    streaming,
    conversations,
    error,
    send,
    newChat,
    resume,
    remove,
    refreshConversations,
  };
}
