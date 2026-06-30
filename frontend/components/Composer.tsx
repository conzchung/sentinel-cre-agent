'use client';

import { useRef, useState } from 'react';
import { SendIcon } from './Icons';

export default function Composer({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (text: string) => void;
}) {
  const [value, setValue] = useState('');
  const taRef = useRef<HTMLTextAreaElement>(null);

  function autoGrow(el: HTMLTextAreaElement) {
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }

  function submit() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue('');
    if (taRef.current) taRef.current.style.height = 'auto';
  }

  return (
    <div className="composer">
      <div className="row">
        <textarea
          ref={taRef}
          placeholder="Ask Sentinel"
          value={value}
          disabled={disabled}
          rows={1}
          onChange={(e) => {
            setValue(e.target.value);
            autoGrow(e.target);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button className="btn send" onClick={submit} disabled={disabled} aria-label="Send message">
          <SendIcon size={16} />
          {disabled ? 'Sending…' : 'Send'}
        </button>
      </div>
    </div>
  );
}
