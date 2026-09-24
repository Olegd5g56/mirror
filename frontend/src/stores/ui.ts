import { defineStore } from "pinia";
import { ref } from "vue";

export const useUiStore = defineStore("ui", () => {
  const filesOpen = ref(false);
  const eventsOpen = ref(false);
  return { filesOpen, eventsOpen };
});
