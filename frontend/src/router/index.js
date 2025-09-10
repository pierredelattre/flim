import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue';
import CinemaMovies from '@/views/CinemaMovies.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'Home', component: Home },
    { path: '/cinema-movies', name: 'CinemaMovies', component: CinemaMovies },
  ],
})

export default router
