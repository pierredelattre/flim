<script setup>
const props = defineProps({
  modelValue: {
    type: String,
    default: "",
  },
  label: {
    type: String,
    default: "Date",
  },
  min: {
    type: String,
    default: "",
  },
  max: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["update:modelValue"]);

const onInput = (event) => {
  emit("update:modelValue", event.target.value);
};
</script>

<template>
  <label class="date-picker-native">
    <span class="date-picker-native__label">{{ label }}</span>
    <input
      type="date"
      :value="modelValue"
      :min="min"
      :max="max"
      @input="onInput"
    />
  </label>
</template>

<style scoped>
.date-picker-native {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.date-picker-native input[type="date"] {
  padding: 0.4rem 0.6rem;
  border: 1px solid rgba(148, 163, 184, 0.6);
  border-radius: 0.375rem;
}
</style>
