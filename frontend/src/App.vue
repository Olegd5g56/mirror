<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import AppHeader from "@/components/AppHeader.vue";

const route = useRoute();
const showHeader = computed(() => route.meta.layout !== "bare");
</script>

<template>
  <div class="h-full flex flex-col">
    <AppHeader v-if="showHeader" />
    <main class="flex-1 min-h-0">
      <router-view />
    </main>
  </div>
</template>
