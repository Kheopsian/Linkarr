<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const API_BASE_URL = ''

// 'props' sont les données passées depuis le parent (App.vue)
// 'emit' est la manière de renvoyer des événements au parent
const props = defineProps({
  basePath: {
    type: String,
    default: '/',
  }
})
const emit = defineEmits(['close', 'select-folder'])

// État interne du composant
const currentPath = ref('/')
const content = ref([])
const isLoading = ref(true)
const error = ref(null)

// Fonction pour appeler notre API /api/browse
async function browsePath(path) {
  isLoading.value = true
  error.value = null
  try {
    const response = await axios.get(`${API_BASE_URL}/api/browse`, { params: { path } })
    content.value = response.data
    currentPath.value = path
  } catch (e) {
    console.error(`Erreur en naviguant vers ${path}`, e)
    error.value = "Impossible de charger le contenu de ce dossier."
  } finally {
    isLoading.value = false
  }
}

function handleItemClick(item) {
  if (item.is_dir) {
    browsePath(item.path)
  }
}

function goUpOneLevel() {
  if (currentPath.value === '/') return
  const parentPath = currentPath.value.substring(0, currentPath.value.lastIndexOf('/')) || '/'
  browsePath(parentPath)
}

function selectCurrentFolder() {
  emit('select-folder', currentPath.value)
}

// Au démarrage du composant, on charge le contenu de la racine
onMounted(() => {
  browsePath(props.basePath)
})
</script>

<template>
  <div class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
    <div class="bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl h-3/4 flex flex-col">
      <div class="p-4 border-b border-gray-700 flex justify-between items-center">
        <h3 class="text-lg font-semibold">Sélectionner un dossier</h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-white">&times;</button>
      </div>

      <div class="p-2 bg-gray-900 flex items-center gap-2">
        <button @click="goUpOneLevel" :disabled="currentPath === '/'" class="px-2 py-1 bg-gray-700 rounded disabled:opacity-50">..</button>
        <div class="font-mono text-sm text-gray-300 bg-gray-700 px-2 py-1 rounded w-full">{{ currentPath }}</div>
        <button @click="selectCurrentFolder" class="px-3 py-1 bg-emerald-600 rounded whitespace-nowrap">Sélectionner ce dossier</button>
      </div>

      <div class="p-4 overflow-y-auto flex-grow">
        <div v-if="isLoading">Chargement...</div>
        <div v-else-if="error" class="text-red-400">{{ error }}</div>
        <div v-else>
          <ul>
            <li v-for="item in content" :key="item.name"
                @click="handleItemClick(item)"
                :class="{'cursor-pointer hover:bg-gray-700': item.is_dir, 'opacity-50': !item.is_dir}"
                class="p-2 rounded flex items-center">
              <span class="mr-2">{{ item.is_dir ? '📁' : '📄' }}</span>
              <span>{{ item.name }}</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>