import http from "./http";

// dj-rest-auth endpoints
export async function registerUser(payload) {
  // expected: registration payload handled by backend serializer
  const res = await http.post("/api/auth/registration/", payload);
  return res.data;
}

export async function loginUser(payload) {
  // expected: login payload handled by backend auth setup
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

<<<<<<< HEAD
// GOOGLE LOGIN
=======
// ==========================================
// GOOGLE LOGIN
// ==========================================
>>>>>>> Nusrat
export async function googleLoginUser(payload) {
  const res = await http.post("/api/users/google/", payload);
  return res.data;
}

<<<<<<< HEAD
// FORGOT / RESET PASSWORD
=======
// ==========================================
// FORGOT / RESET PASSWORD
// ==========================================
>>>>>>> Nusrat
export async function forgotPassword(payload) {
  // expected: { email }
  const res = await http.post("/api/users/forgot-password/", payload);
  return res.data;
}

export async function resetPassword(payload) {
  // expected: { uid, token, new_password }
  const res = await http.post("/api/users/reset-password/", payload);
  return res.data;
}