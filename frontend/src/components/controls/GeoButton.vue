<script setup>
const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["click"]);

const handleClick = (event) => {
  if (props.loading || props.disabled) {
    event.preventDefault();
    return;
  }
  emit("click", event);
};
</script>

<template>
  <button
    type="button"
    :disabled="loading || disabled"
    @click="handleClick"
  >
    <slot>
      {{ loading ? "Chargement..." : "Autour de moi" }}
    </slot>
  </button>
</template>
