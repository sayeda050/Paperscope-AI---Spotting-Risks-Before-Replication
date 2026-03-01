import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { registerUser, loginUser, getMe, logoutUser, googleLoginUser } from "../api/auth.api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(true);

  // Checks if the user is logged in by asking the backend "Who am I?"
  const checkAuth = async () => {
    try {
      const me = await getMe(); // Calls /api/users/me/
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
      const msg = err?.response?.data ? JSON.stringify(err.response.data) : "Registration failed";
      return { success: false, error: msg };
    }
  };

  const login = async (payload) => {
    try {
      await loginUser(payload);
      // After successful login, the backend sets a cookie. 
      // We just need to refresh the user state.
      await checkAuth();
      return { success: true };
    } catch (err) {
      const msg = err?.response?.data ? JSON.stringify(err.response.data) : "Login failed";
      return { success: false, error: msg };
    }
  };

  const googleLogin = async (googleToken) => {
    try {
      await googleLoginUser({ access_token: googleToken });
      // Refresh user state after Google sets the auth cookie
      await checkAuth();
      return { success: true };
    } catch (err) {
      const msg = err?.response?.data ? JSON.stringify(err.response.data) : "Google Login failed";
      return { success: false, error: msg };
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
      isAuthed: !!user, // You are authenticated if the 'user' object exists
      register,
      login,
      googleLogin, 
      logout,
      checkAuth
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