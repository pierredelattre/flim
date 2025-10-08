<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  modelValue: {
    type: String,
    default: "",
  },
  placeholder: {
    type: String,
    default: "Rechercher un film, un cinéma ou une ville",
  },
  suggestions: {
    type: Array,
    default: () => [],
  },
  isOpen: {
    type: Boolean,
    default: false,
  },
  highlightIndex: {
    type: Number,
    default: -1,
  },
  typeLabels: {
    type: Object,
    default: () => ({}),
  },
});

const emit = defineEmits(["update:modelValue", "open", "close", "keydown", "select"]);

const containerRef = ref(null);
const inputRef = ref(null);

const listboxId = "suggestions-list";

const activeDescendant = computed(() => {
  if (!props.isOpen || props.highlightIndex < 0) return undefined;
  const suggestion = props.suggestions[props.highlightIndex];
  if (!suggestion) return undefined;
  return `sugg-${suggestion.type}-${suggestion.id}`;
});

const updateValue = (event) => {
  emit("update:modelValue", event.target.value);
};

const handleFocus = () => {
  emit("open");
};

const handleKeydown = (event) => {
  emit("keydown", event);
};

const handleSelect = (suggestion) => {
  emit("select", suggestion);
};

defineExpose({
  container: containerRef,
  focusInput: () => {
    if (inputRef.value) {
      inputRef.value.focus();
    }
  },
});
</script>

<template>
  <div class="search" ref="containerRef">
    <input
      ref="inputRef"
      type="search"
      :value="modelValue"
      :placeholder="placeholder"
      role="combobox"
      aria-autocomplete="list"
      :aria-expanded="isOpen ? 'true' : 'false'"
      aria-haspopup="listbox"
      :aria-controls="listboxId"
      :aria-activedescendant="activeDescendant"
      @input="updateValue"
      @focus="handleFocus"
      @keydown="handleKeydown"
    />
    <ul
      v-if="isOpen && suggestions.length"
      class="suggestions"
      :id="listboxId"
      role="listbox"
    >
      <li
        v-for="(item, index) in suggestions"
        :key="`${item.type}-${item.id}`"
        :id="`sugg-${item.type}-${item.id}`"
        role="option"
        :aria-selected="index === highlightIndex ? 'true' : 'false'"
        :class="{ highlighted: index === highlightIndex }"
        @mousedown.prevent="handleSelect(item)"
      >
        <span class="suggestion__tag">{{ typeLabels[item.type] ?? item.type }}</span>
        <span class="suggestion__label">{{ item.label }}</span>
        <span v-if="item.sublabel" class="suggestion__sublabel">{{ item.sublabel }}</span>
      </li>
    </ul>
  </div>
</template>
