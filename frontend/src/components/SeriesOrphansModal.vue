<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  isOpen: Boolean,
  orphans: {
    type: Array,
    default: () => []
  },
  columnName: {
    type: String,
    default: 'Colonne'
  }
})

const emit = defineEmits(['close'])

// État pour suivre la série et la saison sélectionnées
const selectedSeries = ref(null)
const selectedSeason = ref(null)

// Fonction pour extraire le nom de la série à partir du chemin
function extractSeriesName(path) {
  const parts = path.split('/')
  // Trouve l'index de "series" dans le chemin
  const seriesIndex = parts.indexOf('series')
  if (seriesIndex !== -1 && parts.length > seriesIndex + 1) {
    // Le nom de la série est le prochain élément après "series"
    return parts[seriesIndex + 1]
  }
  return 'Série inconnue'
}

// Fonction pour extraire le numéro de la saison à partir du chemin
function extractSeasonNumber(path) {
  const parts = path.split('/')
  // Trouve l'index de "Season" ou "S" dans le chemin
  for (let i = 0; i < parts.length; i++) {
    if (parts[i].includes('Season') || parts[i].includes('S')) {
      const seasonMatch = parts[i].match(/Season\s*(\d+)|S(\d+)/)
      if (seasonMatch) {
        return seasonMatch[1] || seasonMatch[2]
      }
    }
  }
  return 'Saison inconnue'
}

// Fonction pour extraire le nom de l'épisode à partir du chemin
function extractEpisodeName(path) {
  const parts = path.split('/')
  const filename = parts[parts.length - 1]
  // Supprime l'extension .mkv
  return filename.replace('.mkv', '')
}

// Grouper les orphelins par série et par saison
const groupedOrphans = computed(() => {
  const groups = {}
  
  props.orphans.forEach(path => {
    const seriesName = extractSeriesName(path)
    const seasonNumber = extractSeasonNumber(path)
    
    if (!groups[seriesName]) {
      groups[seriesName] = {}
    }
    
    if (!groups[seriesName][seasonNumber]) {
      groups[seriesName][seasonNumber] = []
    }
    
    groups[seriesName][seasonNumber].push({
      path,
      episodeName: extractEpisodeName(path)
    })
  })
  
  return groups
})

// Fonctions pour naviguer dans la modale
function selectSeries(seriesName) {
  selectedSeries.value = seriesName
  selectedSeason.value = null
}

function selectSeason(seasonNumber) {
  selectedSeason.value = seasonNumber
}

function goBackToSeries() {
  selectedSeason.value = null
}

function goBackToRoot() {
  selectedSeries.value = null
  selectedSeason.value = null
}

// Fonction pour fermer la modale
function closeModal() {
  selectedSeries.value = null
  selectedSeason.value = null
  emit('close')
}
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
    <div class="bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl h-3/4 flex flex-col">
      <!-- En-tête de la modale -->
      <div class="p-4 border-b border-gray-700 flex justify-between items-center">
        <h3 class="text-lg font-semibold">
          Orphelins de séries - {{ columnName }}
          <span v-if="selectedSeries" class="text-emerald-400"> > {{ selectedSeries }}</span>
          <span v-if="selectedSeason" class="text-emerald-400"> > Saison {{ selectedSeason }}</span>
        </h3>
        <button @click="closeModal" class="text-gray-400 hover:text-white">&times;</button>
      </div>

      <!-- Contenu de la modale -->
      <div class="p-4 overflow-y-auto flex-grow">
        <!-- Vue racine : liste des séries -->
        <div v-if="!selectedSeries">
          <h4 class="text-md font-semibold mb-4 text-gray-300">Séries avec des orphelins ({{ Object.keys(groupedOrphans).length }})</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div 
              v-for="(seasons, seriesName) in groupedOrphans" 
              :key="seriesName"
              @click="selectSeries(seriesName)"
              class="bg-gray-700 p-4 rounded-lg cursor-pointer hover:bg-gray-600 transition-colors"
            >
              <div class="flex items-center mb-2">
                <span class="text-2xl mr-2">📺</span>
                <h5 class="text-lg font-semibold">{{ seriesName }}</h5>
              </div>
              <p class="text-sm text-gray-400">{{ Object.keys(seasons).length }} saison(s) affectée(s)</p>
              <p class="text-sm text-gray-400">
                {{ Object.values(seasons).reduce((total, episodes) => total + episodes.length, 0) }} épisode(s) orphelin(s)
              </p>
            </div>
          </div>
        </div>

        <!-- Vue des saisons d'une série -->
        <div v-else-if="selectedSeries && !selectedSeason">
          <div class="mb-4">
            <button @click="goBackToRoot" class="text-emerald-400 hover:text-emerald-300 mb-2">
              ← Retour à la liste des séries
            </button>
            <h4 class="text-md font-semibold text-gray-300">Saisons de {{ selectedSeries }}</h4>
          </div>
          
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div 
              v-for="(episodes, seasonNumber) in groupedOrphans[selectedSeries]" 
              :key="seasonNumber"
              @click="selectSeason(seasonNumber)"
              class="bg-gray-700 p-4 rounded-lg cursor-pointer hover:bg-gray-600 transition-colors"
            >
              <div class="flex items-center mb-2">
                <span class="text-2xl mr-2">📁</span>
                <h5 class="text-lg font-semibold">Saison {{ seasonNumber }}</h5>
              </div>
              <p class="text-sm text-gray-400">{{ episodes.length }} épisode(s) orphelin(s)</p>
            </div>
          </div>
        </div>

        <!-- Vue des épisodes d'une saison -->
        <div v-else-if="selectedSeries && selectedSeason">
          <div class="mb-4">
            <button @click="goBackToSeries" class="text-emerald-400 hover:text-emerald-300 mb-2">
              ← Retour aux saisons de {{ selectedSeries }}
            </button>
            <h4 class="text-md font-semibold text-gray-300">
              Épisodes orphelins - {{ selectedSeries }} - Saison {{ selectedSeason }}
            </h4>
          </div>
          
          <div class="space-y-2">
            <div 
              v-for="episode in groupedOrphans[selectedSeries][selectedSeason]" 
              :key="episode.path"
              class="bg-gray-700 p-3 rounded-lg font-mono text-sm"
            >
              <div class="flex items-center mb-1">
                <span class="text-xl mr-2">🎬</span>
                <span class="font-semibold">{{ episode.episodeName }}</span>
              </div>
              <div class="text-gray-400 text-xs break-all">{{ episode.path }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>