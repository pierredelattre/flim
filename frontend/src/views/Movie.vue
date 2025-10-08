<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useGeolocation } from "@/composables/geoloc.js";
import GeoButton from "@/components/controls/GeoButton.vue";
import RadiusSelector from "@/components/controls/RadiusSelector.vue";
import MovieHeader from "@/components/movie/MovieHeader.vue";
import CinemaBlock from "@/components/movie/CinemaBlock.vue";
import FilterBar from "@/components/filters/FilterBar.vue";
import FilterItem from "@/components/filters/FilterItem.vue";
import FilterDropdown from "@/components/filters/FilterDropdown.vue";
import FilterCheckboxList from "@/components/filters/FilterCheckboxList.vue";
import DatePickerNative from "@/components/filters/DatePickerNative.vue";
import DurationSelector from "@/components/filters/DurationSelector.vue";
import SortBySelector from "@/components/filters/SortBySelector.vue";

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

const persistString = (key, value) => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, value);
};

const removeStoredKey = (key) => {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(key);
};

const readStoredString = (key) => {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(key) || "";
};

const readStoredArray = (key) => {
  if (typeof window === "undefined") return [];
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
  if (typeof window === "undefined") return;
  if (!arr || arr.length === 0) {
    removeStoredKey(key);
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(arr));
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
const defaultRadius = readStoredRadius();
const radiusKm = ref(defaultRadius);
let pendingReloadTimeoutId;
const scheduleMovieRefresh = (options) => {
  if (pendingReloadTimeoutId) {
    clearTimeout(pendingReloadTimeoutId);
  }
  pendingReloadTimeoutId = setTimeout(async () => {
    try {
      await loadMovie(options ?? {});
    } finally {
      pendingReloadTimeoutId = undefined;
    }
  }, 200);
};

const handleRadiusUpdate = (value) => {
  radiusKm.value = value;
  persistNumber("radius_km", radiusKm.value);
  openDropdownKey.value = null;
  scheduleMovieRefresh();
};
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

const extractMovieGenres = (movieValue) => toStringArray(movieValue?.genres ?? movieValue?.genre);
const extractMovieLanguages = (movieValue) => toStringArray(movieValue?.languages ?? movieValue?.language);

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

watch(filterDate, (value) => {
  if (value) {
    persistString("filters_date", value);
  } else {
    removeStoredKey("filters_date");
  }
  scheduleMovieRefresh();
});

watch(filterGenres, (value) => {
  persistArray("filters_genres", value);
  scheduleMovieRefresh();
}, { deep: true });

watch(filterLanguages, (value) => {
  persistArray("filters_languages", value);
  scheduleMovieRefresh();
}, { deep: true });

watch(filterSubtitles, (value) => {
  persistArray("filters_subtitles", value);
  scheduleMovieRefresh();
}, { deep: true });

watch(filterDurationMax, (value) => {
  if (typeof value === "number") {
    persistNumber("filters_duration_max_minutes", value);
  } else {
    removeStoredKey("filters_duration_max_minutes");
  }
  scheduleMovieRefresh();
});

watch(filterSortBy, (value) => {
  if (value && value !== "relevance") {
    persistString("filters_sort_by", value);
  } else {
    removeStoredKey("filters_sort_by");
  }
  scheduleMovieRefresh();
});

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
  toggleValueInList(filterSubtitles, String(id).toUpperCase(), checked);
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

const parseShowStart = (show) => {
  try {
    if (show?.startsAt) {
      const d = new Date(show.startsAt);
      return isNaN(d) ? null : d;
    }
    const dStr = show?.start_date;
    let tStr = show?.start_time;
    if (!dStr || !tStr) return null;
    if (/^\d{2}:\d{2}$/.test(tStr)) {
      tStr = `${tStr}:00`;
    }
    const iso = `${dStr}T${tStr}`;
    const d = new Date(iso);
    return isNaN(d) ? null : d;
  } catch {
    return null;
  }
};

const filteredMovie = computed(() => {
  if (!movie.value) return null;

  const nowRef = new Date();
  const activeDate = filterDate.value;
  const activeSubtitles = new Set(filterSubtitles.value.map((s) => s.toUpperCase()));
  const hasSubtitlesFilter = activeSubtitles.size > 0;
  const durationMax = typeof filterDurationMax.value === "number" ? filterDurationMax.value : null;
  const activeGenres = filterGenres.value.map((g) => g.toLowerCase());
  const hasGenreFilter = activeGenres.length > 0;
  const activeLanguages = filterLanguages.value.map((l) => l.toLowerCase());
  const hasLanguageFilter = activeLanguages.length > 0;
  const sortBy = filterSortBy.value || "relevance";

  let passesDuration = true;
  if (durationMax !== null) {
    const duration = typeof movie.value.duration === "number" ? movie.value.duration : null;
    if (duration !== null && duration > durationMax) {
      passesDuration = false;
    }
  }

  let passesLanguage = true;
  if (hasLanguageFilter) {
    const movieLanguages = extractMovieLanguages(movie.value).map((lang) => lang.toLowerCase());
    if (movieLanguages.length) {
      const matchesLanguage = activeLanguages.some((lang) => movieLanguages.includes(lang));
      if (!matchesLanguage) {
        passesLanguage = false;
      }
    }
  }

  let passesGenre = true;
  if (hasGenreFilter) {
    const normalized = extractMovieGenres(movie.value).map((g) => g.toLowerCase());
    if (normalized.length) {
      const intersects = activeGenres.some((g) => normalized.includes(g));
      if (!intersects) {
        passesGenre = false;
      }
    }
  }

  const cinemasWithMeta = (movie.value.cinemas || [])
    .map((cinema) => {
      let earliestTimestamp = Number.POSITIVE_INFINITY;
      let showtimes = (cinema.showtimes || []).filter((show) => {
        const dt = parseShowStart(show);
        return dt && dt >= nowRef;
      });

      if (activeDate) {
        showtimes = showtimes.filter((show) => show?.start_date === activeDate);
      }
      if (hasSubtitlesFilter) {
        showtimes = showtimes.filter((show) => activeSubtitles.has(String(show?.diffusion_version || "").toUpperCase()));
      }

      if (!showtimes.length) {
        return null;
      }

      for (const show of showtimes) {
        const dt = parseShowStart(show);
        if (dt) {
          const ts = dt.getTime();
          if (ts < earliestTimestamp) {
            earliestTimestamp = ts;
          }
        }
      }

      const distance = typeof cinema.distance_km === "number" ? cinema.distance_km : Number.POSITIVE_INFINITY;

      return {
        cinema: { ...cinema, showtimes },
        meta: {
          earliestTimestamp,
          distance,
        },
      };
    })
    .filter((entry) => entry !== null);

  let filteredCinemas = cinemasWithMeta;

  if (!passesDuration || !passesLanguage || !passesGenre) {
    filteredCinemas = [];
  }

  if (sortBy === "distance") {
    filteredCinemas = [...filteredCinemas].sort((a, b) => (a.meta.distance ?? Number.POSITIVE_INFINITY) - (b.meta.distance ?? Number.POSITIVE_INFINITY));
  } else if (sortBy === "earliest_showtime") {
    filteredCinemas = [...filteredCinemas].sort((a, b) => (a.meta.earliestTimestamp ?? Number.POSITIVE_INFINITY) - (b.meta.earliestTimestamp ?? Number.POSITIVE_INFINITY));
  }

  return {
    ...movie.value,
    cinemas: filteredCinemas.map((entry) => entry.cinema),
  };
});

const hasFilteredShowtimes = computed(() => (filteredMovie.value?.cinemas || []).length > 0);
const availableGenres = computed(() => {
  const set = new Set();
  for (const genre of extractMovieGenres(movie.value)) {
    set.add(genre);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
});

const availableLanguages = computed(() => {
  const languages = extractMovieLanguages(movie.value);
  return Array.from(new Set(languages)).sort((a, b) => a.localeCompare(b));
});

const availableSubtitles = computed(() => {
  const set = new Set();
  for (const cinema of movie.value?.cinemas || []) {
    for (const show of cinema?.showtimes || []) {
      if (typeof show?.diffusion_version === "string" && show.diffusion_version.trim()) {
        set.add(show.diffusion_version.trim().toUpperCase());
      }
    }
  }
  return Array.from(set).sort();
});

const subtitleLabels = {
  ORIGINAL: "Original",
  LOCAL: "Local",
  DUBBED: "Doublé",
};

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

// ---------- Actions ----------
const refreshAroundMe = async () => {
  if (pendingReloadTimeoutId) {
    clearTimeout(pendingReloadTimeoutId);
    pendingReloadTimeoutId = undefined;
  }
  openDropdownKey.value = null;
  await loadMovie({ forceGeoloc: true });
};

// ---------- Lifecycle ----------
onMounted(async () => {
  await loadMovie();
});

onBeforeUnmount(() => {
  if (pendingReloadTimeoutId) {
    clearTimeout(pendingReloadTimeoutId);
    pendingReloadTimeoutId = undefined;
  }
});
</script>

<template>
  <div class="page">
    <!-- Errors -->
    <div v-if="geoError" class="error">{{ geoError }}</div>
    <div v-else-if="fetchError" class="error">{{ fetchError }}</div>

    <!-- Controls -->
    <div class="controls">
      <GeoButton :loading="loading" @click="refreshAroundMe" />
    </div>

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
              label="Périmètre"
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

    <!-- Loading -->
    <div v-if="loading" class="loading">Chargement…</div>

    <!-- Content -->
    <div v-else-if="movie" class="movie">
      <MovieHeader
        :title="movie.title"
        :poster-url="movie.poster_url"
        :duration="movie.duration"
        :director="movie.director"
        :synopsis="movie.synopsis"
      />

      <h2>Séances</h2>
      <div v-if="hasFilteredShowtimes">
        <div v-for="(cinema, cIdx) in filteredMovie.cinemas" :key="cinema.id ?? cIdx" class="cinema-wrapper">
          <CinemaBlock :cinema="cinema" :distance-precision="1" />
        </div>
      </div>
      <p v-else class="empty-showtimes">Aucune séance ne correspond aux filtres sélectionnés.</p>
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
:deep(.poster) {
  max-width: 220px;
  display: block;
  margin-bottom: 12px;
}
:deep(.cinema) {
  margin: 12px 0 20px;
}
:deep(.showtimes) {
  margin: 8px 0 0 0;
  padding-left: 18px;
}
.empty-showtimes {
  margin-top: 0.75rem;
  color: #475569;
}
</style>
