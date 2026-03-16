import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import { Shield, Mail, Lock, Loader2 } from 'lucide-react';
import './Login.css';

function normalizeErrorMessage(err) {
  if (!err) return 'Login failed. Please check your credentials.';

  if (typeof err === 'string') return err;

  if (Array.isArray(err)) {
    return err.map((item) => normalizeErrorMessage(item)).join(' ');
  }

  if (typeof err === 'object') {
    if (typeof err.detail === 'string') return err.detail;

    if (Array.isArray(err.non_field_errors) && err.non_field_errors.length > 0) {
      return err.non_field_errors.join(' ');
    }

    if (Array.isArray(err.email) && err.email.length > 0) {
      return err.email.join(' ');
    }

    if (Array.isArray(err.username) && err.username.length > 0) {
      return err.username.join(' ');
    }

    if (Array.isArray(err.password) && err.password.length > 0) {
      return err.password.join(' ');
    }

    const flatValues = Object.values(err)
      .flatMap((value) => (Array.isArray(value) ? value : [value]))
      .filter((value) => typeof value === 'string');

    if (flatValues.length > 0) {
      return flatValues.join(' ');
    }
  }

  return 'Invalid email or password.';
}

export default function Login() {
  const { login, googleLogin } = useAuth();
  const navigate = useNavigate();
 
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const existing = document.querySelector('script[src="https://accounts.google.com/gsi/client"]');
    if (existing) return;

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await login({
        email: email,
        password: password
      });

      if (res.success) {
        navigate('/dashboard');
      } else {
        setError(normalizeErrorMessage(res.error));
      }
    } catch (err) {
      setError(normalizeErrorMessage(err?.response?.data || err?.message));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = () => {
    setError('');

    if (!window.google) {
      setError('Google script is still loading. Please wait a second and try again.');
      return;
    }

    const client = window.google.accounts.oauth2.initTokenClient({
      client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
      scope: 'email profile',
      callback: async (response) => {
        if (response.error) {
          setError(`Google login failed: ${response.error}`);
          return;
        }
        
        if (response.access_token) {
          setLoading(true);
          try {
            const res = await googleLogin(response.access_token);

            if (res.success) {
              navigate('/dashboard');
            } else {
              setError(normalizeErrorMessage(res.error));
            }
          } catch (err) {
            setError(normalizeErrorMessage(err?.response?.data || err?.message));
          } finally {
            setLoading(false);
          }
        }
      },
    });
    
    client.requestAccessToken();
  };

  return (
    <div className="ps-register-page">
      <div className="ps-register-card">
        
        <Link to="/" className="ps-register-brand">
          <Shield className="ps-brand-icon" size={32} />
          <span className="ps-brand-text">PaperScope AI</span>
        </Link>

        <div className="ps-register-header">
          <h1 className="ps-register-title">Welcome back</h1>
          <p className="ps-register-subtitle">Sign in to your account to continue</p>
        </div>

        {error && <div className="ps-register-error">{error}</div>}

        <form onSubmit={handleSubmit} className="ps-register-form" autoComplete="off">
          <input type="text" style={{ display: 'none' }} />
          <input type="password" style={{ display: 'none' }} />

          <div className="ps-field">
            <label htmlFor="email" className="ps-label">Email</label>
            <div className="ps-input-wrapper">
              <Mail className="ps-input-icon" size={16} />
              <input
                id="email"
                type="email"
                className="ps-input has-icon"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="off"
                required
              />
            </div>
          </div>

          <div className="ps-field">
            <div className="ps-label-row">
              <label htmlFor="password" className="ps-label">Password</label>
              <Link
                to="/forgot-password"
                style={{ fontSize: '14px', color: '#0d9488', textDecoration: 'none' }}
              >
                Forgot password?
              </Link>
            </div>
            <div className="ps-input-wrapper">
              <Lock className="ps-input-icon" size={16} />
              <input
                id="password"
                type="password"
                className="ps-input has-icon"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </div>
          </div>

          <button type="submit" className="ps-btn ps-btn-primary" disabled={loading}>
            {loading && <Loader2 className="ps-spin" size={16} />}
            Sign In
          </button>
        </form>

        <div className="ps-divider">
          <div className="ps-divider-line"></div>
          <span className="ps-divider-text">or continue with</span>
        </div>

        <button type="button" className="ps-btn ps-btn-outline" onClick={handleGoogle} disabled={loading}>
          <svg width="16" height="16" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Google Sign In
        </button>

        <p className="ps-register-footer">
          Don't have an account? <Link to="/register" className="ps-link">Create one</Link>
        </p>
      </div>
    </div>
  );
}