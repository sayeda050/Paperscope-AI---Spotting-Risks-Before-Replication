import axios from "axios";

// Updated to use localhost to match your browser's domain
const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const http = axios.create({
  baseURL,
  withCredentials: true, // MANDATORY: This allows the browser to send/receive cookies
  headers: { 
    "Content-Type": "application/json" 
  },
});

// We no longer need to manually attach tokens from localStorage 
// because the browser handles the "paperscope-auth" cookie for us.
http.interceptors.request.use((config) => {
  return config;
}, (error) => {
  return Promise.reject(error);
});

export default http;