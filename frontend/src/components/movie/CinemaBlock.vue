<script setup>
import { computed } from "vue";
import ShowtimesList from "@/components/movie/ShowtimesList.vue";

const props = defineProps({
  cinema: {
    type: Object,
    required: true,
  },
  distancePrecision: {
    type: Number,
    default: 2,
  },
});

const formattedDistance = computed(() => {
  if (typeof props.cinema?.distance_km !== "number") {
    return null;
  }
  return props.cinema.distance_km.toFixed(props.distancePrecision);
});
</script>

<template>
  <div class="cinema">
    <strong>{{ cinema.name }}</strong>
    <span v-if="formattedDistance !== null">
      ({{ formattedDistance }} km)
    </span>
    <span v-else>(? km)</span>
    <p v-if="cinema.address">{{ cinema.address }}</p>

    <ShowtimesList :showtimes="cinema.showtimes || []" />
  </div>
</template>
