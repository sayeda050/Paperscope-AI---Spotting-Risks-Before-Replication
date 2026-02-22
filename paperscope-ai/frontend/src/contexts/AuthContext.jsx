import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { registerUser, loginUser, getMe, logoutUser } from "../api/auth.api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function boot() {
      try {
        const token = localStorage.getItem("access_token");
        if (!token) {
          if (mounted) setUser(null);
          return;
        }
        const me = await getMe();
        if (mounted) setUser(me);
      } catch (e) {
        localStorage.removeItem("access_token");
        if (mounted) setUser(null);
      } finally {
        if (mounted) setInitializing(false);
      }
    }

    boot();
    return () => {
      mounted = false;
    };
  }, []);

  const register = async (payload) => {
    try {
      const data = await registerUser(payload);
      // DO NOT auto-login here
      return { success: true, data };
    } catch (err) {
      const msg = err?.response?.data ? JSON.stringify(err.response.data) : (err?.message || "Registration failed");
      return { success: false, error: msg };
    }
  };

  const login = async (payload) => {
    try {
      const data = await loginUser(payload);
      const token = data?.key;

      if (!token) return { success: false, error: "No token returned from backend." };

      localStorage.setItem("access_token", token);
      const me = await getMe();
      setUser(me);
      return { success: true, data: me };
    } catch (err) {
      const msg = err?.response?.data ? JSON.stringify(err.response.data) : (err?.message || "Login failed");
      return { success: false, error: msg };
    }
  };

  const logout = async () => {
    try {
      await logoutUser();
    } catch (e) {
      // ignore
    } finally {
      localStorage.removeItem("access_token");
      setUser(null);
    }
  };

  const value = useMemo(
    () => ({
      user,
      initializing,
      isAuthed: !!localStorage.getItem("access_token"),
      register,
      login,
      logout,
    }),
    [user, initializing]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider />");
  return ctx;
}