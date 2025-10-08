<script setup>
import MovieCard from "@/components/movie/MovieCard.vue";

const props = defineProps({
  movies: {
    type: Array,
    default: () => [],
  },
});
</script>

<template>
  <div id="results" v-if="movies.length">
    <MovieCard
      v-for="movie in movies"
      :key="movie.id ?? movie.title"
      :movie="movie"
    />
  </div>
</template>
