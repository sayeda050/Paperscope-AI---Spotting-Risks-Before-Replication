import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export const http = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

// Attach token only when needed (skip login/register/logout endpoints)
http.interceptors.request.use((config) => {
  const url = config.url || "";

  const isAuthEndpoint =
    url.includes("/api/auth/login/") ||
    url.includes("/api/auth/logout/") ||
    url.includes("/api/auth/registration/");

  if (!isAuthEndpoint) {
    const token =
      localStorage.getItem("access_token") ||
      localStorage.getItem("token");

    if (token) {
      // dj-rest-auth default token auth uses: "Token <token>"
      config.headers.Authorization = `Token ${token}`;
    }
  }

  return config;
});

export default http;