<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useAuthStore } from "@/stores/auth";
import { uploadRejectReason, useUploadQueue } from "@/composables/useUploadQueue";
import Notice from "@/components/Notice.vue";
import { apiErrorMessage } from "@/lib/errors";
import { deleteMedia, listMedia, type Media } from "@/api/media";
import MediaThumb from "@/components/MediaThumb.vue";

const emit = defineEmits<{ close: []; changed: [] }>();

const auth = useAuthStore();
const mode = ref<"list" | "add" | "confirm">("list");
const files = ref<Media[]>([]);
const pendingDelete = ref<Media | null>(null);
const deleting = ref(false);
const name = ref("");
const file = ref<File | null>(null);
const error = ref<string | null>(null);
const dragging = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
let poll: number | undefined;

const { items: uploads, hasActive, addFile } = useUploadQueue({
  getToken: () => auth.token,
  onUploaded: () => load(),
});

const visibleUploads = computed(() => uploads.value.filter((it) => it.status !== "success"));

const busy = computed(() =>
  files.value.some((m) => m.status === "pending" || m.status === "processing" || m.status === "converting"),
);

async function load() {
  files.value = await listMedia();
  const names = new Set(files.value.map((m) => m.name));
  uploads.value = uploads.value.filter((it) => it.status !== "success" || !names.has(it.name));
}

function openAdd() {
  error.value = null;
  name.value = "";
  file.value = null;
  dragging.value = false;
  if (fileInput.value) fileInput.value.value = "";
  mode.value = "add";
}

function backToList() {
  error.value = null;
  pendingDelete.value = null;
  deleting.value = false;
  mode.value = "list";
}

function takeFile(f: File) {
  error.value = null;
  const reason = uploadRejectReason(f);
  if (reason) {
    file.value = null;
    if (fileInput.value) fileInput.value.value = "";
    error.value = reason;
    return;
  }
  file.value = f;
  if (!name.value.trim()) name.value = f.name.replace(/\.[^/.]+$/, "");
}

function onPick(e: Event) {
  const input = e.target as HTMLInputElement;
  const f = input.files?.[0];
  if (f) takeFile(f);
}

function onDrop(e: DragEvent) {
  dragging.value = false;
  const f = e.dataTransfer?.files?.[0];
  if (f) takeFile(f);
}

function upload() {
  error.value = null;
  if (!file.value || !name.value.trim()) {
    error.value = "Заповніть назву і виберіть файл";
    return;
  }
  const trimmed = name.value.trim();
  const nameTaken =
    files.value.some((m) => m.name === trimmed) ||
    uploads.value.some((it) => it.name === trimmed && it.status !== "error" && it.status !== "cancelled");
  if (nameTaken) {
    error.value = "Назва вже зайнята";
    return;
  }
  const reason = uploadRejectReason(file.value);
  if (reason) {
    error.value = reason;
    return;
  }
  if (!auth.token) {
    error.value = "Немає токена авторизації";
    return;
  }
  addFile(file.value, trimmed);
  file.value = null;
  name.value = "";
  if (fileInput.value) fileInput.value.value = "";
  mode.value = "list";
}

function askRemove(m: Media) {
  error.value = null;
  pendingDelete.value = m;
  mode.value = "confirm";
}

async function confirmRemove() {
  const m = pendingDelete.value;
  if (!m || deleting.value) return;
  deleting.value = true;
  error.value = null;
  try {
    await deleteMedia(m.id);
    emit("changed");
    pendingDelete.value = null;
    mode.value = "list";
    await load();
  } catch (e) {
    error.value = apiErrorMessage(e, "Не вдалося видалити");
  } finally {
    deleting.value = false;
  }
}

function preview(m: Media) {
  if (m.air_url) window.open(m.air_url, "_blank");
}

function statusLabel(m: Media): string {
  if (m.status === "ready") return "";
  if (m.status === "failed") return "помилка обробки";
  if (m.status === "converting") return `обробка ${m.progress}%`;
  return "обробка…";
}

onMounted(async () => {
  await load();
  poll = window.setInterval(() => {
    if (busy.value || hasActive.value) load();
  }, 2000);
});

onUnmounted(() => {
  if (poll) window.clearInterval(poll);
});
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal-panel">
      <div class="relative flex items-center justify-center px-6 py-4 border-b border-slate-700 min-h-[3.5rem]">
        <button
          v-if="mode !== 'list'"
          class="absolute left-4 btn-ghost px-3 py-1.5 text-sm"
          type="button"
          @click="backToList"
        >
          ← Назад
        </button>
        <h2 class="text-lg font-semibold text-center">
          {{ mode === "list" ? "Файли" : mode === "add" ? "Новий файл" : "Видалити файл" }}
        </h2>
        <button
          class="absolute right-4 text-2xl text-slate-400 hover:text-white leading-none"
          type="button"
          @click="emit('close')"
        >
          ×
        </button>
      </div>

      <div v-if="mode === 'list'" class="p-6">
        <Notice v-if="error" class="mb-3" :message="error" />
        <div v-if="visibleUploads.length" class="mb-4 space-y-3">
          <div v-for="it in visibleUploads" :key="it.id" class="text-sm">
            <div class="flex justify-between text-slate-300 mb-1 gap-3">
              <span class="truncate">{{ it.name }}</span>
              <span v-if="it.status !== 'error'" class="shrink-0">{{ it.progress }}%</span>
            </div>
            <Notice v-if="it.status === 'error' && it.error" :message="it.error" />
            <div v-else class="h-2 rounded bg-slate-700 overflow-hidden">
              <div class="h-full bg-blue-500" :style="{ width: it.progress + '%' }" />
            </div>
          </div>
        </div>
        <div class="divide-y divide-slate-700 max-h-[28rem] overflow-y-auto rounded-lg border border-slate-700">
          <div v-if="files.length === 0" class="p-8 text-slate-400 text-center">
            Поки що немає файлів
          </div>
          <div v-for="m in files" :key="m.id" class="flex items-center gap-3 p-3">
            <MediaThumb :media="m" />
            <div class="flex-1 min-w-0">
              <div class="font-medium truncate">{{ m.name }}</div>
              <div class="text-xs text-slate-400">
                {{ m.type === "video" ? "відео" : "зображення" }}
                <span v-if="statusLabel(m)"> · {{ statusLabel(m) }}</span>
              </div>
            </div>
            <button
              class="btn-ghost text-xs px-3 py-1.5"
              type="button"
              :disabled="!m.air_url"
              @click="preview(m)"
            >
              Переглянути
            </button>
            <button class="btn-danger text-xs px-3 py-1.5" type="button" @click="askRemove(m)">
              Видалити
            </button>
          </div>
        </div>
        <button class="btn-primary w-full mt-4" type="button" @click="openAdd">
          Додати
        </button>
      </div>

      <div v-else-if="mode === 'confirm'" class="p-6 space-y-4">
        <p v-if="pendingDelete && (pendingDelete.used_in_events || pendingDelete.used_in_schedule)">
          Файл «{{ pendingDelete.name }}» використовується і буде видалений з усіх місць, де він стоїть.
        </p>
        <p v-else>Видалити «{{ pendingDelete?.name }}»?</p>
        <Notice v-if="error" :message="error" />
        <div class="flex gap-3 justify-end">
          <button class="btn-ghost" type="button" :disabled="deleting" @click="backToList">
            Скасувати
          </button>
          <button class="btn-danger" type="button" :disabled="deleting" @click="confirmRemove">
            {{ deleting ? "Видалення…" : "Видалити" }}
          </button>
        </div>
      </div>

      <div v-else class="p-6 space-y-4">
        <p class="text-sm text-slate-400">
          JPEG, PNG, WebP або відео MP4, WebM, MOV.
        </p>
        <div>
          <label class="label">Назва</label>
          <input v-model="name" class="input" placeholder="меню" autofocus />
        </div>
        <input
          ref="fileInput"
          type="file"
          class="sr-only"
          accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime"
          @change="onPick"
        />
        <div
          class="rounded-xl border-2 border-dashed px-4 py-8 text-center cursor-pointer transition"
          :class="dragging ? 'border-blue-400 bg-blue-500/10 text-slate-200' : error ? 'border-red-400/80 bg-red-500/5 text-slate-300' : 'border-slate-600 text-slate-400 hover:border-slate-400'"
          @dragover.prevent="dragging = true"
          @dragleave="dragging = false"
          @drop.prevent="onDrop"
          @click="fileInput?.click()"
        >
          <div v-if="file" class="text-slate-100 font-medium">{{ file.name }}</div>
          <div v-else>Перетягніть файл сюди або натисніть, щоб обрати</div>
        </div>
        <Notice v-if="error" :message="error" />
        <div class="flex gap-3 justify-end">
          <button class="btn-ghost" type="button" @click="backToList">Скасувати</button>
          <button class="btn-primary" type="button" @click="upload">Завантажити</button>
        </div>
      </div>
    </div>
  </div>
</template>
