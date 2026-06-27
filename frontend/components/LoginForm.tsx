'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginForm() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (r.ok) {
        router.replace('/');
        router.refresh();
      } else {
        setError('Invalid username or password. Please try again.');
      }
    } catch {
      setError('Could not reach the server. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <div className="login-aside">
        <div className="la-brand">
          <span className="brand-mark">S</span>
          <span className="brand-name">SENTINEL</span>
        </div>
        <h1 className="la-h1">
          The London office market,
          <br />
          watched in real time.
        </h1>
        <p className="la-p">
          Prime &amp; Grade-A rents, vacancy, leasing take-up, the supply pipeline and live news —
          answered with data, charts and citations.
        </p>
        <div className="la-stats">
          <div>
            <b>142.5</b>
            <span>West End prime £/sq ft</span>
          </div>
          <div>
            <b>5.3%</b>
            <span>West End vacancy</span>
          </div>
          <div>
            <b>4</b>
            <span>market skills</span>
          </div>
        </div>
        <div className="la-foot">Illustrative, public-range data · not investment advice</div>
      </div>

      <div className="login-panel">
        <form className="login-card" onSubmit={submit}>
          <h1>Welcome back</h1>
          <p className="sub">Sign in to your market workspace.</p>
          <div className="field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
          {error && <div className="error">{error}</div>}
          <div className="login-hint">Demo workspace · credentials provided on request</div>
        </form>
      </div>
    </div>
  );
}
