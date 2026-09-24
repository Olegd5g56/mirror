import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common["Authorization"];
  }
}

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      const url = err.config?.url ?? "";
      if (!url.endsWith("/auth/login")) {
        localStorage.removeItem("mirror.token");
        if (location.pathname !== "/login" && location.pathname !== "/screen") {
          location.assign("/login");
        }
      }
    }
    return Promise.reject(err);
  },
);
