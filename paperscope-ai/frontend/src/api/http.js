import axios from "axios";

// Updated to use 127.0.0.1 to match your Django ALLOWED_HOSTS
const baseURL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export const http = axios.create({
  baseURL,
  withCredentials: true, // MANDATORY: This allows the browser to send/receive cookies
  
  // ADDED: Tell Axios how to handle Django's CSRF tokens
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  
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