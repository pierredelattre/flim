<script setup>
import { computed } from "vue";

const props = defineProps({
  groupLabel: {
    type: String,
    required: true,
  },
  items: {
    type: Array,
    default: () => [],
  },
  maxVisibleItems: {
    type: Number,
    default: 10,
  },
  maxHeight: {
    type: String,
    default: null,
  },
});

const emit = defineEmits(["toggle"]);

const onToggle = (id, checked) => {
  emit("toggle", { id, checked });
};

const computedMaxHeight = computed(() => {
  if (props.maxHeight) {
    return props.maxHeight;
  }
  const items = Number.isFinite(props.maxVisibleItems) && props.maxVisibleItems > 0 ? props.maxVisibleItems : 10;
  const lineHeightRem = 2.2;
  return `${(items * lineHeightRem).toFixed(2)}rem`;
});
</script>

<template>
  <fieldset class="filter-checkbox-list">
    <legend class="filter-checkbox-list__label">{{ groupLabel }}</legend>
    <p v-if="!items.length" class="filter-checkbox-list__empty">Aucune option disponible</p>
    <div
      class="options-list"
      role="listbox"
      :style="{ maxHeight: computedMaxHeight }"
      tabindex="0"
      @wheel.stop
    >
      <ul>
        <li v-for="item in items" :key="item.id">
          <label>
            <input
              type="checkbox"
              :value="item.id"
            :checked="item.checked"
            @change="onToggle(item.id, $event.target.checked)"
          />
            <span class="filter-checkbox-list__text">
              <span>{{ item.label }}</span>
              <span v-if="item.count !== undefined" class="filter-checkbox-list__count">({{ item.count }})</span>
            </span>
          </label>
        </li>
      </ul>
    </div>
  </fieldset>
</template>

<style scoped>
.filter-checkbox-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 0;
  padding: 0;
  border: none;
}

.filter-checkbox-list__label {
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.filter-checkbox-list ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.options-list {
  overflow-y: auto;
  max-height: 20rem;
  padding-right: 0.5rem;
  scrollbar-gutter: stable;
}

.options-list:focus {
  outline: none;
}

.options-list::-webkit-scrollbar {
  width: 0.5rem;
}

.options-list::-webkit-scrollbar-thumb {
  background-color: rgba(100, 116, 139, 0.4);
  border-radius: 9999px;
}

.filter-checkbox-list__empty {
  margin: 0;
  font-size: 0.85rem;
  color: #64748b;
}

.filter-checkbox-list label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.filter-checkbox-list input[type="checkbox"] {
  cursor: pointer;
}

.filter-checkbox-list__text {
  display: inline-flex;
  gap: 0.25rem;
  align-items: baseline;
}

.filter-checkbox-list__count {
  font-size: 0.85rem;
  color: #475569;
}
</style>
