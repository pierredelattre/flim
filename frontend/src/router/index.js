import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue';
import Movie from '@/views/Movie.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'Home', component: Home },
    { path: '/movie/:id', name: 'Movie', component: Movie, props: true },
  ],
})

export default router