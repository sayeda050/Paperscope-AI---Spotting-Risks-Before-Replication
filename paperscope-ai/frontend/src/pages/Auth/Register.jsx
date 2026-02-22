import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import { Shield, Mail, Lock, User, Loader2 } from 'lucide-react';
import './Register.css';

export default function Register() {
  const { register, googleLogin } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', password: '', confirm: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    if (form.password !== form.confirm) { 
      setError('Passwords do not match'); 
      return; 
    }
    if (form.password.length < 6) { 
      setError('Password must be at least 6 characters'); 
      return; 
    }
    
    setLoading(true);
    const res = await register({ 
      firstName: form.firstName, 
      lastName: form.lastName, 
      email: form.email, 
      password: form.password 
    });
    setLoading(false);
    
    if (res.success) {
      navigate('/login');
    } else {
      setError(res.error || 'Registration failed');
    }
  };

  const handleGoogle = async () => {
    setLoading(true);
    const res = await googleLogin();
    setLoading(false);
    if (res.success) navigate('/dashboard');
  };

  const update = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }));

  return (
    <div className="ps-register-page">
      <div className="ps-register-card">
        
        {/* Brand Link */}
        <Link to="/" className="ps-register-brand">
          <Shield className="ps-brand-icon" size={32} />
          <span className="ps-brand-text">PaperScope AI</span>
        </Link>

        {/* Header */}
        <div className="ps-register-header">
          <h1 className="ps-register-title">Create your account</h1>
          <p className="ps-register-subtitle">Start analyzing research papers today</p>
        </div>

        {/* Error Alert */}
        {error && <div className="ps-register-error">{error}</div>}

        {/* Form */}
        <form onSubmit={handleSubmit} className="ps-register-form">
          <div className="ps-register-grid">
            <div className="ps-field">
              <label htmlFor="fn" className="ps-label">First Name</label>
              <div className="ps-input-wrapper">
                <User className="ps-input-icon" size={16} />
                <input 
                  id="fn" 
                  className="ps-input has-icon" 
                  placeholder="Jane" 
                  value={form.firstName} 
                  onChange={update('firstName')} 
                  required 
                />
              </div>
            </div>

            <div className="ps-field">
              <label htmlFor="ln" className="ps-label">Last Name</label>
              <input 
                id="ln" 
                className="ps-input" 
                placeholder="Doe" 
                value={form.lastName} 
                onChange={update('lastName')} 
                required 
              />
            </div>
          </div>

          <div className="ps-field">
            <label htmlFor="email" className="ps-label">Email</label>
            <div className="ps-input-wrapper">
              <Mail className="ps-input-icon" size={16} />
              <input 
                id="email" 
                type="email" 
                className="ps-input has-icon" 
                placeholder="you@example.com" 
                value={form.email} 
                onChange={update('email')} 
                required 
              />
            </div>
          </div>

          <div className="ps-field">
            <label htmlFor="pw" className="ps-label">Password</label>
            <div className="ps-input-wrapper">
              <Lock className="ps-input-icon" size={16} />
              <input 
                id="pw" 
                type="password" 
                className="ps-input has-icon" 
                placeholder="Min 6 characters" 
                value={form.password} 
                onChange={update('password')} 
                required 
              />
            </div>
          </div>

          <div className="ps-field">
            <label htmlFor="cpw" className="ps-label">Confirm Password</label>
            <input 
              id="cpw" 
              type="password" 
              className="ps-input" 
              placeholder="••••••••" 
              value={form.confirm} 
              onChange={update('confirm')} 
              required 
            />
          </div>

          <button type="submit" className="ps-btn ps-btn-primary" disabled={loading}>
            {loading && <Loader2 className="ps-spin" size={16} />} 
            Create Account
          </button>
        </form>

        {/* Divider */}
        <div className="ps-divider">
          <div className="ps-divider-line"></div>
          <span className="ps-divider-text">or</span>
        </div>

        {/* Google Login */}
        <button type="button" className="ps-btn ps-btn-outline" onClick={handleGoogle} disabled={loading}>
          <svg width="16" height="16" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Sign up with Google
        </button>

        {/* Footer Link */}
        <p className="ps-register-footer">
          Already have an account? <Link to="/login" className="ps-link">Sign in</Link>
        </p>

      </div>
    </div>
  );
}