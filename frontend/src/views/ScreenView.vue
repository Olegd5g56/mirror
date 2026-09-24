<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import Notice from "@/components/Notice.vue";

const CHECK_INTERVAL = 5000;
const currentPath = ref<string | null>(null);
const currentType = ref<"image" | "video" | null>(null);
const error = ref<string | null>(null);
let timer: number | undefined;

async function check() {
  try {
    const res = await fetch("/api/now");
    if (!res.ok) throw new Error(String(res.status));
    const data = (await res.json()) as { type: "image" | "video"; path: string };
    error.value = null;
    if (data.path !== currentPath.value) {
      currentPath.value = data.path;
      currentType.value = data.type;
    }
  } catch {
    error.value = "Помилка з'єднання з сервером";
  }
}

onMounted(() => {
  check();
  timer = window.setInterval(check, CHECK_INTERVAL);
});

onUnmounted(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<template>
  <div class="fixed inset-0 bg-black overflow-hidden">
    <video
      v-if="currentType === 'video' && currentPath"
      :key="currentPath"
      class="absolute inset-0 h-full w-full object-contain bg-black"
      :src="'/' + currentPath"
      autoplay
      muted
      loop
      playsinline
    />
    <img
      v-else-if="currentType === 'image' && currentPath"
      :key="currentPath"
      class="absolute inset-0 h-full w-full object-contain bg-black"
      :src="'/' + currentPath"
      alt=""
    />
    <div
      v-else
      class="absolute inset-0 flex items-center justify-center text-white text-lg"
    >
      Завантаження…
    </div>
    <div
      v-if="error"
      class="absolute inset-0 flex items-center justify-center p-6 bg-black/55"
    >
      <Notice class="max-w-md" :message="error" />
    </div>
  </div>
</template>
