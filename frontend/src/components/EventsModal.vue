<script setup lang="ts">
import { onMounted, ref } from "vue";
import { apiErrorMessage } from "@/lib/errors";
import Notice from "@/components/Notice.vue";
import { normalizeTime, timeToHhMm } from "@/lib/format";
import { listMedia, type Media } from "@/api/media";
import { createEvent, deleteEvent, listEvents, type EventItem } from "@/api/events";
import MediaPicker from "@/components/MediaPicker.vue";
import MediaThumb from "@/components/MediaThumb.vue";

const emit = defineEmits<{ close: [] }>();

const mode = ref<"list" | "add" | "confirm">("list");
const events = ref<EventItem[]>([]);
const media = ref<Media[]>([]);
const pendingDelete = ref<EventItem | null>(null);
const deleting = ref(false);
const name = ref("");
const start = ref("09:00");
const end = ref("09:03");
const mediaId = ref<number | null>(null);
const error = ref<string | null>(null);
const saving = ref(false);

function mediaById(id: number): Media | undefined {
  return media.value.find((m) => m.id === id);
}

function rangeLabel(ev: EventItem): string {
  return `${timeToHhMm(ev.start_at)} – ${timeToHhMm(ev.end_at)}`;
}

const eodHint = () => {
  const e = normalizeTime(end.value);
  return e.startsWith("23:59");
};

async function load() {
  const [ev, files] = await Promise.all([listEvents(), listMedia()]);
  events.value = ev;
  media.value = files;
}

function openAdd() {
  error.value = null;
  name.value = "";
  start.value = "09:00";
  end.value = "09:03";
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
  if (!name.value.trim() || !start.value || !end.value || mediaId.value == null) {
    error.value = "Заповніть усі поля";
    return;
  }
  saving.value = true;
  try {
    await createEvent({
      name: name.value.trim(),
      start_at: normalizeTime(start.value),
      end_at: normalizeTime(end.value),
      media_id: mediaId.value,
    });
    await load();
    mode.value = "list";
  } catch (e) {
    error.value = apiErrorMessage(e, "Не вдалося зберегти подію");
  } finally {
    saving.value = false;
  }
}

function askRemove(ev: EventItem) {
  error.value = null;
  pendingDelete.value = ev;
  mode.value = "confirm";
}

async function confirmRemove() {
  const ev = pendingDelete.value;
  if (!ev || deleting.value) return;
  deleting.value = true;
  error.value = null;
  try {
    await deleteEvent(ev.id);
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
          {{ mode === "list" ? "Події" : mode === "add" ? "Нова подія" : "Видалити подію" }}
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
          <div v-if="events.length === 0" class="p-8 text-slate-400 text-center">
            Поки що немає подій
          </div>
          <div v-for="ev in events" :key="ev.id" class="flex items-center gap-3 p-3">
            <MediaThumb :media="mediaById(ev.media_id)" />
            <div class="flex-1 min-w-0">
              <div class="font-medium truncate">{{ ev.name }}</div>
              <div class="text-xs text-slate-400">
                {{ rangeLabel(ev) }}
                <span v-if="ev.until_midnight"> · до кінця доби</span>
                · {{ ev.media_name }}
              </div>
            </div>
            <button class="btn-danger text-xs px-3 py-1.5" type="button" @click="askRemove(ev)">
              Видалити
            </button>
          </div>
        </div>
        <button class="btn-primary w-full mt-4" type="button" @click="openAdd">
          Додати
        </button>
      </div>

      <div v-else-if="mode === 'confirm'" class="p-6 space-y-4">
        <p>Видалити подію «{{ pendingDelete?.name }}»?</p>
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
          Щоденне вікно. Наприклад 09:00–09:03 або 19:00–23:59.
        </p>
        <div>
          <label class="label">Назва</label>
          <input v-model="name" class="input" autofocus />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="label">Від</label>
            <input v-model="start" type="time" class="input" />
          </div>
          <div>
            <label class="label">До</label>
            <input v-model="end" type="time" class="input" />
            <p v-if="eodHint()" class="text-xs text-slate-400 mt-1">до кінця доби</p>
          </div>
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
