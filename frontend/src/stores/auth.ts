import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api, setAuthToken } from "@/api/client";
import { apiErrorMessage } from "@/lib/errors";

export interface User {
  id: string;
  username: string;
  created_at: string;
}

interface LoginResponse {
  token: string;
  user: User;
}

const TOKEN_KEY = "mirror.token";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(null);
  const user = ref<User | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const isAuthenticated = computed(() => Boolean(token.value));

  function restoreFromStorage() {
    const t = localStorage.getItem(TOKEN_KEY);
    if (t) {
      token.value = t;
      setAuthToken(t);
    }
  }

  async function login(username: string, password: string) {
    loading.value = true;
    error.value = null;
    try {
      const { data } = await api.post<LoginResponse>("/auth/login", {
        username,
        password,
      });
      token.value = data.token;
      user.value = data.user;
      localStorage.setItem(TOKEN_KEY, data.token);
      setAuthToken(data.token);
    } catch (e: unknown) {
      error.value = apiErrorMessage(e, "Помилка входу");
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function fetchMe() {
    const { data } = await api.get<User>("/auth/me");
    user.value = data;
  }

  async function logout() {
    try {
      await api.post("/auth/logout");
    } catch {
      /* local cleanup anyway */
    }
    token.value = null;
    user.value = null;
    localStorage.removeItem(TOKEN_KEY);
    setAuthToken(null);
  }

  return {
    token,
    user,
    loading,
    error,
    isAuthenticated,
    restoreFromStorage,
    login,
    fetchMe,
    logout,
  };
});
