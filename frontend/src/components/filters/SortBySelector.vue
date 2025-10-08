<script setup>
const props = defineProps({
  modelValue: {
    type: String,
    default: "relevance",
  },
});

const emit = defineEmits(["update:modelValue"]);

const options = [
  { value: "relevance", label: "Pertinence" },
  { value: "distance", label: "Distance" },
  { value: "earliest_showtime", label: "Première séance" },
  { value: "title_asc", label: "Titre A→Z" },
  { value: "duration_asc", label: "Durée croissante" },
];

const onChange = (event) => {
  emit("update:modelValue", event.target.value);
};
</script>

<template>
  <label class="sort-by-selector">
    <span class="sort-by-selector__label">Trier par</span>
    <select :value="modelValue" @change="onChange">
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
  </label>
</template>

<style scoped>
.sort-by-selector {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.sort-by-selector select {
  padding: 0.4rem 0.6rem;
  border: 1px solid rgba(148, 163, 184, 0.6);
  border-radius: 0.375rem;
}
</style>
