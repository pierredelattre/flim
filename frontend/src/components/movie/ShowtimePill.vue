<script setup>
import { computed } from "vue";
import { formatDiffusionVersion } from "@/utils/formatters.js";

const props = defineProps({
  show: {
    type: Object,
    required: true,
  },
});

const formattedVersion = computed(() => formatDiffusionVersion(props.show?.diffusion_version));
</script>

<template>
  <div class="showtime">
    {{ show.start_date }} {{ show.start_time }}
    <span v-if="formattedVersion"> ({{ formattedVersion }})</span>
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
