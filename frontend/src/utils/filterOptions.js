import { GENRES_OPTIONS, SUBTITLES_OPTIONS } from "@/constants/filterOptions.js";
import { canonicalizeDiffusionVersion, normalizeLanguagesArray } from "@/utils/formatters.js";

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
      const languagesInput = Array.isArray(payload?.languages)
        ? payload.languages
        : [];
      const subtitlesInput = Array.isArray(payload?.subtitles) && payload.subtitles.length
        ? payload.subtitles
        : SUBTITLES_OPTIONS;

      const normalizedLanguageSet = new Set();
      for (const entry of languagesInput) {
        for (const value of normalizeLanguagesArray(entry)) {
          normalizedLanguageSet.add(value);
        }
      }

      const normalizedSubtitleSet = new Set();
      for (const entry of subtitlesInput) {
        const canonical = canonicalizeDiffusionVersion(entry);
        if (canonical) {
          normalizedSubtitleSet.add(canonical);
        }
      }

      const normalized = {
        genres: [...genres].map((g) => g.trim()).filter(Boolean),
        languages: Array.from(normalizedLanguageSet).sort((a, b) => a.localeCompare(b)),
        subtitles: Array.from(normalizedSubtitleSet).sort(),
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
