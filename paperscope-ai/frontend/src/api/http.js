import axios from "axios";

const baseURL =
  import.meta.env.VITE_API_BASE_URL ||
  `http://${window.location.hostname}:8000`;

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return parts.pop().split(";").shift();
  }
  return "";
}

export const http = axios.create({
  baseURL,
  withCredentials: true,
});

http.interceptors.request.use(
  (config) => {
    const method = (config.method || "get").toUpperCase();
    const csrftoken = getCookie("csrftoken");

    config.headers = config.headers || {};

    // Never force JSON for FormData uploads
    if (!(config.data instanceof FormData) && !config.headers["Content-Type"]) {
      config.headers["Content-Type"] = "application/json";
    }

    // Send Django CSRF header for unsafe methods
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && csrftoken) {
      config.headers["X-CSRFToken"] = csrftoken;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

export default http;