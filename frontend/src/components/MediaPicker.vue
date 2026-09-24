<script setup lang="ts">
import { computed } from "vue";
import type { Media } from "@/api/media";
import MediaThumb from "@/components/MediaThumb.vue";

const props = defineProps<{
  items: Media[];
  modelValue: number | null;
}>();

const emit = defineEmits<{
  "update:modelValue": [number];
}>();

const ready = computed(() => props.items.filter((m) => m.status === "ready"));
</script>

<template>
  <div class="divide-y divide-slate-700 max-h-56 overflow-y-auto rounded-lg border border-slate-700">
    <div v-if="ready.length === 0" class="p-4 text-slate-400 text-center text-sm">
      Немає готових файлів
    </div>
    <button
      v-for="m in ready"
      :key="m.id"
      type="button"
      class="w-full flex items-center gap-3 p-2 text-left transition"
      :class="
        modelValue === m.id
          ? 'bg-blue-500/20 ring-1 ring-inset ring-blue-400'
          : 'hover:bg-slate-800/80'
      "
      @click="emit('update:modelValue', m.id)"
    >
      <MediaThumb :media="m" />
      <div class="flex-1 min-w-0">
        <div class="font-medium truncate">{{ m.name }}</div>
        <div class="text-xs text-slate-400">
          {{ m.type === "video" ? "відео" : "зображення" }}
        </div>
      </div>
    </button>
  </div>
</template>
