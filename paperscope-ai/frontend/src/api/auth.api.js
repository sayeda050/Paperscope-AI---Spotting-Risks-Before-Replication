import http from "./http";

// dj-rest-auth endpoints
export async function registerUser(payload) {
  const res = await http.post("/api/auth/registration/", payload);
  return res.data;
}

export async function loginUser(payload) {
  const res = await http.post("/api/auth/login/", payload);
  return res.data;
}

export async function logoutUser() {
  const res = await http.post("/api/auth/logout/");
  return res.data;
}

export async function getMe() {
  const res = await http.get("/api/users/me/");
  return res.data;
}

// ==========================================
// GOOGLE LOGIN
// ==========================================
export async function googleLoginUser(payload) {
  const res = await http.post("/api/users/google/", payload);
  return res.data;
}

// ==========================================
// FORGOT / RESET PASSWORD
// ==========================================
export async function forgotPassword(payload) {
  const res = await http.post("/api/users/forgot-password/", payload);
  return res.data;
}

export async function resetPassword(payload) {
  const res = await http.post("/api/users/reset-password/", payload);
  return res.data;
}

// ==========================================
// CHANGE PASSWORD (LOGGED-IN USER)
// ==========================================
export async function changePassword(payload) {
  const res = await http.post("/api/auth/password/change/", payload);
  return res.data;
}