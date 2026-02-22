import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { loginUser } from "../../api/auth.api";

export default function Login() {
  const nav = useNavigate();
  const location = useLocation();

  const [form, setForm] = useState({
    // choose one; backend can accept username
    username: "",
    password: "",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  useEffect(() => {
    if (location.state?.justRegistered) {
      setInfo("Registration successful. Please login.");
    }
  }, [location.state]);

  function onChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  function prettifyError(err) {
    const data = err?.response?.data;
    if (!data) return "Login failed.";
    if (typeof data === "string") return data;
    if (data.detail) return data.detail;
    return JSON.stringify(data);
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);

    try {
      const data = await loginUser(form);

      // store token (dj-rest-auth token auth)
      if (data?.key) localStorage.setItem("access_token", data.key);

      nav("/dashboard", { replace: true });
    } catch (err) {
      setError(prettifyError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-slate-950 text-slate-100">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/40 p-8 shadow-lg">
        <h1 className="text-3xl font-bold mb-2">Login</h1>
        <p className="text-slate-300 mb-6">Welcome back to PaperScope AI.</p>

        {info && (
          <div className="mb-4 rounded-xl border border-slate-700 bg-slate-950/40 px-4 py-3 text-slate-200">
            {info}
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-xl border border-red-800 bg-red-950/40 px-4 py-3 text-red-200">
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-4">
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
            <label className="block text-sm mb-1">Password *</label>
            <input
              name="password"
              type="password"
              value={form.password}
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
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>

        <p className="mt-5 text-slate-300">
          Don’t have an account?{" "}
          <Link className="text-indigo-300 hover:underline" to="/register">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}