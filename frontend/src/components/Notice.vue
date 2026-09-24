<script setup lang="ts">
defineProps<{ message: string }>();
</script>

<template>
  <div class="notice" role="alert">
    <svg class="notice-mark" viewBox="0 0 20 20" aria-hidden="true">
      <path
        fill="currentColor"
        d="M10 1.6a8.4 8.4 0 1 0 0 16.8 8.4 8.4 0 0 0 0-16.8Zm0 3.9a.95.95 0 0 1 .95.95v4.3a.95.95 0 1 1-1.9 0V6.45A.95.95 0 0 1 10 5.5Zm0 8.55a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Z"
      />
    </svg>
    <p>{{ message }}</p>
  </div>
</template>
