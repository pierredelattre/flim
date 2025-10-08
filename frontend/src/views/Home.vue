<script setup>
import { onBeforeUnmount, onMounted, ref, watch, computed } from "vue";
import { useGeolocation } from "@/composables/geoloc.js";
import EmptyState from "@/components/common/EmptyState.vue";
import Toast from "@/components/feedback/Toast.vue";
import ControlsBar from "@/components/home/ControlsBar.vue";
import ResultsList from "@/components/home/ResultsList.vue";
import FilterBar from "@/components/filters/FilterBar.vue";
import FilterItem from "@/components/filters/FilterItem.vue";
import FilterDropdown from "@/components/filters/FilterDropdown.vue";
import FilterCheckboxList from "@/components/filters/FilterCheckboxList.vue";
import DatePickerNative from "@/components/filters/DatePickerNative.vue";
import DurationSelector from "@/components/filters/DurationSelector.vue";
import SortBySelector from "@/components/filters/SortBySelector.vue";
import RadiusSelector from "@/components/controls/RadiusSelector.vue";

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

const persistString = (key, value) => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(key, value);
};

const removeStoredKey = (key) => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(key);
};

const readStoredString = (key) => {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(key) || "";
};

const readStoredArray = (key) => {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const persistArray = (key, arr) => {
  if (typeof window === "undefined") {
    return;
  }
  if (!arr || arr.length === 0) {
    removeStoredKey(key);
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(arr));
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
let pendingFetchTimeoutId;

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

const scheduleDataRefresh = () => {
  if (pendingFetchTimeoutId) {
    clearTimeout(pendingFetchTimeoutId);
  }
  pendingFetchTimeoutId = setTimeout(async () => {
    try {
      const opts = lastRequestOptions.value ? { ...lastRequestOptions.value } : {};
      if (opts.forceGeolocate) {
        delete opts.forceGeolocate;
      }
      await fetchMovies(opts);
    } finally {
      pendingFetchTimeoutId = undefined;
    }
  }, 200);
};

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
const filterDate = ref(readStoredString("filters_date"));
const filterGenres = ref(readStoredArray("filters_genres"));
const filterLanguages = ref(readStoredArray("filters_languages"));
const filterSubtitles = ref(readStoredArray("filters_subtitles").map((item) => String(item).toUpperCase()));
const storedDurationMax = readStoredNumber("filters_duration_max_minutes");
const filterDurationMax = ref(Number.isNaN(storedDurationMax) ? null : storedDurationMax);
const filterSortBy = ref(readStoredString("filters_sort_by") || "relevance");
const openDropdownKey = ref(null);
const sortLabelMap = {
  distance: "Distance",
  earliest_showtime: "Première séance",
  title_asc: "Titre A→Z",
  duration_asc: "Durée croissante",
};

const toStringArray = (value) => {
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === "string" ? item.trim() : ""))
      .filter((item) => item);
  }
  if (typeof value === "string") {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item);
  }
  return [];
};

const extractMovieGenres = (movie) => toStringArray(movie?.genres ?? movie?.genre);
const extractMovieLanguages = (movie) => toStringArray(movie?.languages ?? movie?.language);

watch(radiusKm, (next, previous) => {
  if (next === previous) {
    return;
  }
  persistNumber("radius_km", next);
  showRadiusToast(next);
  scheduleDataRefresh();
});

watch(filterDate, (value) => {
  if (value) {
    persistString("filters_date", value);
  } else {
    removeStoredKey("filters_date");
  }
  scheduleDataRefresh();
});

watch(filterGenres, (value) => {
  persistArray("filters_genres", value);
  scheduleDataRefresh();
}, { deep: true });

watch(filterLanguages, (value) => {
  persistArray("filters_languages", value);
  scheduleDataRefresh();
}, { deep: true });

watch(filterSubtitles, (value) => {
  persistArray("filters_subtitles", value);
  scheduleDataRefresh();
}, { deep: true });

watch(filterDurationMax, (value) => {
  if (typeof value === "number") {
    persistNumber("filters_duration_max_minutes", value);
  } else {
    removeStoredKey("filters_duration_max_minutes");
  }
  scheduleDataRefresh();
});

watch(filterSortBy, (value) => {
  if (value && value !== "relevance") {
    persistString("filters_sort_by", value);
  } else {
    removeStoredKey("filters_sort_by");
  }
  scheduleDataRefresh();
});

// --- Time helpers to hide past showtimes ---
const now = ref(new Date());
let nowTimerId;
const availableGenres = computed(() => {
  const set = new Set();
  for (const movie of moviesNearby.value || []) {
    for (const genre of extractMovieGenres(movie)) {
      set.add(genre);
    }
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
});

const availableLanguages = computed(() => {
  const set = new Set();
  for (const movie of moviesNearby.value || []) {
    for (const language of extractMovieLanguages(movie)) {
      set.add(language);
    }
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
});

const availableSubtitles = computed(() => {
  const set = new Set();
  for (const movie of moviesNearby.value || []) {
    for (const cinema of movie?.cinemas || []) {
      for (const show of cinema?.showtimes || []) {
        if (typeof show?.diffusion_version === "string" && show.diffusion_version.trim()) {
          set.add(show.diffusion_version.trim().toUpperCase());
        }
      }
    }
  }
  return Array.from(set).sort();
});

const genreItems = computed(() =>
  availableGenres.value.map((genre) => ({
    id: genre,
    label: genre,
    checked: filterGenres.value.includes(genre),
  }))
);

const languageItems = computed(() =>
  availableLanguages.value.map((language) => ({
    id: language,
    label: language,
    checked: filterLanguages.value.includes(language),
  }))
);

const subtitleLabels = {
  ORIGINAL: "Original",
  LOCAL: "Local",
  DUBBED: "Doublé",
};

const subtitleItems = computed(() =>
  availableSubtitles.value.map((code) => ({
    id: code,
    label: subtitleLabels[code] || code,
    checked: filterSubtitles.value.includes(code),
  }))
);

const selectedDateLabel = computed(() => (filterDate.value ? filterDate.value : ""));
const selectedGenresLabel = computed(() => (filterGenres.value.length ? `${filterGenres.value.length}` : ""));
const selectedLanguagesLabel = computed(() => (filterLanguages.value.length ? `${filterLanguages.value.length}` : ""));
const selectedSubtitlesLabel = computed(() => (filterSubtitles.value.length ? `${filterSubtitles.value.length}` : ""));
const selectedDurationLabel = computed(() => (typeof filterDurationMax.value === "number" ? `${filterDurationMax.value} min` : ""));
const selectedSortLabel = computed(() => {
  if (!filterSortBy.value || filterSortBy.value === "relevance") {
    return "";
  }
  return sortLabelMap[filterSortBy.value] || filterSortBy.value;
});
const radiusLabel = computed(() => (radiusKm.value !== defaultRadius ? `${radiusKm.value} km` : ""));

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

// Compute list of movies with only future showtimes and local filter fallbacks
const upcomingMovies = computed(() => {
  const nowVal = now.value;
  if (!Array.isArray(moviesNearby.value)) return [];

  const activeDate = filterDate.value;
  const activeGenres = filterGenres.value.map((g) => g.toLowerCase());
  const hasGenreFilter = activeGenres.length > 0;
  const activeLanguages = filterLanguages.value.map((l) => l.toLowerCase());
  const hasLanguageFilter = activeLanguages.length > 0;
  const activeSubtitles = new Set(filterSubtitles.value.map((s) => s.toUpperCase()));
  const hasSubtitlesFilter = activeSubtitles.size > 0;
  const durationMax = typeof filterDurationMax.value === "number" ? filterDurationMax.value : null;
  const sortBy = filterSortBy.value || "relevance";

  const moviesWithMeta = moviesNearby.value.map((movie) => {
    let minDistance = Number.POSITIVE_INFINITY;
    let earliestTimestamp = Number.POSITIVE_INFINITY;

    const cinemas = (movie.cinemas || [])
      .map((cinema) => {
        let showtimes = (cinema.showtimes || []).filter((s) => {
          const dt = parseShowStart(s);
          return dt && dt >= nowVal;
        });

        if (activeDate) {
          showtimes = showtimes.filter((s) => s?.start_date === activeDate);
        }
        if (hasSubtitlesFilter) {
          showtimes = showtimes.filter((s) => activeSubtitles.has(String(s?.diffusion_version || "").toUpperCase()));
        }

        if (!showtimes.length) {
          return null;
        }

        const distance = typeof cinema.distance_km === "number" ? cinema.distance_km : null;
        if (distance !== null && distance < minDistance) {
          minDistance = distance;
        }

        for (const s of showtimes) {
          const dt = parseShowStart(s);
          if (dt) {
            const ts = dt.getTime();
            if (ts < earliestTimestamp) {
              earliestTimestamp = ts;
            }
          }
        }

        return { ...cinema, showtimes };
      })
      .filter((c) => c && (c.showtimes || []).length > 0);

    if (!cinemas.length) {
      return null;
    }

    if (durationMax !== null) {
      const duration = typeof movie?.duration === "number" ? movie.duration : null;
      if (duration !== null && duration > durationMax) {
        return null;
      }
    }

    if (hasLanguageFilter) {
      const movieLanguages = extractMovieLanguages(movie).map((lang) => lang.toLowerCase());
      if (movieLanguages.length) {
        const matchLanguage = activeLanguages.some((lang) => movieLanguages.includes(lang));
        if (!matchLanguage) {
          return null;
        }
      }
    }

    if (hasGenreFilter) {
      const movieGenres = extractMovieGenres(movie).map((g) => g.toLowerCase());
      if (movieGenres.length) {
        const intersects = activeGenres.some((g) => movieGenres.includes(g));
        if (!intersects) {
          return null;
        }
      }
    }

    const movieCopy = { ...movie, cinemas };

    return {
      movie: movieCopy,
      meta: {
        minDistance,
        earliestTimestamp,
      },
    };
  }).filter((entry) => entry && Array.isArray(entry.movie?.cinemas) && entry.movie.cinemas.length > 0);

  if (sortBy === "relevance") {
    return moviesWithMeta.map((entry) => entry.movie);
  }

  const sorted = [...moviesWithMeta];
  if (sortBy === "distance") {
    sorted.sort((a, b) => (a.meta.minDistance || Infinity) - (b.meta.minDistance || Infinity));
  } else if (sortBy === "earliest_showtime") {
    sorted.sort((a, b) => (a.meta.earliestTimestamp || Infinity) - (b.meta.earliestTimestamp || Infinity));
  } else if (sortBy === "title_asc") {
    sorted.sort((a, b) => {
      const titleA = String(a.movie?.title || "").toLowerCase();
      const titleB = String(b.movie?.title || "").toLowerCase();
      return titleA.localeCompare(titleB);
    });
  } else if (sortBy === "duration_asc") {
    sorted.sort((a, b) => {
      const durationA = typeof a.movie?.duration === "number" ? a.movie.duration : Number.POSITIVE_INFINITY;
      const durationB = typeof b.movie?.duration === "number" ? b.movie.duration : Number.POSITIVE_INFINITY;
      return durationA - durationB;
    });
  }

  return sorted.map((entry) => entry.movie);
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

  if (filterDate.value) {
    body.date = filterDate.value;
  }
  if (filterGenres.value.length) {
    body.genres = [...filterGenres.value];
  }
  if (filterLanguages.value.length) {
    body.languages = [...filterLanguages.value];
  }
  if (filterSubtitles.value.length) {
    body.subtitles = [...filterSubtitles.value];
  }
  if (typeof filterDurationMax.value === "number") {
    body.duration_max_minutes = filterDurationMax.value;
  }
  if (filterSortBy.value) {
    body.sort_by = filterSortBy.value;
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
  openDropdownKey.value = null;
};

const handleRadiusUpdate = (value) => {
  radiusKm.value = value;
  openDropdownKey.value = null;
};

const handleDateChange = (value) => {
  filterDate.value = value;
};

const clearDateFilter = () => {
  filterDate.value = "";
  openDropdownKey.value = null;
};

const toggleValueInList = (listRef, value, checked) => {
  const normalized = String(value);
  const current = new Set(listRef.value);
  if (checked) {
    current.add(normalized);
  } else {
    current.delete(normalized);
  }
  listRef.value = Array.from(current);
};

const handleGenresToggle = ({ id, checked }) => {
  toggleValueInList(filterGenres, id, checked);
};

const handleLanguagesToggle = ({ id, checked }) => {
  toggleValueInList(filterLanguages, id, checked);
};

const handleSubtitlesToggle = ({ id, checked }) => {
  const normalized = String(id).toUpperCase();
  toggleValueInList(filterSubtitles, normalized, checked);
};

const handleDurationChange = (value) => {
  filterDurationMax.value = value;
};

const clearDurationFilter = () => {
  filterDurationMax.value = null;
  openDropdownKey.value = null;
};

const handleSortByChange = (value) => {
  filterSortBy.value = value;
  openDropdownKey.value = null;
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
  if (pendingFetchTimeoutId) {
    clearTimeout(pendingFetchTimeoutId);
    pendingFetchTimeoutId = undefined;
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

    <FilterBar
      :openDropdownKey="openDropdownKey"
      @update:openDropdownKey="openDropdownKey = $event"
    >
      <template #date>
        <div class="filter-entry">
          <FilterItem
            label="Date"
            dropdownKey="date"
            :active="!!filterDate"
          >
            <template #value>
              <span v-if="selectedDateLabel" class="filter-item__value">{{ selectedDateLabel }}</span>
            </template>
          </FilterItem>
          <FilterDropdown dropdownKey="date">
            <DatePickerNative
              :modelValue="filterDate"
              @update:modelValue="handleDateChange"
            />
            <button type="button" @click="clearDateFilter">Effacer</button>
          </FilterDropdown>
        </div>
      </template>

      <template #genres>
        <div class="filter-entry">
          <FilterItem
            label="Genres"
            dropdownKey="genres"
            :active="filterGenres.length > 0"
          >
            <template #value>
              <span v-if="selectedGenresLabel" class="filter-item__value">{{ selectedGenresLabel }}</span>
            </template>
          </FilterItem>
          <FilterDropdown dropdownKey="genres">
            <FilterCheckboxList
              groupLabel="Genres"
              :items="genreItems"
              @toggle="handleGenresToggle"
            />
          </FilterDropdown>
        </div>
      </template>

      <template #languages>
        <div class="filter-entry">
          <FilterItem
            label="Langues"
            dropdownKey="languages"
            :active="filterLanguages.length > 0"
          >
            <template #value>
              <span v-if="selectedLanguagesLabel" class="filter-item__value">{{ selectedLanguagesLabel }}</span>
            </template>
          </FilterItem>
          <FilterDropdown dropdownKey="languages">
            <FilterCheckboxList
              groupLabel="Langues"
              :items="languageItems"
              @toggle="handleLanguagesToggle"
            />
          </FilterDropdown>
        </div>
      </template>

      <template #subtitles>
        <div class="filter-entry">
          <FilterItem
            label="Sous-titres"
            dropdownKey="subtitles"
            :active="filterSubtitles.length > 0"
          >
            <template #value>
              <span v-if="selectedSubtitlesLabel" class="filter-item__value">{{ selectedSubtitlesLabel }}</span>
            </template>
          </FilterItem>
          <FilterDropdown dropdownKey="subtitles">
            <FilterCheckboxList
              groupLabel="Sous-titres"
              :items="subtitleItems"
              @toggle="handleSubtitlesToggle"
            />
          </FilterDropdown>
        </div>
      </template>

      <template #duration>
        <div class="filter-entry">
          <FilterItem
            label="Durée"
            dropdownKey="duration"
            :active="filterDurationMax !== null"
          >
            <template #value>
              <span v-if="selectedDurationLabel" class="filter-item__value">{{ selectedDurationLabel }}</span>
            </template>
          </FilterItem>
          <FilterDropdown dropdownKey="duration">
            <DurationSelector
              :modelValue="filterDurationMax"
              @update:modelValue="handleDurationChange"
            />
            <button type="button" @click="clearDurationFilter">Réinitialiser</button>
          </FilterDropdown>
        </div>
      </template>

      <template #radius>
        <div class="filter-entry">
          <FilterItem
            label="Périmètre"
            dropdownKey="radius"
            :active="radiusKm !== defaultRadius"
          >
            <template #value>
              <span v-if="radiusLabel" class="filter-item__value">{{ radiusLabel }}</span>
            </template>
          </FilterItem>
          <FilterDropdown dropdownKey="radius">
            <RadiusSelector
              :modelValue="radiusKm"
              label="Rayon de recherche"
              @update:modelValue="handleRadiusUpdate"
            />
          </FilterDropdown>
        </div>
      </template>

      <template #sort>
        <div class="filter-entry">
          <FilterItem
            label="Trier"
            dropdownKey="sort"
            :active="filterSortBy !== 'relevance'"
          >
            <template #value>
              <span v-if="selectedSortLabel" class="filter-item__value">{{ selectedSortLabel }}</span>
            </template>
          </FilterItem>
          <FilterDropdown dropdownKey="sort">
            <SortBySelector
              :modelValue="filterSortBy"
              @update:modelValue="handleSortByChange"
            />
          </FilterDropdown>
        </div>
      </template>
    </FilterBar>

    <ResultsList v-if="upcomingMovies.length" :movies="upcomingMovies" />
    <EmptyState
      v-else-if="!loading"
      description="Aucun film avec séance à venir dans le périmètre."
    />
  </div>
</template>
