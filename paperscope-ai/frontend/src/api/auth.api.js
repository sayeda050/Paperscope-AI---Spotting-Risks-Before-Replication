import http from "./http";


// dj-rest-auth endpoints
export async function registerUser(payload) {
  // expected: { username, email, password1, password2 }
  const res = await http.post("/api/auth/registration/", payload);
  return res.data;
}


export async function loginUser(payload) {
  // expected: { username, password }
  // (username can be email too if your backend supports it via allauth)
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
// NEW ADDITION FOR GOOGLE LOGIN
// ==========================================
export async function googleLoginUser(payload) {
  const res = await http.post("/api/users/google/", payload);
  return res.data;
}
