import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { registerUser } from "../../api/auth.api";

export default function Register() {
  const nav = useNavigate();

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    username: "",
    email: "",
    password1: "",
    password2: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function onChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  function prettifyError(err) {
    // dj-rest-auth / DRF style errors: {field: ["msg"]} or {detail:"..."}
    const data = err?.response?.data;
    if (!data) return "Registration failed.";

    if (typeof data === "string") return data;
    if (data.detail) return data.detail;

    // flatten field errors
    const parts = [];
    for (const [k, v] of Object.entries(data)) {
      if (Array.isArray(v)) parts.push(`${k}: ${v.join(" ")}`);
      else if (typeof v === "string") parts.push(`${k}: ${v}`);
      else parts.push(`${k}: ${JSON.stringify(v)}`);
    }
    return parts.join(" | ") || "Registration failed.";
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // IMPORTANT: do NOT auto-login here
      await registerUser(form);

      // go to login only
      nav("/login", { replace: true, state: { justRegistered: true } });
    } catch (err) {
      setError(prettifyError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-slate-950 text-slate-100">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/40 p-8 shadow-lg">
        <h1 className="text-3xl font-bold mb-2">Create Account</h1>
        <p className="text-slate-300 mb-6">
          PaperScope AI — Spotting risks before replication.
        </p>

        {error && (
          <div className="mb-4 rounded-xl border border-red-800 bg-red-950/40 px-4 py-3 text-red-200">
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm mb-1">First Name *</label>
              <input
                name="first_name"
                value={form.first_name}
                onChange={onChange}
                required
                className="w-full rounded-xl bg-slate-950/40 border border-slate-800 px-4 py-3 outline-none focus:border-slate-600"
                placeholder="First name"
              />
            </div>
            <div>
              <label className="block text-sm mb-1">Last Name *</label>
              <input
                name="last_name"
                value={form.last_name}
                onChange={onChange}
                required
                className="w-full rounded-xl bg-slate-950/40 border border-slate-800 px-4 py-3 outline-none focus:border-slate-600"
                placeholder="Last name"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm mb-1">Username *</label>
            <input
              name="username"
              value={form.username}
              onChange={onChange}
              required
              className="w-full rounded-xl bg-slate-950/40 border border-slate-800 px-4 py-3 outline-none focus:border-slate-600"
              placeholder="Username"
            />
          </div>

          <div>
            <label className="block text-sm mb-1">Email *</label>
            <input
              name="email"
              type="email"
              value={form.email}
              onChange={onChange}
              required
              className="w-full rounded-xl bg-slate-950/40 border border-slate-800 px-4 py-3 outline-none focus:border-slate-600"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm mb-1">Password *</label>
            <input
              name="password1"
              type="password"
              value={form.password1}
              onChange={onChange}
              required
              className="w-full rounded-xl bg-slate-950/40 border border-slate-800 px-4 py-3 outline-none focus:border-slate-600"
              placeholder="••••••••"
            />
          </div>

          <div>
            <label className="block text-sm mb-1">Confirm Password *</label>
            <input
              name="password2"
              type="password"
              value={form.password2}
              onChange={onChange}
              required
              className="w-full rounded-xl bg-slate-950/40 border border-slate-800 px-4 py-3 outline-none focus:border-slate-600"
              placeholder="••••••••"
            />
          </div>

          <button
            disabled={loading}
            className="w-full rounded-2xl bg-slate-100 text-slate-900 font-semibold py-3 hover:bg-white disabled:opacity-60"
            type="submit"
          >
            {loading ? "Registering..." : "Register"}
          </button>
        </form>

        <p className="mt-5 text-slate-300">
          Already have an account?{" "}
          <Link className="text-indigo-300 hover:underline" to="/login">
            Login
          </Link>
        </p>
      </div>
    </div>
  );
}