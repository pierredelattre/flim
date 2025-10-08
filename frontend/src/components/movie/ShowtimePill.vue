<script setup>
const props = defineProps({
  show: {
    type: Object,
    required: true,
  },
});
</script>

<template>
  <div class="showtime">
    {{ show.start_date }} {{ show.start_time }}
    <span v-if="show.diffusion_version"> ({{ show.diffusion_version }})</span>
    <span v-if="show.format"> • {{ show.format }}</span>
    <a
      v-if="show.reservation_url"
      :href="show.reservation_url"
      target="_blank"
      rel="noopener noreferrer"
    >
      Réserver
    </a>
  </div>
</template>
