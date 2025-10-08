<script setup>
const props = defineProps({
  groupLabel: {
    type: String,
    required: true,
  },
  items: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["toggle"]);

const onToggle = (id, checked) => {
  emit("toggle", { id, checked });
};
</script>

<template>
  <fieldset class="filter-checkbox-list">
    <legend class="filter-checkbox-list__label">{{ groupLabel }}</legend>
    <p v-if="!items.length" class="filter-checkbox-list__empty">Aucune option disponible</p>
    <ul>
      <li v-for="item in items" :key="item.id">
        <label>
          <input
            type="checkbox"
            :value="item.id"
            :checked="item.checked"
            @change="onToggle(item.id, $event.target.checked)"
          />
          <span>{{ item.label }}</span>
        </label>
      </li>
    </ul>
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
</style>
