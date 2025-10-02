<script setup>
import { onBeforeUnmount, ref, watch } from "vue";
import { useGeolocation } from "@/composables/geoloc.js";

const { position, error: geoError, getPosition } = useGeolocation();
const moviesNearby = ref([]);
const loading = ref(false);
const fetchError = ref("");
const readStoredRadius = () => {
  if (typeof window === "undefined") {
    return NaN;
  }
  const stored = window.localStorage.getItem("radius_km");
  return stored !== null ? Number(stored) : NaN;
};
const persistRadius = (value) => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem("radius_km", String(value));
};

const storedRadius = readStoredRadius();
const defaultRadius = Number.isNaN(storedRadius) || storedRadius <= 0 ? 5 : storedRadius;
const radiusKm = ref(defaultRadius);
const radiusToast = ref("");
let toastTimeoutId;

const clearToast = () => {
  if (toastTimeoutId) {
    clearTimeout(toastTimeoutId);
    toastTimeoutId = undefined;
  }
};

const showToast = (radius) => {
  radiusToast.value = `Rayon mis à jour : ${radius} km`;
  clearToast();
  toastTimeoutId = setTimeout(() => {
    radiusToast.value = "";
    toastTimeoutId = undefined;
  }, 2000);
};

watch(radiusKm, (newVal, oldVal) => {
  if (newVal === oldVal) {
    return;
  }
  persistRadius(newVal);
  showToast(newVal);
});

onBeforeUnmount(() => {
  clearToast();
});

const fetchNearbyMovies = async () => {
  loading.value = true;
  fetchError.value = "";
  getPosition();

  const waitForPosition = () =>
    new Promise((resolve, reject) => {
      let attempts = 0;
      const check = setInterval(() => {
        const lat = position.value?.lat;
        const lng = position.value?.lng;
        if (lat != null && lng != null) {
          clearInterval(check);
          resolve({ lat: Number(lat), lng: Number(lng) });
          return;
        }
        attempts += 1;
        if (attempts >= 50) {
          clearInterval(check);
          reject(new Error("Impossible de récupérer la géolocalisation."));
        }
      }, 100);
    });

  try {
    const { lat, lng } = await waitForPosition();
    if (Number.isNaN(lat) || Number.isNaN(lng)) {
      throw new Error("Coordonnées géolocalisées invalides.");
    }
    const res = await fetch("/api/movies_nearby", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat,
        lon: lng,
        radius_km: radiusKm.value,
      }),
    });

    persistRadius(radiusKm.value);

    if (!res.ok) {
      const message = await res.text();
      throw new Error(message || `Requête échouée (${res.status})`);
    }

    const data = await res.json();
    moviesNearby.value = data.success ? data.data : [];
  } catch (err) {
    console.error("Erreur fetch:", err);
    fetchError.value = err instanceof Error ? err.message : "Erreur inconnue";
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div>
    <label>
      Rayon de recherche
      <select v-model.number="radiusKm">
        <option :value="2">2 km</option>
        <option :value="5">5 km</option>
        <option :value="10">10 km</option>
        <option :value="15">15 km</option>
        <option :value="20">20 km</option>
        <option :value="30">30 km</option>
      </select>
    </label>
    <p>Périmètre : {{ radiusKm }} km</p>
    <p v-if="radiusToast">{{ radiusToast }}</p>

    <button @click="fetchNearbyMovies" :disabled="loading">
      {{ loading ? "Chargement..." : "Chercher les films autour de moi" }}
    </button>

    <div v-if="geoError" style="color: red">{{ geoError }}</div>
    <div v-if="fetchError" style="color: red">{{ fetchError }}</div>

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
