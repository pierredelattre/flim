<script setup>
const props = defineProps({
  message: {
    type: String,
    default: "",
  },
});
</script>

<template>
  <div v-if="message" class="toast" role="status" aria-live="polite">
    {{ message }}
  </div>
</template>
