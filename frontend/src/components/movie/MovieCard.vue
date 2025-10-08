<script setup>
import { computed } from "vue";
import CinemaBlock from "@/components/movie/CinemaBlock.vue";

const props = defineProps({
  movie: {
    type: Object,
    required: true,
  },
});

const hasId = computed(() => typeof props.movie?.id === "number" || typeof props.movie?.id === "string");
</script>

<template>
  <div class="movie">
    <h2>{{ movie.title }}</h2>
    <img
      v-if="movie.poster"
      :src="movie.poster"
      :alt="movie.title"
      width="100"
    />

    <div>
      <router-link
        v-if="hasId"
        :to="{ name: 'Movie', params: { id: movie.id } }"
      >
        <button type="button">Voir toutes les séances</button>
      </router-link>
      <button
        v-else
        type="button"
        disabled
        title="Identifiant film indisponible"
      >
        Voir toutes les séances
      </button>
    </div>

    <div class="cinemas">
      <CinemaBlock
        v-for="cinema in movie.cinemas || []"
        :key="cinema.id ?? cinema.name"
        :cinema="cinema"
      />
    </div>
  </div>
</template>
