<script setup>
const props = defineProps({
  modelValue: {
    type: Number,
    required: true,
  },
  label: {
    type: String,
    default: "Rayon de recherche",
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["update:modelValue"]);

const options = [2, 5, 10, 15, 20, 30];

const handleChange = (event) => {
  const value = Number(event.target.value);
  emit("update:modelValue", value);
};
</script>

<template>
  <label class="radius">
    <span>{{ label }}</span>
    <select
      :value="modelValue"
      :disabled="disabled"
      @change="handleChange"
    >
      <option v-for="option in options" :key="option" :value="option">
        {{ option }} km
      </option>
    </select>
  </label>
</template>
