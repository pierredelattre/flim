import { GENRES_OPTIONS, SUBTITLES_OPTIONS } from "@/constants/filterOptions.js";

let cachedOptions;
let pendingRequest;

const buildDefaultOptions = () => ({
  genres: [...GENRES_OPTIONS],
  languages: [],
  subtitles: [...SUBTITLES_OPTIONS],
});

export const loadFilterOptions = async () => {
  if (cachedOptions) {
    return cachedOptions;
  }

  if (pendingRequest) {
    return pendingRequest;
  }

  const fetchPromise = (async () => {
    try {
      const response = await fetch("/api/filters_options");
      if (!response.ok) {
        throw new Error(`Unexpected status: ${response.status}`);
      }
      const payload = await response.json();
      const genres = Array.isArray(payload?.genres) && payload.genres.length ? payload.genres : GENRES_OPTIONS;
      const languages = Array.isArray(payload?.languages)
        ? payload.languages.filter((entry) => typeof entry === "string" && entry.trim())
        : [];
      const subtitles =
        Array.isArray(payload?.subtitles) && payload.subtitles.length
          ? payload.subtitles.map((entry) => String(entry).trim().toUpperCase())
          : SUBTITLES_OPTIONS;

      const normalized = {
        genres: [...genres].map((g) => g.trim()).filter(Boolean),
        languages: [...languages].map((lang) => lang.trim()).filter(Boolean),
        subtitles: [...subtitles].map((code) => code.trim().toUpperCase()).filter(Boolean),
      };
      cachedOptions = normalized;
      return cachedOptions;
    } catch (error) {
      console.error("Unable to load filter options, using defaults:", error);
      cachedOptions = buildDefaultOptions();
      return cachedOptions;
    } finally {
      pendingRequest = null;
    }
  })();

  pendingRequest = fetchPromise;
  return fetchPromise;
};
