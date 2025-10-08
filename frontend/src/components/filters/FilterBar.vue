<script setup>
import { computed, provide } from "vue";
import { filterBarContextKey } from "./filterContext.js";

const props = defineProps({
  openDropdownKey: {
    type: String,
    default: null,
  },
});

const emit = defineEmits(["update:openDropdownKey"]);

const openKey = computed(() => props.openDropdownKey);

const setOpenKey = (key) => {
  emit("update:openDropdownKey", key);
};

const toggleDropdown = (key) => {
  if (!key) {
    setOpenKey(null);
    return;
  }
  setOpenKey(openKey.value === key ? null : key);
};

const closeDropdown = () => {
  setOpenKey(null);
};

const triggerRefs = new Map();

const registerTrigger = (key, el) => {
  if (!key) return;
  if (el) {
    triggerRefs.set(key, el);
  } else {
    triggerRefs.delete(key);
  }
};

const getTrigger = (key) => triggerRefs.get(key) || null;

provide(filterBarContextKey, {
  openKey,
  toggleDropdown,
  closeDropdown,
  registerTrigger,
  getTrigger,
});
</script>

<template>
  <div class="filter-bar" role="toolbar">
    <slot name="date" />
    <slot name="genres" />
    <slot name="languages" />
    <slot name="subtitles" />
    <slot name="duration" />
    <slot name="radius" />
    <slot name="sort" />
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  gap: 0.75rem;
  padding: 0.5rem 0;
}

.filter-bar::-webkit-scrollbar {
  height: 6px;
}

.filter-bar::-webkit-scrollbar-thumb {
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
}

:deep(.filter-entry) {
  position: relative;
  flex: 0 0 auto;
}
</style>
