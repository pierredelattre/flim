<script setup>
import { ref } from "vue";
import BackButton from "@/components/controls/BackButton.vue";
import GeoButton from "@/components/controls/GeoButton.vue";
import RadiusSelector from "@/components/controls/RadiusSelector.vue";
import SearchBox from "@/components/search/SearchBox.vue";

const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  radiusKm: {
    type: Number,
    required: true,
  },
  typeLabels: {
    type: Object,
    default: () => ({}),
  },
  searchQuery: {
    type: String,
    default: "",
  },
  suggestions: {
    type: Array,
    default: () => [],
  },
  isSuggestionsOpen: {
    type: Boolean,
    default: false,
  },
  highlightIndex: {
    type: Number,
    default: -1,
  },
  backVisible: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits([
  "reset",
  "search-input",
  "open-suggestions",
  "keydown",
  "select-suggestion",
  "fetch-nearby",
  "update:radiusKm",
]);

const handleUpdateSearch = (value) => {
  emit("search-input", value);
};

const handleRadiusUpdate = (value) => {
  emit("update:radiusKm", value);
};

const searchBoxRef = ref(null);

defineExpose({
  searchBox: searchBoxRef,
});
</script>

<template>
  <div class="controls">
    <BackButton
      :visible="backVisible"
      :disabled="loading"
      title="Revenir à la vue initiale (tous les films et cinémas autour de moi)"
      @click="emit('reset')"
    />

    <SearchBox
      ref="searchBoxRef"
      :modelValue="searchQuery"
      :suggestions="suggestions"
      :isOpen="isSuggestionsOpen"
      :highlightIndex="highlightIndex"
      :typeLabels="typeLabels"
      @update:modelValue="handleUpdateSearch"
      @open="emit('open-suggestions')"
      @keydown="emit('keydown', $event)"
      @select="emit('select-suggestion', $event)"
    />

    <GeoButton :loading="loading" @click="emit('fetch-nearby')" />

    <RadiusSelector
      :modelValue="radiusKm"
      @update:modelValue="handleRadiusUpdate"
    />
  </div>
</template>
