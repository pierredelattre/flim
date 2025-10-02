<script setup>
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useGeolocation } from "@/composables/geoloc.js";

const route = useRoute();
const movieId = Number(route.params.id);

// ---------- State ----------
const movie = ref(null);
const fetchError = ref("");
const loading = ref(false);

// ---------- Geoloc helpers (aligned with Home.vue) ----------
const { position, error: geoError, getPosition } = useGeolocation();

const readStoredNumber = (key) => {
  if (typeof window === "undefined") return NaN;
  const stored = window.localStorage.getItem(key);
  return stored !== null ? Number(stored) : NaN;
};

const persistNumber = (key, value) => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, String(value));
};

const readStoredRadius = () => {
  const stored = readStoredNumber("radius_km");
  return Number.isNaN(stored) || stored <= 0 ? 5 : stored;
};

const readStoredPosition = () => {
  const lat = readStoredNumber("lat");
  const lon = readStoredNumber("lon");
  return {
    lat: Number.isNaN(lat) ? null : lat,
    lon: Number.isNaN(lon) ? null : lon,
  };
};

const persistPosition = (lat, lon) => {
  if (typeof lat !== "number" || Number.isNaN(lat) || typeof lon !== "number" || Number.isNaN(lon)) return;
  persistNumber("lat", lat);
  persistNumber("lon", lon);
};

// ---------- Radius UI ----------
const radiusKm = ref(readStoredRadius());
const radiusOptions = [2, 5, 10, 15, 20, 30];
const onRadiusChange = async () => {
  persistNumber("radius_km", radiusKm.value);
  await loadMovie(); // refetch with new radius
};

// ---------- Position wait loop ----------
const waitForPosition = async () => {
  let attempts = 0;
  const maxAttempts = 50;
  while (attempts < maxAttempts) {
    const lat = position.value?.lat;
    const lon = position.value?.lng;
    if (lat != null && lon != null) {
      const parsedLat = Number(lat);
      const parsedLon = Number(lon);
      if (!Number.isNaN(parsedLat) && !Number.isNaN(parsedLon)) {
        return { lat: parsedLat, lon: parsedLon };
      }
    }
    if (geoError.value) throw new Error(geoError.value);
    attempts += 1;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("Impossible de récupérer la géolocalisation.");
};

// ---------- Fetcher ----------
const loadMovie = async (opts = { forceGeoloc: false }) => {
  fetchError.value = "";
  loading.value = true;

  try {
    let { lat, lon } = readStoredPosition();

    if (opts.forceGeoloc || lat == null || lon == null) {
      await getPosition();
      const coords = await waitForPosition();
      lat = coords.lat;
      lon = coords.lon;
      persistPosition(lat, lon);
    }

    const body = {
      lat,
      lon,
      radius_km: radiusKm.value,
    };

    const res = await fetch(`/api/movie/${movieId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const message = await res.text();
      throw new Error(message || `Requête échouée (${res.status})`);
    }

    const data = await res.json();
    movie.value = data;
  } catch (err) {
    console.error("Erreur fetch movie:", err);
    fetchError.value = err instanceof Error ? err.message : "Erreur inconnue";
  } finally {
    loading.value = false;
  }
};

// ---------- Actions ----------
const refreshAroundMe = async () => {
  await loadMovie({ forceGeoloc: true });
};

// ---------- Lifecycle ----------
onMounted(async () => {
  await loadMovie();
});
</script>

<template>
  <div class="page">
    <!-- Errors -->
    <div v-if="geoError" class="error">{{ geoError }}</div>
    <div v-else-if="fetchError" class="error">{{ fetchError }}</div>

    <!-- Controls -->
    <div class="controls">
      <label>
        Périmètre :
        <select v-model.number="radiusKm" @change="onRadiusChange">
          <option v-for="r in radiusOptions" :key="r" :value="r">{{ r }} km</option>
        </select>
      </label>

      <button @click="refreshAroundMe">Autour de moi</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading">Chargement…</div>

    <!-- Content -->
    <div v-else-if="movie" class="movie">
      <h1>{{ movie.title }}</h1>
      <img v-if="movie.poster_url" :src="movie.poster_url" :alt="movie.title" class="poster" />
      <p><strong>Durée :</strong> {{ movie.duration ?? "?" }} min</p>
      <p><strong>Réalisateur :</strong> {{ movie.director ?? "—" }}</p>
      <p><strong>Synopsis :</strong> {{ movie.synopsis ?? "—" }}</p>

      <h2>Séances</h2>
      <div v-for="(cinema, cIdx) in (movie.cinemas || [])" :key="cinema.id ?? cIdx" class="cinema">
        <h3>
          {{ cinema.name }}
          <span v-if="typeof cinema.distance_km === 'number'">
            ({{ cinema.distance_km.toFixed(1) }} km)
          </span>
        </h3>
        <p v-if="cinema.address">{{ cinema.address }}</p>

        <ul class="showtimes">
          <li
            v-for="(show, sIdx) in (cinema.showtimes || [])"
            :key="`${cinema.id ?? cIdx}-${show.start_date ?? ''}-${show.start_time ?? ''}-${sIdx}`"
          >
            {{ show.start_date }} {{ show.start_time }}
            <span v-if="show.diffusion_version"> ({{ show.diffusion_version }})</span>
            <span v-if="show.format"> • {{ show.format }}</span>
            <a v-if="show.reservation_url" :href="show.reservation_url" target="_blank" rel="noopener noreferrer">Réserver</a>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  max-width: 920px;
  margin: 0 auto;
  padding: 16px;
}
.controls {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}
button {
  cursor: pointer;
}
.error {
  color: #b00020;
  margin-bottom: 12px;
}
.loading {
  opacity: 0.8;
}
.poster {
  max-width: 220px;
  display: block;
  margin-bottom: 12px;
}
.cinema {
  margin: 12px 0 20px;
}
.showtimes {
  margin: 8px 0 0 0;
  padding-left: 18px;
}
</style>
