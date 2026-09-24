<script setup lang="ts">
import { onMounted, ref } from "vue";
import { apiErrorMessage } from "@/lib/errors";
import Notice from "@/components/Notice.vue";
import { formatTime, normalizeTime } from "@/lib/format";
import { listMedia, type Media } from "@/api/media";
import { createSchedule, deleteSchedule, listSchedule, type ScheduleItem } from "@/api/schedule";
import MediaPicker from "@/components/MediaPicker.vue";
import MediaThumb from "@/components/MediaThumb.vue";

const props = defineProps<{ date: string }>();
const emit = defineEmits<{ close: []; changed: [] }>();

const mode = ref<"list" | "add" | "confirm">("list");
const items = ref<ScheduleItem[]>([]);
const media = ref<Media[]>([]);
const pendingDelete = ref<ScheduleItem | null>(null);
const deleting = ref(false);
const time = ref("08:00");
const mediaId = ref<number | null>(null);
const error = ref<string | null>(null);
const saving = ref(false);

const title = props.date.split("-").reverse().join(".");

function mediaById(id: number): Media | undefined {
  return media.value.find((m) => m.id === id);
}

async function load() {
  const [sch, files] = await Promise.all([
    listSchedule({ date: props.date }),
    listMedia(),
  ]);
  items.value = sch;
  media.value = files;
}

function openAdd() {
  error.value = null;
  time.value = "08:00";
  const first = media.value.find((m) => m.status === "ready");
  mediaId.value = first ? first.id : null;
  mode.value = "add";
}

function backToList() {
  error.value = null;
  pendingDelete.value = null;
  deleting.value = false;
  mode.value = "list";
}

async function add() {
  error.value = null;
  if (!time.value || mediaId.value == null) {
    error.value = "Заповніть усі поля";
    return;
  }
  saving.value = true;
  try {
    await createSchedule({
      media_id: mediaId.value,
      start_at: `${props.date}T${normalizeTime(time.value)}`,
    });
    await load();
    emit("changed");
    mode.value = "list";
  } catch (e) {
    error.value = apiErrorMessage(e, "Не вдалося додати слот");
  } finally {
    saving.value = false;
  }
}

function askRemove(it: ScheduleItem) {
  error.value = null;
  pendingDelete.value = it;
  mode.value = "confirm";
}

async function confirmRemove() {
  const it = pendingDelete.value;
  if (!it || deleting.value) return;
  deleting.value = true;
  error.value = null;
  try {
    await deleteSchedule(it.id);
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

onMounted(load);
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
          {{ mode === "list" ? title : mode === "add" ? "Новий слот" : "Видалити слот" }}
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
        <div class="divide-y divide-slate-700 max-h-[28rem] overflow-y-auto rounded-lg border border-slate-700">
          <div v-if="items.length === 0" class="p-8 text-slate-400 text-center">
            На цей день поки немає файлів
          </div>
          <div v-for="it in items" :key="it.id" class="flex items-center gap-3 p-3">
            <MediaThumb :media="mediaById(it.media_id)" />
            <div class="flex-1 min-w-0">
              <div class="font-medium truncate">{{ it.media_name }}</div>
              <div class="text-xs text-slate-400">{{ formatTime(it.start_at) }}</div>
            </div>
            <button class="btn-danger text-xs px-3 py-1.5" type="button" @click="askRemove(it)">
              Видалити
            </button>
          </div>
        </div>
        <button class="btn-primary w-full mt-4" type="button" @click="openAdd">
          Додати
        </button>
      </div>

      <div v-else-if="mode === 'confirm'" class="p-6 space-y-4">
        <p>
          Видалити слот «{{ pendingDelete?.media_name }}» о {{ pendingDelete ? formatTime(pendingDelete.start_at) : "" }}?
        </p>
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
          Грає з цього часу до наступного слота цього дня або до півночі.
        </p>
        <div>
          <label class="label">Час</label>
          <input v-model="time" type="time" class="input max-w-xs" />
        </div>
        <div>
          <label class="label">Файл</label>
          <MediaPicker v-model="mediaId" :items="media" />
        </div>
        <Notice v-if="error" :message="error" />
        <div class="flex gap-3 justify-end">
          <button class="btn-ghost" type="button" @click="backToList">Скасувати</button>
          <button class="btn-primary" type="button" :disabled="saving" @click="add">
            {{ saving ? "Збереження…" : "Зберегти" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
