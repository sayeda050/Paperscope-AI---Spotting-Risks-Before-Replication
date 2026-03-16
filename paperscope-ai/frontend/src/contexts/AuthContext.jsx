import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { registerUser, loginUser, getMe, logoutUser, googleLoginUser } from "../api/auth.api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(true);

  const checkAuth = async () => {
    try {
      const me = await getMe();
      setUser(me);
    } catch (e) {
      setUser(null);
    } finally {
      setInitializing(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  const register = async (payload) => {
    try {
      const data = await registerUser(payload);
      return { success: true, data };
    } catch (err) {
      const msg = err?.response?.data
        ? JSON.stringify(err.response.data)
        : "Registration failed";
      return { success: false, error: msg };
    }
  };

  const login = async (payload) => {
    try {
      // Step 1: hit login endpoint so backend sets JWT cookies
      await loginUser(payload);

      // Step 2: verify cookie-based auth actually works
      const me = await getMe();
      setUser(me);

      return { success: true };
    } catch (err) {
      setUser(null);
      return {
        success: false,
        error: err?.response?.data || "Login failed",
      };
    }
  };

  const googleLogin = async (accessToken) => {
    try {
      const payload = { access_token: accessToken };

      // Step 1: let backend set JWT cookies
      await googleLoginUser(payload);

      // Step 2: verify cookie-based auth actually works
      const me = await getMe();
      setUser(me);

      return { success: true };
    } catch (err) {
      setUser(null);
      console.error("Google Auth Error:", err?.response?.data);
      return { success: false, error: "Google login failed on the server." };
    }
  };

  const logout = async () => {
    try {
      await logoutUser();
    } catch (e) {
      console.error("Logout failed", e);
    } finally {
      setUser(null);
    }
  };

  const value = useMemo(
    () => ({
      user,
      initializing,
      isAuthed: !!user,
      register,
      login,
      googleLogin,
      logout,
      checkAuth,
    }),
    [user, initializing]
  );

  return (
    <AuthContext.Provider value={value}>
      {!initializing && children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider />");
  return ctx;
}