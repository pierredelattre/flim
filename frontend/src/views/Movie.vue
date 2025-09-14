<script setup>
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useGeolocation } from "@/composables/geoloc.js";

const route = useRoute();
const movieId = route.params.id;

const movie = ref(null);

const { position, error, getPosition } = useGeolocation();

onMounted(async () => {
  await getPosition();

  let attempts = 0;
  while (
    (
      !position.value ||
      position.value.lat == null ||
      position.value.lng == null ||
      isNaN(parseFloat(position.value.lat)) ||
      isNaN(parseFloat(position.value.lng))
    )
    && attempts < 50
  ) {
    await new Promise(resolve => setTimeout(resolve, 100));
    attempts++;
  }

  let lat = parseFloat(position.value?.lat);
  let lon = parseFloat(position.value?.lng);

  if (isNaN(lat) || isNaN(lon)) {
    console.warn("Invalid geolocation data, using fallback coordinates.");
    lat = 50.63;
    lon = 3.06;
  }

  const body = {
    lat: lat,
    lon: lon,
    radius_km: 5
  };

  const res = await fetch(`/api/movie/${movieId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await res.json();
  movie.value = data;
});


</script>

<template>
  <div v-if="movie">
    <h1>{{ movie.title }}</h1>
    <img :src="movie.poster_url" :alt="movie.title" />
    <p><strong>Durée :</strong> {{ movie.duration }} min</p>
    <p><strong>Réalisateur :</strong> {{ movie.director }}</p>
    <p><strong>Synopsis :</strong> {{ movie.synopsis }}</p>

    <h2>Séances</h2>
    <div v-for="cinema in movie.cinemas" :key="cinema.id">
      <h3>{{ cinema.name }} ({{ cinema.distance_km?.toFixed(1) }} km)</h3>
      <p>{{ cinema.address }}</p>
      <ul>
        <li v-for="show in cinema.showtimes" :key="show.start_date + show.start_time">
          {{ show.start_date }} {{ show.start_time }} ({{ show.diffusion_version }})
          <a v-if="show.reservation_url" :href="show.reservation_url" target="_blank">Réserver</a>
        </li>
      </ul>
    </div>
  </div>
</template>