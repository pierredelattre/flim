<script setup>
import { ref } from "vue";
import { useGeolocation } from "@/composables/geoloc.js";

const { position, error, getPosition } = useGeolocation();
const moviesNearby = ref([]);
const loading = ref(false);

const fetchNearbyMovies = async () => {
  loading.value = true;
  getPosition();

  const waitForPosition = () =>
    new Promise((resolve) => {
      const check = setInterval(() => {
        if (position.value.lat && position.value.lng) {
          clearInterval(check);
          resolve();
        }
      }, 100);
    });

  await waitForPosition();

  try {
    const res = await fetch("/api/movies_nearby", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat: position.value.lat,
        lon: position.value.lng,
        radius_km: 5,
      }),
    });

    const data = await res.json();
    moviesNearby.value = data.success ? data.data : [];
  } catch (err) {
    console.error("Erreur fetch:", err);
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div>
    <button @click="fetchNearbyMovies" :disabled="loading">
      {{ loading ? "Chargement..." : "Chercher les films autour de moi" }}
    </button>

    <div v-if="error" style="color: red">{{ error }}</div>

    <div v-if="moviesNearby.length" id="results">
      <div v-for="movie in moviesNearby" :key="movie.title">
        <h2>{{ movie.title }}</h2>
        <img v-if="movie.poster" :src="movie.poster" :alt="movie.title" width="100" />

        <router-link :to="{ name: 'Movie', params: { id: movie.id } }">
          <button>Voir toutes les séances</button>
        </router-link>

        <div>
          <div class="results__cinema" v-for="cinema in movie.cinemas" :key="cinema.id">
            <strong>{{ cinema.name }}</strong>
            ({{ cinema.distance_km ? cinema.distance_km.toFixed(2) : "?" }} km)
            <p>{{ cinema.address }}</p>
 
            <div>
              <div class="results__cinema__seance" v-for="(show, index) in (cinema.showtimes || [])" :key="index">
                {{ show.start_date }} {{ show.start_time }} ({{ show.diffusion_version || "" }})
                <a v-if="show.reservation_url" :href="show.reservation_url" target="_blank">Réserver</a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <p v-else-if="!loading">Aucun film trouvé dans le périmètre.</p>
  </div>
</template>