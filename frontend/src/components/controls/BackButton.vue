<script setup>
const props = defineProps({
  visible: {
    type: Boolean,
    default: true,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["click"]);

const handleClick = (event) => {
  if (props.disabled) {
    event.preventDefault();
    return;
  }
  emit("click", event);
};
</script>

<template>
  <button
    v-if="visible"
    type="button"
    :disabled="disabled"
    @click="handleClick"
  >
    ← Retour
  </button>
</template>
