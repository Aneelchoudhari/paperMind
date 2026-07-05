import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import { api } from '../utils/api';

export default function AuthPage() {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ email: '', password: '', full_name: '' });
  const navigate = useNavigate();

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === 'register') {
        await api.register({ email: form.email, password: form.password, full_name: form.full_name });
        toast.success('Account created! Please sign in.');
        setMode('login');
      } else {
        const res = await api.login({ email: form.email, password: form.password });
        localStorage.setItem('pm_token', res.access_token);
        toast.success('Welcome back!');
        navigate('/library');
      }
    } catch (err) {
      toast.error(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🧠</div>
          <div className="auth-title gradient-text">PaperMind AI</div>
          <div className="auth-subtitle">Research Paper Intelligence</div>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {mode === 'register' && (
            <div className="form-group">
              <label className="label">Full Name</label>
              <input className="input" type="text" placeholder="Jane Smith" value={form.full_name} onChange={set('full_name')} />
            </div>
          )}
          <div className="form-group">
            <label className="label">Email</label>
            <input className="input" type="email" placeholder="you@example.com" value={form.email} onChange={set('email')} required />
          </div>
          <div className="form-group">
            <label className="label">Password</label>
            <input className="input" type="password" placeholder="••••••••" value={form.password} onChange={set('password')} required minLength={8} />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ marginTop: '0.5rem' }}>
            {loading ? <span className="spinner" /> : mode === 'login' ? '🔑 Sign In' : '🚀 Create Account'}
          </button>
        </form>

        <div style={{ margin: '1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          <hr style={{ flex: 1, border: 'none', borderTop: '1px solid var(--border)' }} />
          <span>or</span>
          <hr style={{ flex: 1, border: 'none', borderTop: '1px solid var(--border)' }} />
        </div>

        <button
          className="btn"
          type="button"
          onClick={async () => {
            setLoading(true);
            try {
              const guestEmail = `guest_${Math.floor(Math.random() * 10000000)}@papermind.ai`;
              const guestPassword = `guestpwd_${Math.floor(Math.random() * 10000000)}`;
              const guestName = 'Guest Scholar';
              await api.register({ email: guestEmail, password: guestPassword, full_name: guestName });
              const res = await api.login({ email: guestEmail, password: guestPassword });
              localStorage.setItem('pm_token', res.access_token);
              toast.success('Welcome, Guest Scholar!');
              navigate('/library');
            } catch (err) {
              toast.error(err.message || 'Could not enter as guest. Please try registering manually.');
            } finally {
              setLoading(false);
            }
          }}
          disabled={loading}
          style={{ background: 'rgba(255, 255, 255, 0.05)', color: 'var(--text-secondary)', border: '1px solid var(--border)', width: '100%' }}
        >
          👤 Continue as Guest
        </button>

        <div className="auth-switch">
          {mode === 'login' ? (
            <>Don't have an account? <span className="auth-link" onClick={() => setMode('register')}>Sign up</span></>
          ) : (
            <>Already have an account? <span className="auth-link" onClick={() => setMode('login')}>Sign in</span></>
          )}
        </div>
      </div>
    </div>
  );
}
