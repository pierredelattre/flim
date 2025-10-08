<script setup>
import ShowtimePill from "@/components/movie/ShowtimePill.vue";

const props = defineProps({
  showtimes: {
    type: Array,
    default: () => [],
  },
});
</script>

<template>
  <div class="showtimes">
    <ShowtimePill
      v-for="(show, index) in showtimes"
      :key="`${show.start_date ?? ''}-${show.start_time ?? ''}-${index}`"
      :show="show"
    />
  </div>
</template>
