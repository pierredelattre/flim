<script setup>
import { computed } from "vue";
import { formatLanguages } from "@/utils/formatters.js";

const props = defineProps({
  title: {
    type: String,
    default: "",
  },
  posterUrl: {
    type: String,
    default: "",
  },
  duration: {
    type: [Number, String],
    default: "",
  },
  director: {
    type: String,
    default: "",
  },
  synopsis: {
    type: String,
    default: "",
  },
  languages: {
    type: [String, Array],
    default: "",
  },
});

const formattedLanguages = computed(() => formatLanguages(props.languages));
</script>

<template>
  <header class="movie-header">
    <h1>{{ title }}</h1>
    <img
      v-if="posterUrl"
      :src="posterUrl"
      :alt="title"
      class="poster"
    />
    <p><strong>Durée :</strong> {{ duration ?? "?" }} min</p>
    <p v-if="formattedLanguages"><strong>Langues :</strong> {{ formattedLanguages }}</p>
    <p><strong>Réalisateur :</strong> {{ director ?? "—" }}</p>
    <p><strong>Synopsis :</strong> {{ synopsis ?? "—" }}</p>
  </header>
</template>
