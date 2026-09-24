<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import Notice from "@/components/Notice.vue";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const username = ref("");
const password = ref("");

onMounted(() => {
  if (auth.token) router.replace({ name: "calendar" });
});

function safeRedirect(raw: unknown): string {
  if (typeof raw !== "string" || raw.length === 0) return "/";
  if (raw[0] !== "/" || raw.startsWith("//")) return "/";
  return raw;
}

async function submit() {
  try {
    await auth.login(username.value.trim(), password.value);
    router.replace(safeRedirect(route.query.redirect));
  } catch {
    /* auth.error */
  }
}
</script>

<template>
  <div class="min-h-full flex items-center justify-center px-4">
    <form
      class="login-card w-full rounded-2xl border border-slate-600/50 bg-slate-900/90 shadow-2xl"
      @submit.prevent="submit"
    >
      <h1 class="text-4xl font-bold text-center mb-8">Mirror</h1>

      <div class="field">
        <input
          id="username"
          v-model="username"
          type="text"
          placeholder=" "
          autocomplete="username"
          required
          autofocus
        />
        <label for="username">Логін</label>
      </div>

      <div class="field field-last">
        <input
          id="password"
          v-model="password"
          type="password"
          placeholder=" "
          autocomplete="current-password"
          required
        />
        <label for="password">Пароль</label>
      </div>

      <button type="submit" class="btn-primary login-submit w-full" :disabled="auth.loading">
        {{ auth.loading ? "Вхід…" : "Увійти" }}
      </button>

      <Notice v-if="auth.error" class="mt-5" :message="auth.error" />
    </form>
  </div>
</template>

<style scoped>
.login-card {
  max-width: 32rem;
  padding: 3rem 2.75rem 2.75rem;
}
.login-submit {
  padding: 0.95rem 1.25rem;
  font-size: 1.05rem;
  border-radius: 0.9rem;
}
.field {
  position: relative;
  margin-bottom: 1rem;
}
.field-last {
  margin-bottom: 1.75rem;
}
.field input {
  display: block;
  width: 100%;
  height: 4rem;
  box-sizing: border-box;
  border-radius: 0.65rem;
  border: 1px solid rgb(71 85 105);
  background-color: rgb(30 41 59 / 0.8);
  color: rgb(241 245 249);
  font-size: 1rem;
  line-height: 1.5rem;
  padding: 1.7rem 1rem 0.4rem;
}
.field input::placeholder {
  color: transparent;
}
.field input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px #3b82f6;
}
.field input:-webkit-autofill {
  -webkit-text-fill-color: rgb(241 245 249);
  caret-color: rgb(241 245 249);
  box-shadow: 0 0 0 1000px rgb(30 41 59) inset;
}
.field label {
  position: absolute;
  left: 1rem;
  top: 50%;
  color: rgb(148 163 184);
  font-size: 1rem;
  line-height: 1.5rem;
  pointer-events: none;
  transform: translateY(-50%);
  transform-origin: left center;
  transition: transform 150ms ease;
}
.field input:focus + label,
.field input:not(:placeholder-shown) + label,
.field input:autofill + label,
.field input:-webkit-autofill + label {
  transform: translateY(calc(-50% - 1rem)) scale(0.75);
}
</style>
