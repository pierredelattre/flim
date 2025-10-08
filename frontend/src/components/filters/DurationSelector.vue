<script setup>
const props = defineProps({
  modelValue: {
    type: Number,
    default: null,
  },
});

const emit = defineEmits(["update:modelValue"]);

const options = [
  { label: "< 1h30", value: 90 },
  { label: "< 2h", value: 120 },
  { label: "< 2h30", value: 150 },
  { label: "< 3h", value: 180 },
];

const onChange = (event) => {
  const raw = event.target.value;
  if (!raw) {
    emit("update:modelValue", null);
    return;
  }
  const parsed = Number(raw);
  emit("update:modelValue", Number.isNaN(parsed) ? null : parsed);
};
</script>

<template>
  <label class="duration-selector">
    <span class="duration-selector__label">Durée max</span>
    <select :value="modelValue ?? ''" @change="onChange">
      <option value="">Toutes</option>
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
  </label>
</template>

<style scoped>
.duration-selector {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.duration-selector select {
  padding: 0.4rem 0.6rem;
  border: 1px solid rgba(148, 163, 184, 0.6);
  border-radius: 0.375rem;
}
</style>
