<script setup>
import { ref } from "vue"

const departement = ref("P0571")

const results = ref([])

async function scrape() {
  if (!departement.value) {
    alert("Merci de remplir tous les champs !")
    return
  }

  const res = await fetch("http://127.0.0.1:8000/scrape", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      departement_id: departement.value
    })
  })
  const data = await res.json()
  if (data.success) {
    results.value = data.data
  } else {
    alert("Erreur: " + data.error)
  }
}
</script>

<template>
  <div>
    <h1>movies around me</h1>
    <input v-model="departement" placeholder="Département" />
    <button @click="scrape">Scraper</button>

    <h2>Films</h2>
    <div id="results" v-if="results.length">
      <div class="result__movie" v-for="(res, index) in results" :key="index">
        <img :src="res.urlPoster" :alt="res.title">
        <p>{{ res.title }}</p>
        <p>{{ res.director }}</p>
        <p>{{ res.runtime }}</p>
      </div>
    </div>
  </div>
</template>
