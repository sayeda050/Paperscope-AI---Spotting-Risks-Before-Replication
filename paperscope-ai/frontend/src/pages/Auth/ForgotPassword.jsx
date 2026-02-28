import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Shield, Mail, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { forgotPassword } from '../../api/auth.api';
import './ForgotPassword.css';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [submittedEmail, setSubmittedEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const validateEmail = (value) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const trimmedEmail = email.trim();

    if (!trimmedEmail) {
      setError('Email is required.');
      return;
    }

    if (!validateEmail(trimmedEmail)) {
      setError('Please enter a valid email address.');
      return;
    }

    setLoading(true);

    try {
      const data = await forgotPassword({ email: trimmedEmail });

      setSubmittedEmail(trimmedEmail);
      setSuccess(true);

      // If you want to show backend message somewhere later:
      // console.log(data?.detail);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.email?.[0] ||
          'Something went wrong. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="forgot-page">
      <div className="forgot-wrapper">
        <div className="forgot-brand">
          <Shield className="forgot-brand-icon" />
          <h1>PaperScope AI</h1>
        </div>

        <div className="forgot-card">
          {!success ? (
            <>
              <h2>Reset your password</h2>
              <p>We&apos;ll send you a link to reset your password</p>

              <form onSubmit={handleSubmit} className="forgot-form">
                <label htmlFor="email">Email address</label>

                <div className="input-group">
                  <Mail className="input-icon" size={18} />
                  <input
                    type="email"
                    id="email"
                    name="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                  />
                </div>

                {error && <div className="form-error">{error}</div>}

                <button type="submit" className="forgot-btn" disabled={loading}>
                  {loading ? 'Sending...' : 'Send Reset Link'}
                </button>
              </form>

              <Link to="/login" className="back-link">
                <ArrowLeft size={16} />
                <span>Back to sign in</span>
              </Link>
            </>
          ) : (
            <>
              <h2>Reset your password</h2>
              <p className="forgot-success-subtitle">
                We&apos;ll send you a link to reset your password
              </p>

              <div className="success-icon-wrap">
                <CheckCircle2 className="success-icon" />
              </div>

              <h3>Check your email</h3>

              <p className="success-message">
                If an account exists for <span>{submittedEmail}</span>, you&apos;ll
                receive a password reset link.
              </p>

              <p className="success-note">
                Note: If your backend email service is not configured yet, this may
                be a placeholder flow.
              </p>

              <Link to="/login" className="back-link success-back-link">
                <ArrowLeft size={16} />
                <span>Back to sign in</span>
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}