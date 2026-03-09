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

  // Inside AuthContext.jsx
  const login = async (payload) => {
    try {
      const data = await loginUser(payload); // API call
      
      // 🚨 CRITICAL: You MUST set the state here before returning!
      // If you skip this, PrivateRoute will kick the user out.
      setUser(data.user); // Or however your backend returns user data
      // FIXED: Removed setIsAuthed(true) because it does not exist and caused the crash!
      
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data };
    }
  };

  const googleLogin = async (accessToken) => {
    try {
      // 1. MUST wrap the token in an object matching Django's expectation
      const payload = { access_token: accessToken }; 
      const data = await googleLoginUser(payload);
      
      // 2. 🚨 CRITICAL: Set state before returning so the router doesn't bounce you
      setUser(data.user); 
      // FIXED: Removed setIsAuthed(true) because it does not exist and caused the crash!
      
      return { success: true };
    } catch (err) {
      console.error("Google Auth Error:", err.response?.data);
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
