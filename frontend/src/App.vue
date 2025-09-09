<script setup>
import { ref } from "vue"

const url = ref("")
const results = ref([])

async function scrape() {
  const res = await fetch("http://127.0.0.1:8000/scrape", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ url: url.value })
  })
  const data = await res.json()
  results.value = data.results
}
</script>

<template>
  <div>
    <h1>Scraper Allociné</h1>
    <input v-model="url" placeholder="Entrez une URL" />
    <button @click="scrape">Scraper</button>

    <ul>
      <li v-for="r in results" :key="r">{{ r }}</li>
    </ul>
  </div>
</template>
