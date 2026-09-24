<script setup lang="ts">
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";
import { useRouter } from "vue-router";

const auth = useAuthStore();
const ui = useUiStore();
const router = useRouter();

async function doLogout() {
  await auth.logout();
  router.push({ name: "login" });
}

function openScreen() {
  window.open("/screen", "_blank");
}
</script>

<template>
  <header class="border-b border-slate-600/30 bg-slate-950/40">
    <div class="relative px-6 py-3 flex items-center justify-center">
      <nav class="nav-seg" aria-label="Розділи">
        <button
          class="nav-seg-btn"
          :class="ui.filesOpen && 'nav-seg-btn-active'"
          type="button"
          @click="ui.filesOpen = true"
        >
          <svg class="h-4 w-4 opacity-80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
          </svg>
          Файли
        </button>
        <span class="w-px self-stretch bg-slate-600/40 my-1" />
        <button
          class="nav-seg-btn"
          :class="ui.eventsOpen && 'nav-seg-btn-active'"
          type="button"
          @click="ui.eventsOpen = true"
        >
          <svg class="h-4 w-4 opacity-80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="5" width="18" height="16" rx="2" />
            <path d="M3 10h18M8 3v4M16 3v4" />
          </svg>
          Події
        </button>
        <span class="w-px self-stretch bg-slate-600/40 my-1" />
        <button class="nav-seg-btn" type="button" @click="openScreen">
          <svg class="h-4 w-4 opacity-80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="4" width="20" height="14" rx="2" />
            <path d="M8 20h8M12 18v2" />
          </svg>
          Екран
        </button>
      </nav>

      <button
        class="absolute right-6 text-sm text-slate-400 hover:text-white transition-colors px-2 py-1"
        type="button"
        @click="doLogout"
      >
        Вийти
      </button>
    </div>
  </header>
</template>
