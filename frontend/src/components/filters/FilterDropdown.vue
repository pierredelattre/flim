<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { filterBarContextKey } from "./filterContext.js";

const props = defineProps({
  dropdownKey: {
    type: String,
    required: true,
  },
});

const filterContext = inject(filterBarContextKey);

if (!filterContext) {
  throw new Error("FilterDropdown must be used within a FilterBar.");
}

const dropdownId = `filter-dropdown-${props.dropdownKey}`;

const isOpen = computed(() => filterContext.openKey.value === props.dropdownKey);

const panelRef = ref(null);

const focusFirstElement = () => {
  const el = panelRef.value;
  if (!el) return;
  const focusable = el.querySelector(
    "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])"
  );
  if (focusable && typeof focusable.focus === "function") {
    focusable.focus();
  }
};

const closeAndRestoreFocus = () => {
  filterContext.closeDropdown();
  const trigger = filterContext.getTrigger(props.dropdownKey);
  if (trigger && typeof trigger.focus === "function") {
    trigger.focus();
  }
};

const onDocumentClick = (event) => {
  const panelEl = panelRef.value;
  if (!panelEl) return;
  if (panelEl.contains(event.target)) return;
  const trigger = filterContext.getTrigger(props.dropdownKey);
  if (trigger && trigger.contains && trigger.contains(event.target)) return;
  closeAndRestoreFocus();
};

const onDocumentKeydown = (event) => {
  if (event.key === "Escape") {
    event.preventDefault();
    closeAndRestoreFocus();
  }
};

watch(
  () => isOpen.value,
  (open) => {
    if (open) {
      nextTick(focusFirstElement);
      document.addEventListener("mousedown", onDocumentClick);
      document.addEventListener("keydown", onDocumentKeydown);
    } else {
      document.removeEventListener("mousedown", onDocumentClick);
      document.removeEventListener("keydown", onDocumentKeydown);
    }
  }
);

onMounted(() => {
  if (isOpen.value) {
    nextTick(focusFirstElement);
    document.addEventListener("mousedown", onDocumentClick);
    document.addEventListener("keydown", onDocumentKeydown);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("mousedown", onDocumentClick);
  document.removeEventListener("keydown", onDocumentKeydown);
});
</script>

<template>
  <div
    v-if="isOpen"
    :id="dropdownId"
    ref="panelRef"
    class="filter-dropdown"
    role="group"
    :aria-labelledby="`filter-trigger-${dropdownKey}`"
    tabindex="-1"
  >
    <slot />
  </div>
</template>

<style scoped>
.filter-dropdown {
  position: absolute;
  top: calc(100% + 0.35rem);
  left: 0;
  min-width: 220px;
  max-width: 320px;
  background-color: #fff;
  border: 1px solid rgba(148, 163, 184, 0.6);
  border-radius: 0.5rem;
  box-shadow: 0 10px 25px rgba(15, 23, 42, 0.15);
  padding: 0.75rem;
  z-index: 30;
}

.filter-dropdown:focus {
  outline: none;
}
</style>
