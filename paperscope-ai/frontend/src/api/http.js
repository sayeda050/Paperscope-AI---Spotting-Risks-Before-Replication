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
  // Force JSON parsing of every response — protects against backends that
  // return a JSON body with the wrong Content-Type (e.g. text/plain).
  responseType: "json",
  headers: {
    Accept: "application/json",
  },
});

http.interceptors.request.use(
  (config) => {
    const method = (config.method || "get").toUpperCase();
    const csrftoken = getCookie("csrftoken");

    config.headers = config.headers || {};

    // Always advertise we accept JSON back
    if (!config.headers["Accept"]) {
      config.headers["Accept"] = "application/json";
    }

    // Force JSON Content-Type whenever the body is a plain object (NOT FormData,
    // NOT a string, NOT a Blob/Buffer). This prevents proxies / interceptors
    // from defaulting to text/plain on cross-origin POSTs.
    const isFormData = config.data instanceof FormData;
    const isPlainObject =
      config.data &&
      typeof config.data === "object" &&
      !isFormData &&
      !(config.data instanceof Blob) &&
      !(config.data instanceof ArrayBuffer);

    if (isPlainObject) {
      config.headers["Content-Type"] = "application/json";
    }

    if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && csrftoken) {
      config.headers["X-CSRFToken"] = csrftoken;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Defensive response interceptor — if a server ever returns a JSON-shaped
// string (Content-Type: text/plain with valid JSON inside), parse it so the
// rest of the app receives a real object. Idempotent on already-parsed bodies.
http.interceptors.response.use(
  (response) => {
    if (typeof response.data === "string") {
      try {
        response.data = JSON.parse(response.data);
      } catch (_) {
        // not JSON — leave as string
      }
    }
    return response;
  },
  (error) => {
    if (error?.response && typeof error.response.data === "string") {
      try {
        error.response.data = JSON.parse(error.response.data);
      } catch (_) {
        // leave as string
      }
    }
    return Promise.reject(error);
  }
);

export default http;
