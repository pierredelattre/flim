import { ref } from 'vue';

export function useGeolocation() {
  const position = ref({ lat: null, lng: null });
  const error = ref(null);

  const getPosition = () => {
    if (!navigator.geolocation) {
      error.value = "Géolocalisation non supportée";
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        position.value.lat = pos.coords.latitude;
        position.value.lng = pos.coords.longitude;
      },
      (err) => {
        error.value = err.message;
      }
    );
  };

  return { position, error, getPosition };
}