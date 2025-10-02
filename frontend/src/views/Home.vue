<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useGeolocation } from "@/composables/geoloc.js";

const { position, error: geoError, getPosition } = useGeolocation();

const moviesNearby = ref([]);
const loading = ref(false);
const fetchError = ref("");
const lastSearchCenter = ref(null);

const readStoredNumber = (key) => {
  if (typeof window === "undefined") {
    return NaN;
  }
  const stored = window.localStorage.getItem(key);
  return stored !== null ? Number(stored) : NaN;
};

const persistNumber = (key, value) => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(key, String(value));
};

const readStoredRadius = () => {
  const storedRadius = readStoredNumber("radius_km");
  return Number.isNaN(storedRadius) || storedRadius <= 0 ? 5 : storedRadius;
};

const readStoredPosition = () => {
  const lat = readStoredNumber("lat");
  const lon = readStoredNumber("lon");
  return {
    lat: Number.isNaN(lat) ? null : lat,
    lon: Number.isNaN(lon) ? null : lon,
  };
};

const defaultRadius = readStoredRadius();
const radiusKm = ref(defaultRadius);
const currentPosition = ref(readStoredPosition());
const radiusToast = ref("");
let radiusToastTimeoutId;

const clearRadiusToast = () => {
  if (radiusToastTimeoutId) {
    clearTimeout(radiusToastTimeoutId);
    radiusToastTimeoutId = undefined;
  }
};

const showRadiusToast = (radius) => {
  radiusToast.value = `Rayon mis à jour : ${radius} km`;
  clearRadiusToast();
  radiusToastTimeoutId = setTimeout(() => {
    radiusToast.value = "";
    radiusToastTimeoutId = undefined;
  }, 2000);
};

watch(radiusKm, (next, previous) => {
  if (next === previous) {
    return;
  }
  persistNumber("radius_km", next);
  showRadiusToast(next);
});

const formatCoordinate = (value) => {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "?";
  }
  return value.toFixed(4);
};

const suggestions = ref([]);
const searchQuery = ref("");
const isSuggestionsOpen = ref(false);
const highlightIndex = ref(-1);
const searchContainer = ref(null);
const typeLabels = {
  film: "FILM",
  cinema: "CINÉMA",
  city: "VILLE",
};
let suggestionsDebounceId;
let suppressNextSuggestionFetch = false;

const resetSuggestions = () => {
  suggestions.value = [];
  highlightIndex.value = -1;
};

const closeSuggestions = () => {
  isSuggestionsOpen.value = false;
  resetSuggestions();
};

const openSuggestions = () => {
  if (suggestions.value.length) {
    isSuggestionsOpen.value = true;
  }
};

const fetchSuggestions = async (term) => {
  const query = term.trim();
  if (!query) {
    closeSuggestions();
    return;
  }

  try {
    const response = await fetch(`/api/search_suggest?q=${encodeURIComponent(query)}&limit=10`);
    if (!response.ok) {
      throw new Error(`Suggestion request failed (${response.status})`);
    }
    const payload = await response.json();

    // Accept multiple shapes:
    //  - [ ... ]
    //  - { data: [...] }
    //  - { results: [...] }
    //  - { suggestions: [...] }
    const rawList = Array.isArray(payload)
      ? payload
      : Array.isArray(payload?.data)
        ? payload.data
        : Array.isArray(payload?.results)
          ? payload.results
          : Array.isArray(payload?.suggestions)
            ? payload.suggestions
            : [];

    const normalized = rawList.map((it) => {
      const id =
        (typeof it.id === "number" || typeof it.id === "string") ? Number(it.id) :
        (typeof it.movie_id === "number" || typeof it.movie_id === "string") ? Number(it.movie_id) :
        (typeof it.cinema_id === "number" || typeof it.cinema_id === "string") ? Number(it.cinema_id) :
        (typeof it.city_id === "number" || typeof it.city_id === "string") ? Number(it.city_id) :
        undefined;

      const label = it.label ?? it.title ?? it.name ?? it.city ?? "";
      const sublabel = it.sublabel ?? it.original_title ?? it.zipcode ?? it.postal_code ?? "";
      // Normalize backend variations: "movie" -> "film"
      let type = it.type ?? it.category;
      if (!type) {
        if (typeof it.lat === "number" && typeof it.lon === "number" && (it.city || it.zipcode || it.postal_code)) {
          type = "city";
        } else if (it.title || it.original_title) {
          type = "film";
        } else if (it.name) {
          type = "cinema";
        }
      }
      if (type === "movie") type = "film";

      const lat = (typeof it.lat === "number") ? it.lat : null;
      const lon = (typeof it.lon === "number") ? it.lon : null;

      return { id, label, sublabel, type, lat, lon };
    }).filter((x) => x.id != null && x.label);

    suggestions.value = normalized;
    if (suggestions.value.length > 0) {
      highlightIndex.value = 0;
      isSuggestionsOpen.value = true;
    } else {
      highlightIndex.value = -1;
      isSuggestionsOpen.value = false;
    }
  } catch (error) {
    console.error("Erreur suggestions:", error);
    closeSuggestions();
  }
};

watch(
  searchQuery,
  (value) => {
    if (suppressNextSuggestionFetch) {
      suppressNextSuggestionFetch = false;
      return;
    }

    if (suggestionsDebounceId) {
      clearTimeout(suggestionsDebounceId);
    }

    suggestionsDebounceId = setTimeout(() => {
      fetchSuggestions(value);
    }, 250);
  },
  { flush: "post" }
);

const handleClickOutside = (event) => {
  if (!searchContainer.value) {
    return;
  }
  if (!searchContainer.value.contains(event.target)) {
    closeSuggestions();
  }
};

const waitForPosition = () =>
  new Promise((resolve, reject) => {
    let attempts = 0;
    const maxAttempts = 50;
    const interval = setInterval(() => {
      const lat = position.value?.lat;
      const lon = position.value?.lng;
      if (lat != null && lon != null) {
        clearInterval(interval);
        resolve({ lat: Number(lat), lon: Number(lon) });
        return;
      }
      if (geoError.value) {
        clearInterval(interval);
        reject(new Error(geoError.value));
        return;
      }
      attempts += 1;
      if (attempts >= maxAttempts) {
        clearInterval(interval);
        reject(new Error("Impossible de récupérer la géolocalisation."));
      }
    }, 100);
  });

const persistPosition = (lat, lon) => {
  if (typeof lat !== "number" || Number.isNaN(lat) || typeof lon !== "number" || Number.isNaN(lon)) {
    return;
  }
  persistNumber("lat", lat);
  persistNumber("lon", lon);
  currentPosition.value = { lat, lon };
};

const resolveLocation = async ({ forceGeolocate = false } = {}) => {
  const storedLat = currentPosition.value?.lat;
  const storedLon = currentPosition.value?.lon;

  if (!forceGeolocate && typeof storedLat === "number" && typeof storedLon === "number") {
    return { lat: storedLat, lon: storedLon };
  }

  try {
    if (geoError.value) {
      geoError.value = null;
    }
    getPosition();
    const coords = await waitForPosition();
    persistPosition(coords.lat, coords.lon);
    return coords;
  } catch (error) {
    throw error instanceof Error ? error : new Error("Géolocalisation indisponible");
  }
};

const buildMoviesRequestBody = async (options = {}) => {
  const body = {
    radius_km: radiusKm.value,
  };

  if (options.overrideLocation) {
    body.override_location = true;
    body.center_lat = options.centerLat;
    body.center_lon = options.centerLon;
    if (typeof currentPosition.value?.lat === "number" && typeof currentPosition.value?.lon === "number") {
      body.lat = currentPosition.value.lat;
      body.lon = currentPosition.value.lon;
    }
  } else {
    const { lat, lon } = await resolveLocation({ forceGeolocate: options.forceGeolocate });
    body.lat = lat;
    body.lon = lon;
  }

  if (typeof options.movieId === "number") {
    body.movie_id = options.movieId;
  }
  if (typeof options.cinemaId === "number") {
    body.cinema_id = options.cinemaId;
  }

  return body;
};

const applySearchCenter = (lat, lon) => {
  if (typeof lat === "number" && typeof lon === "number") {
    persistPosition(lat, lon);
    lastSearchCenter.value = { lat, lon };
  }
};

const fetchMovies = async (options = {}) => {
  loading.value = true;
  fetchError.value = "";

  try {
    const body = await buildMoviesRequestBody(options);
    const response = await fetch("/api/movies_nearby", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Requête échouée (${response.status})`);
    }

    const data = await response.json();
    // Accept either a plain array or a shape like { success, data: [...] } or { movies: [...] }
    const payload = data;
    const list = Array.isArray(payload)
      ? payload
      : Array.isArray(payload?.data)
        ? payload.data
        : Array.isArray(payload?.movies)
          ? payload.movies
          : [];

    moviesNearby.value = list;

    if (typeof data?.center_lat === "number" && typeof data?.center_lon === "number") {
      applySearchCenter(data.center_lat, data.center_lon);
    } else if (options.overrideLocation) {
      applySearchCenter(options.centerLat, options.centerLon);
    } else if (typeof body.lat === "number" && typeof body.lon === "number") {
      applySearchCenter(body.lat, body.lon);
    }
  } catch (error) {
    console.error("Erreur fetch:", error);
    fetchError.value = error instanceof Error ? error.message : "Erreur inconnue";
  } finally {
    loading.value = false;
  }
};

const fetchNearbyMovies = async () => {
  await fetchMovies({ forceGeolocate: true });
};

const selectSuggestion = async (suggestion) => {
  closeSuggestions();
  suppressNextSuggestionFetch = true;
  searchQuery.value = suggestion.label;

  if (suggestion.type === "film") {
    await fetchMovies({ movieId: Number(suggestion.id) });
    return;
  }
  if (suggestion.type === "cinema") {
    await fetchMovies({ cinemaId: Number(suggestion.id) });
    return;
  }
  if (suggestion.type === "city") {
    if (typeof suggestion.lat !== "number" || typeof suggestion.lon !== "number") {
      fetchError.value = "Coordonnées ville indisponibles";
      return;
    }
    await fetchMovies({ overrideLocation: true, centerLat: suggestion.lat, centerLon: suggestion.lon });
  }
};

const onSearchKeydown = (event) => {
  if (!isSuggestionsOpen.value || !suggestions.value.length) {
    if (event.key === "Enter") {
      event.preventDefault();
    }
    return;
  }

  if (event.key === "ArrowDown") {
    event.preventDefault();
    highlightIndex.value = (highlightIndex.value + 1) % suggestions.value.length;
    return;
  }

  if (event.key === "ArrowUp") {
    event.preventDefault();
    highlightIndex.value = highlightIndex.value <= 0
      ? suggestions.value.length - 1
      : highlightIndex.value - 1;
    return;
  }

  if (event.key === "Enter") {
    event.preventDefault();
    const selected = suggestions.value[highlightIndex.value] ?? suggestions.value[0];
    if (selected) {
      selectSuggestion(selected);
    }
    return;
  }

  if (event.key === "Escape") {
    event.preventDefault();
    closeSuggestions();
  }
};

onMounted(() => {
  document.addEventListener("click", handleClickOutside);
  if (typeof currentPosition.value?.lat === "number" && typeof currentPosition.value?.lon === "number") {
    fetchMovies();
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleClickOutside);
  clearRadiusToast();
  if (suggestionsDebounceId) {
    clearTimeout(suggestionsDebounceId);
    suggestionsDebounceId = undefined;
  }
});
</script>

<template>
  <div class="home">
    <div class="controls">
      <div class="search" ref="searchContainer">
        <input
          type="search"
          v-model="searchQuery"
          placeholder="Rechercher un film, un cinéma ou une ville"
          @focus="openSuggestions"
          @keydown="onSearchKeydown"
          role="combobox"
          aria-autocomplete="list"
          :aria-expanded="isSuggestionsOpen ? 'true' : 'false'"
          aria-haspopup="listbox"
          aria-controls="suggestions-list"
          :aria-activedescendant="isSuggestionsOpen && highlightIndex >= 0 && suggestions[highlightIndex] ? `sugg-${suggestions[highlightIndex].type}-${suggestions[highlightIndex].id}` : undefined"
        />
        <ul
          v-if="isSuggestionsOpen && suggestions.length"
          class="suggestions"
          id="suggestions-list"
          role="listbox"
        >
          <li
            v-for="(item, index) in suggestions"
            :key="`${item.type}-${item.id}`"
            :id="`sugg-${item.type}-${item.id}`"
            role="option"
            :aria-selected="index === highlightIndex ? 'true' : 'false'"
            :class="{ highlighted: index === highlightIndex }"
            @mousedown.prevent="selectSuggestion(item)"
          >
            <span class="suggestion__tag">{{ typeLabels[item.type] ?? item.type }}</span>
            <span class="suggestion__label">{{ item.label }}</span>
            <span v-if="item.sublabel" class="suggestion__sublabel">{{ item.sublabel }}</span>
          </li>
        </ul>
      </div>

      <button @click="fetchNearbyMovies" :disabled="loading">
        {{ loading ? "Chargement..." : "Autour de moi" }}
      </button>

      <label class="radius">
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
    </div>

    <div v-if="moviesNearby.length" id="results">
      <div v-for="movie in moviesNearby" :key="movie.id ?? movie.title" class="movie">
        <h2>{{ movie.title }}</h2>
        <img v-if="movie.poster" :src="movie.poster" :alt="movie.title" width="100" />

        <div>
          <router-link v-if="movie.id" :to="{ name: 'Movie', params: { id: movie.id } }">
            <button>Voir toutes les séances</button>
          </router-link>
          <button v-else disabled title="Identifiant film indisponible">Voir toutes les séances</button>
        </div>

        <div class="cinemas">
          <div class="cinema" v-for="cinema in movie.cinemas" :key="cinema.id">
            <strong>{{ cinema.name }}</strong>
            <span>
              ({{ typeof cinema.distance_km === "number" ? cinema.distance_km.toFixed(2) : "?" }} km)
            </span>
            <p v-if="cinema.address">{{ cinema.address }}</p>

            <div class="showtimes">
              <div class="showtime" v-for="(show, index) in cinema.showtimes" :key="index">
                {{ show.start_date }} {{ show.start_time }}
                <span v-if="show.diffusion_version"> ({{ show.diffusion_version }})</span>
                <span v-if="show.format"> • {{ show.format }}</span>
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

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-start;
}

.search {
  position: relative;
  flex: 1 1 260px;
  max-width: 480px;
}

.search input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.suggestions {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  max-height: 320px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.1);
  z-index: 10;
  list-style: none;
  margin: 0;
  padding: 0;
}

.suggestions li {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
}

.suggestions li.highlighted,
.suggestions li:hover {
  background-color: #f2f2f2;
}

.suggestion__tag {
  font-size: 0.7rem;
  font-weight: 600;
  color: #555;
  border: 1px solid #bbb;
  border-radius: 999px;
  padding: 0.1rem 0.45rem;
}

.suggestion__label {
  font-weight: 600;
}

.suggestion__sublabel {
  font-size: 0.85rem;
  color: #666;
}

.radius {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.toast {
  color: #2b6cb0;
}

.error {
  color: #c53030;
}

.search-info {
  font-size: 0.9rem;
  color: #555;
}

.movie {
  border: 1px solid #e2e2e2;
  padding: 1rem;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.cinemas {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.cinema {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.showtimes {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.showtime {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.showtime a {
  color: #2b6cb0;
}
</style>
