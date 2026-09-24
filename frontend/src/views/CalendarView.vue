<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import FilesModal from "@/components/FilesModal.vue";
import EventsModal from "@/components/EventsModal.vue";
import ScheduleModal from "@/components/ScheduleModal.vue";
import { listSchedule, type ScheduleItem } from "@/api/schedule";
import {
  DAY_NAMES,
  MONTH_NAMES,
  daysInMonth,
  isoDate,
  kyivDateKey,
  kyivParts,
  mondayIndexOfFirst,
} from "@/lib/format";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();
const nowKyiv = kyivParts();
const viewYear = ref(nowKyiv.year);
const viewMonth = ref(nowKyiv.month);
const items = ref<ScheduleItem[]>([]);
const selectedDate = ref<string | null>(null);
const todayKey = kyivDateKey(new Date());

const title = computed(() => `${MONTH_NAMES[viewMonth.value - 1]} ${viewYear.value}`);

const byDate = computed(() => {
  const map: Record<string, ScheduleItem[]> = {};
  for (const it of items.value) {
    const key = kyivDateKey(new Date(it.start_at));
    (map[key] ??= []).push(it);
  }
  return map;
});

const cells = computed(() => {
  const year = viewYear.value;
  const month = viewMonth.value;
  const startDay = mondayIndexOfFirst(year, month);
  const last = daysInMonth(year, month);
  const out: { date: string | null; day: number | null; count: number; today: boolean }[] = [];
  for (let i = 0; i < startDay; i++) {
    out.push({ date: null, day: null, count: 0, today: false });
  }
  for (let day = 1; day <= last; day++) {
    const date = isoDate(year, month, day);
    out.push({
      date,
      day,
      count: byDate.value[date]?.length ?? 0,
      today: date === todayKey,
    });
  }
  return out;
});

async function load() {
  const from = isoDate(viewYear.value, viewMonth.value, 1);
  const to = isoDate(viewYear.value, viewMonth.value, daysInMonth(viewYear.value, viewMonth.value));
  items.value = await listSchedule({ from, to });
}

function prev() {
  if (viewMonth.value === 1) {
    viewMonth.value = 12;
    viewYear.value -= 1;
  } else {
    viewMonth.value -= 1;
  }
  load();
}
function next() {
  if (viewMonth.value === 12) {
    viewMonth.value = 1;
    viewYear.value += 1;
  } else {
    viewMonth.value += 1;
  }
  load();
}

onMounted(load);
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="px-6 py-4 flex items-center gap-4">
      <button class="btn-ghost" type="button" @click="prev">← Попер</button>
      <div class="flex-1 text-center text-2xl font-bold">{{ title }}</div>
      <button class="btn-ghost" type="button" @click="next">Наст →</button>
    </div>

    <div
      class="flex-1 min-h-0 mx-6 mb-6 grid grid-cols-7 auto-rows-fr gap-0.5 rounded-2xl overflow-hidden bg-slate-800/60 shadow-2xl"
      style="grid-template-rows: auto repeat(6, minmax(0, 1fr))"
    >
      <div
        v-for="d in DAY_NAMES"
        :key="d"
        class="text-center font-bold py-3 text-white"
        style="background: linear-gradient(135deg, #3b82f6, #8b5cf6)"
      >
        {{ d }}
      </div>
      <button
        v-for="(c, i) in cells"
        :key="i"
        type="button"
        class="relative text-left p-3 min-h-[72px] border border-slate-700/40 transition flex flex-col"
        :class="
          !c.date
            ? 'bg-slate-900/40'
            : 'bg-slate-700/80 hover:bg-blue-500/20 cursor-pointer'
        "
        :disabled="!c.date"
        :aria-current="c.today ? 'date' : undefined"
        @click="c.date && (selectedDate = c.date)"
      >
        <span v-if="c.today" class="day-mark" aria-hidden="true" />
        <div
          v-if="c.day"
          class="inline-flex h-9 w-9 items-center justify-center text-xl font-bold leading-none"
          :class="c.today && 'rounded-full text-white'"
          :style="c.today ? 'background: linear-gradient(135deg, #3b82f6, #8b5cf6)' : undefined"
        >
          {{ c.day }}
        </div>
        <div
          v-if="c.count"
          class="mt-auto inline-block text-xs font-semibold text-white rounded-full px-2.5 py-0.5"
          style="background: linear-gradient(135deg, #3b82f6, #8b5cf6)"
        >
          {{ c.count }}
        </div>
      </button>
    </div>

    <FilesModal v-if="ui.filesOpen" @close="ui.filesOpen = false" @changed="load" />
    <EventsModal v-if="ui.eventsOpen" @close="ui.eventsOpen = false" />
    <ScheduleModal
      v-if="selectedDate"
      :date="selectedDate"
      @close="selectedDate = null"
      @changed="load"
    />
  </div>
</template>
