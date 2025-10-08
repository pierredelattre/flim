<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { filterBarContextKey } from "./filterContext.js";

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  dropdownKey: {
    type: String,
    required: true,
  },
  active: {
    type: Boolean,
    default: false,
  },
});

const filterContext = inject(filterBarContextKey);

if (!filterContext) {
  throw new Error("FilterItem must be used within a FilterBar.");
}

const triggerId = `filter-trigger-${props.dropdownKey}`;
const dropdownId = `filter-dropdown-${props.dropdownKey}`;

const isOpen = computed(() => filterContext.openKey.value === props.dropdownKey);

const buttonRef = ref(null);

const toggle = () => {
  filterContext.toggleDropdown(props.dropdownKey);
};

const handleKeydown = (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    toggle();
  }
  if (event.key === "Escape" && isOpen.value) {
    event.preventDefault();
    filterContext.closeDropdown();
  }
};

onMounted(() => {
  filterContext.registerTrigger(props.dropdownKey, buttonRef.value);
});

onBeforeUnmount(() => {
  filterContext.registerTrigger(props.dropdownKey, null);
});

watch(
  () => buttonRef.value,
  (el) => {
    filterContext.registerTrigger(props.dropdownKey, el);
  }
);

defineExpose({
  focus: () => {
    buttonRef.value?.focus();
  },
  isOpen,
});
</script>

<template>
  <div class="filter-item">
    <button
      ref="buttonRef"
      type="button"
      class="filter-item__button"
      :class="{ 'is-active': active, 'is-open': isOpen }"
      :id="triggerId"
      :aria-expanded="isOpen ? 'true' : 'false'"
      :aria-controls="dropdownId"
      aria-haspopup="true"
      @click="toggle"
      @keydown="handleKeydown"
    >
      <span class="filter-item__label">{{ label }}</span>
      <slot name="value" />
      <span class="filter-item__chevron" aria-hidden="true">▾</span>
    </button>
  </div>
</template>

<style scoped>
.filter-item__button {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.75rem;
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 9999px;
  background-color: #fff;
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.filter-item__button:hover,
.filter-item__button:focus {
  border-color: rgba(59, 130, 246, 0.7);
  outline: none;
}

.filter-item__button.is-active {
  background-color: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.9);
}

.filter-item__chevron {
  font-size: 0.75rem;
}

.filter-item__value {
  font-size: 0.75rem;
  color: #1e3a8a;
}
</style>
