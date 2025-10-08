export const canonicalizeDiffusionVersion = (value) => {
  if (!value) {
    return "";
  }
  const normalized = String(value).trim().toUpperCase();
  if (normalized === "SUBBED") {
    return "SUBS";
  }
  return normalized;
};

export const formatDiffusionVersion = (value) => {
  const canonical = canonicalizeDiffusionVersion(value);

  switch (canonical) {
    case "ORIGINAL":
      return "Langue originale";
    case "SUBS":
      return "Sous-titré en français";
    case "DUBBED":
      return "Doublé en français";
    case "LOCAL":
      return "Version locale";
    default:
      return canonical || "";
  }
};

export const normalizeLanguagesArray = (raw) => {
  if (raw == null) {
    return [];
  }
  if (Array.isArray(raw)) {
    const result = [];
    for (const entry of raw) {
      for (const value of normalizeLanguagesArray(entry)) {
        result.push(value);
      }
    }
    return Array.from(new Set(result));
  }

  const cleanString = String(raw).replace(/[{}]/g, "");
  return Array.from(
    new Set(
      cleanString
        .split(",")
        .map((part) => part.trim())
        .filter((part) => part.length > 0)
    )
  );
};

export const formatLanguages = (raw) => normalizeLanguagesArray(raw).join(", ");
