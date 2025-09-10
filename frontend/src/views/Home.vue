
<script setup>
import { useGeolocation } from '@/composables/geoloc.js';
const { position, error, getPosition } = useGeolocation();
</script>

<template>
  <div>
    <button @click="getPosition">Obtenir ma position</button>

    <div v-if="position.lat && position.lng">
      <p>Latitude: {{ position.lat }}</p>
      <p>Longitude: {{ position.lng }}</p>
    </div>

    <div v-if="error">
      <p style="color:red">{{ error }}</p>
    </div>
  </div>
</template>

<script>
export default {};
</script>