<script setup lang="ts">
import type { Media } from "@/api/media";

defineProps<{
  media?: Pick<Media, "thumb_url" | "type"> | null;
}>();
</script>

<template>
  <img
    v-if="media?.thumb_url"
    :src="media.thumb_url"
    alt=""
    class="h-12 w-12 rounded object-cover bg-slate-800 shrink-0"
  />
  <div
    v-else
    class="h-12 w-12 rounded bg-slate-800 flex items-center justify-center text-xs text-slate-400 shrink-0"
  >
    {{ media?.type === "video" ? "▶" : "🖼" }}
  </div>
</template>
