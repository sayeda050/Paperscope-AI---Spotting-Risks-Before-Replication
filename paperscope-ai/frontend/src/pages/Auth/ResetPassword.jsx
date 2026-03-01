import React, { useMemo, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import {
  Shield,
  Lock,
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
} from 'lucide-react';
import { resetPassword } from '../../api/auth.api';
import './ResetPassword.css';

const useQuery = () => {
  const { search } = useLocation();
  return useMemo(() => new URLSearchParams(search), [search]);
};

export default function ResetPassword() {
  const q = useQuery();
  const navigate = useNavigate();

  const uid = q.get('uid');
  const token = q.get('token');

  const [pw, setPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);

  const validatePassword = (password) => {
    if (!password.trim()) {
      return 'Password is required.';
    }
    if (password.length < 8) {
      return 'Password must be at least 8 characters.';
    }
    return '';
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setMsg('');
    setErr('');

    if (!uid || !token) {
      setErr('Invalid or expired reset link.');
      return;
    }

    const passwordError = validatePassword(pw);
    if (passwordError) {
      setErr(passwordError);
      return;
    }

    if (!confirmPw.trim()) {
      setErr('Please confirm your password.');
      return;
    }

    if (pw !== confirmPw) {
      setErr('Passwords do not match.');
      return;
    }

    setLoading(true);

    try {
      const data = await resetPassword({
        uid,
        token,
        new_password: pw,
      });

      setMsg(data?.detail || 'Password reset successful.');
      setSuccess(true);

      setTimeout(() => {
        navigate('/login');
      }, 1500);
    } catch (e) {
      setErr(
        e?.response?.data?.detail ||
          e?.response?.data?.new_password?.[0] ||
          'Invalid or expired reset link.'
      );
    } finally {
      setLoading(false);
    }
  };

  if (!uid || !token) {
    return (
      <div className="reset-page">
        <div className="reset-wrapper">
          <div className="reset-brand">
            <Shield className="reset-brand-icon" />
            <h1>PaperScope AI</h1>
          </div>

          <div className="reset-card">
            <h2>Invalid reset link</h2>
            <p className="reset-invalid-text">
              This password reset link is missing information or may have expired.
            </p>

            <Link to="/forgot-password" className="reset-back-link">
              <ArrowLeft size={16} />
              <span>Back to forgot password</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="reset-page">
      <div className="reset-wrapper">
        <div className="reset-brand">
          <Shield className="reset-brand-icon" />
          <h1>PaperScope AI</h1>
        </div>

        <div className="reset-card">
          {!success ? (
            <>
              <h2>Set new password</h2>
              <p className="reset-subtitle">
                Enter your new password below to complete the reset process
              </p>

              <form onSubmit={onSubmit} className="reset-form">
                <label htmlFor="newPassword">New password</label>
                <div className="reset-input-group">
                  <Lock className="reset-input-icon" size={18} />
                  <input
                    id="newPassword"
                    type={showPw ? 'text' : 'password'}
                    value={pw}
                    placeholder="Enter new password"
                    onChange={(e) => setPw(e.target.value)}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="reset-eye-btn"
                    onClick={() => setShowPw((prev) => !prev)}
                    aria-label={showPw ? 'Hide password' : 'Show password'}
                  >
                    {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>

                <label htmlFor="confirmPassword">Confirm password</label>
                <div className="reset-input-group">
                  <Lock className="reset-input-icon" size={18} />
                  <input
                    id="confirmPassword"
                    type={showConfirmPw ? 'text' : 'password'}
                    value={confirmPw}
                    placeholder="Confirm new password"
                    onChange={(e) => setConfirmPw(e.target.value)}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="reset-eye-btn"
                    onClick={() => setShowConfirmPw((prev) => !prev)}
                    aria-label={showConfirmPw ? 'Hide password' : 'Show password'}
                  >
                    {showConfirmPw ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>

                {err && <div className="reset-error-box">{err}</div>}
                {msg && <div className="reset-success-box">{msg}</div>}

                <button
                  type="submit"
                  className="reset-btn"
                  disabled={loading}
                >
                  {loading ? 'Resetting...' : 'Reset Password'}
                </button>
              </form>

              <Link to="/login" className="reset-back-link">
                <ArrowLeft size={16} />
                <span>Back to sign in</span>
              </Link>
            </>
          ) : (
            <>
              <h2>Password reset successful</h2>
              <p className="reset-subtitle">
                Your password has been updated successfully
              </p>

              <div className="reset-success-icon-wrap">
                <CheckCircle2 className="reset-success-icon" />
              </div>

              <h3>You can sign in now</h3>

              <p className="reset-success-message">
                Your password has been reset successfully. Redirecting you to the
                sign in page...
              </p>

              <Link to="/login" className="reset-back-link reset-success-link">
                <ArrowLeft size={16} />
                <span>Go to sign in</span>
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}