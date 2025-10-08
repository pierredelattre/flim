<script setup>
import { onBeforeUnmount, onMounted, ref, watch, computed } from "vue";
import { useGeolocation } from "@/composables/geoloc.js";
import EmptyState from "@/components/common/EmptyState.vue";
import Toast from "@/components/feedback/Toast.vue";
import ControlsBar from "@/components/home/ControlsBar.vue";
import ResultsList from "@/components/home/ResultsList.vue";

const { position, error: geoError, getPosition } = useGeolocation();

const moviesNearby = ref([]);
const loading = ref(false);
const fetchError = ref("");
const lastSearchCenter = ref(null);
const lastRequestOptions = ref(null);

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
let radiusRefetchTimeoutId;

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

  // Debounce the refetch to avoid spamming the backend when the user scrolls the dropdown
  if (radiusRefetchTimeoutId) {
    clearTimeout(radiusRefetchTimeoutId);
  }
  radiusRefetchTimeoutId = setTimeout(async () => {
    try {
      // Reuse the last request context if we have one (movie/cinema/city/geolocate)
      const opts = lastRequestOptions.value ? { ...lastRequestOptions.value } : {};
      // Never force geolocation on radius change; keep current center unless explicitly requested later
      if (opts.forceGeolocate) delete opts.forceGeolocate;
      await fetchMovies(opts);
    } finally {
      radiusRefetchTimeoutId = undefined;
    }
  }, 200);
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
const controlsBarRef = ref(null);
const activeFilter = ref({ mode: "all", label: "" });
const typeLabels = {
  film: "FILM",
  cinema: "CINÉMA",
  city: "VILLE",
};
let suggestionsDebounceId;
let suppressNextSuggestionFetch = false;

// --- Time helpers to hide past showtimes ---
const now = ref(new Date());
let nowTimerId;

const parseShowStart = (show) => {
  try {
    // Prefer a direct ISO datetime if present
    if (show?.startsAt) {
      const d = new Date(show.startsAt);
      return isNaN(d) ? null : d;
      }
    // Otherwise, rebuild from date + time fields
    const dStr = show?.start_date;
    let tStr = show?.start_time;
    if (!dStr || !tStr) return null;

    // Normalize HH:MM → HH:MM:SS
    if (/^\d{2}:\d{2}$/.test(tStr)) {
      tStr = tStr + ":00";
    }
    const iso = `${dStr}T${tStr}`;
    const d = new Date(iso);
    return isNaN(d) ? null : d;
  } catch {
    return null;
  }
};

// Compute list of movies with only future showtimes
const upcomingMovies = computed(() => {
  const nowVal = now.value;
  if (!Array.isArray(moviesNearby.value)) return [];

  return moviesNearby.value
    .map((movie) => {
      const cinemas = (movie.cinemas || [])
        .map((cinema) => {
          const showtimes = (cinema.showtimes || []).filter((s) => {
            const dt = parseShowStart(s);
            return dt && dt >= nowVal;
          });
          return { ...cinema, showtimes };
        })
        .filter((c) => (c.showtimes || []).length > 0); // keep cinemas that still have future showtimes

      return { ...movie, cinemas };
    })
    .filter((m) => (m.cinemas || []).length > 0); // keep movies that still have at least one future showtime
});

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
  const searchBoxComponent = controlsBarRef.value?.searchBox ?? null;
  const containerEl = searchBoxComponent?.container?.value ?? null;
  if (!containerEl) {
    return;
  }
  if (!containerEl.contains(event.target)) {
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

const resetToAll = async () => {
  // Clear UI state
  searchQuery.value = "";
  closeSuggestions();
  activeFilter.value = { mode: "all", label: "" };
  lastSearchCenter.value = null;
  lastRequestOptions.value = null;

  // Re-fetch around current geolocated position
  await fetchMovies({ forceGeolocate: true });
};

const fetchMovies = async (options = {}) => {
  loading.value = true;
  fetchError.value = "";

  const optionsToRemember = { ...options };
  if (optionsToRemember.forceGeolocate) delete optionsToRemember.forceGeolocate;

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
    lastRequestOptions.value = optionsToRemember;
  } catch (error) {
    console.error("Erreur fetch:", error);
    fetchError.value = error instanceof Error ? error.message : "Erreur inconnue";
  } finally {
    loading.value = false;
  }
};

const fetchNearbyMovies = async () => {
  await fetchMovies({ forceGeolocate: true });
  lastRequestOptions.value = {}; // reset to default geolocate-based search
};

const selectSuggestion = async (suggestion) => {
  closeSuggestions();
  suppressNextSuggestionFetch = true;
  searchQuery.value = suggestion.label;
  activeFilter.value = { mode: suggestion.type, label: suggestion.label };

  if (suggestion.type === "film") {
    await fetchMovies({ movieId: Number(suggestion.id) });
    lastRequestOptions.value = { movieId: Number(suggestion.id) };
    return;
  }
  if (suggestion.type === "cinema") {
    await fetchMovies({ cinemaId: Number(suggestion.id) });
    lastRequestOptions.value = { cinemaId: Number(suggestion.id) };
    return;
  }
  if (suggestion.type === "city") {
    if (typeof suggestion.lat !== "number" || typeof suggestion.lon !== "number") {
      fetchError.value = "Coordonnées ville indisponibles";
      return;
    }
    await fetchMovies({ overrideLocation: true, centerLat: suggestion.lat, centerLon: suggestion.lon });
    lastRequestOptions.value = { overrideLocation: true, centerLat: suggestion.lat, centerLon: suggestion.lon };
  }
};

const handleSearchInput = (value) => {
  searchQuery.value = value;
};

const handleOpenSuggestions = () => {
  openSuggestions();
};

const handleSearchKeydown = (event) => {
  onSearchKeydown(event);
};

const handleSelectSuggestion = (suggestion) => {
  selectSuggestion(suggestion);
};

const handleFetchNearby = () => {
  fetchNearbyMovies();
};

const handleRadiusUpdate = (value) => {
  radiusKm.value = value;
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
  nowTimerId = setInterval(() => {
    now.value = new Date();
  }, 60_000);
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
  if (nowTimerId) {
    clearInterval(nowTimerId);
    nowTimerId = undefined;
  }
  if (radiusRefetchTimeoutId) {
    clearTimeout(radiusRefetchTimeoutId);
    radiusRefetchTimeoutId = undefined;
  }
});
</script>

<template>
  <div class="home">
    <h1 class="text-3xl font-bold text-blue-600">Flim</h1>
    <ControlsBar
      ref="controlsBarRef"
      :loading="loading"
      :radiusKm="radiusKm"
      :typeLabels="typeLabels"
      :searchQuery="searchQuery"
      :suggestions="suggestions"
      :isSuggestionsOpen="isSuggestionsOpen"
      :highlightIndex="highlightIndex"
      :backVisible="activeFilter.mode !== 'all'"
      @reset="resetToAll"
      @search-input="handleSearchInput"
      @open-suggestions="handleOpenSuggestions"
      @keydown="handleSearchKeydown"
      @select-suggestion="handleSelectSuggestion"
      @fetch-nearby="handleFetchNearby"
      @update:radiusKm="handleRadiusUpdate"
    />

    <Toast :message="radiusToast" />

    <ResultsList v-if="upcomingMovies.length" :movies="upcomingMovies" />
    <EmptyState
      v-else-if="!loading"
      description="Aucun film avec séance à venir dans le périmètre."
    />
  </div>
</template>
