<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
// 1. Importer les nouveaux composants
import FileBrowserModal from './components/FileBrowserModal.vue'
import SeriesOrphansModal from './components/SeriesOrphansModal.vue'

const API_BASE_URL = ''

const config = ref(null)
const activeTabId = ref('movies') // Utilise l'ID de l'onglet au lieu du nom
const error = ref(null)

// --- 2. Nouvel état pour gérer les modales ---
const isModalOpen = ref(false)
// Pour se souvenir pour quelle liste on ajoute un dossier
const addTarget = ref({ category: null, column: null })
// Pour afficher un message de succès après sauvegarde
const saveSuccessMessage = ref('')
const scanResults = ref(null) // Pour stocker les résultats du dernier scan
const isScanning = ref(false) // Pour afficher un message pendant le scan

// État pour la modale des orphelins de séries
const isSeriesOrphansModalOpen = ref(false)
const seriesOrphansType = ref('a') // 'a' ou 'b' pour indiquer quelle colonne d'orphelins afficher

// État pour le mode de scan par dossier
const scanMode = ref('file') // 'file' ou 'folder'
const checkColumn = ref('a') // 'a', 'b' ou 'both' pour le scan par dossier

// État pour la gestion des onglets
const isEditingTabName = ref(false)
const newTabName = ref('')
const editingTabId = ref(null)
const isAddingNewTab = ref(false)

// Fonction pour obtenir l'onglet actif
const activeTab = computed(() => {
  return config.value?.tabs?.find(tab => tab.id === activeTabId.value) || config.value?.tabs?.[0]
})

onMounted(async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/config`)
    config.value = response.data
    if (config.value.tabs && config.value.tabs.length > 0) {
      activeTabId.value = config.value.tabs[0].id
    }
  } catch (e) {
    console.error('Erreur lors de la récupération de la configuration', e)
    error.value = 'Impossible de contacter le backend.'
  }
})

// --- 3. Fonctions pour la modale et la sauvegarde ---

// Ouvre la modale et mémorise où on veut ajouter le dossier
function openBrowser(tabId, column) {
  addTarget.value = { tabId, column }
  isModalOpen.value = true
}

// Gère le dossier sélectionné par la modale
function handleFolderSelect(path) {
  const { tabId, column } = addTarget.value
  if (tabId && column) {
    // Trouver l'onglet correspondant
    const tab = config.value.tabs.find(t => t.id === tabId)
    if (tab) {
      // Ajoute le chemin au bon endroit dans notre config locale
      // On s'assure que le dossier n'est pas déjà dans la liste
      if (!tab[column].includes(path)) {
        tab[column].push(path)
      }
    }
  }
  isModalOpen.value = false
}

// Sauvegarde la configuration entière sur le backend
async function saveConfig() {
  try {
    await axios.post(`${API_BASE_URL}/api/config`, config.value)
    saveSuccessMessage.value = 'Configuration sauvegardée avec succès !'
    // Fait disparaître le message après 3 secondes
    setTimeout(() => { saveSuccessMessage.value = '' }, 3000)
  } catch (e) {
    console.error('Erreur lors de la sauvegarde', e)
    error.value = 'Une erreur est survenue lors de la sauvegarde.'
  }
}

function removePath(tabId, column, pathToRemove) {
    const tab = config.value.tabs.find(t => t.id === tabId)
    if (tab) {
        const list = tab[column]
        tab[column] = list.filter(path => path !== pathToRemove)
    }
}

function updateColumnName(value, column) {
    if (activeTab.value) {
        activeTab.value[`name_${column}`] = value
    }
}

function openSeriesOrphansModal(type) {
    seriesOrphansType.value = type
    isSeriesOrphansModalOpen.value = true
}

function closeSeriesOrphansModal() {
    isSeriesOrphansModalOpen.value = false
}

async function runScanFolder() {
    isScanning.value = true
    scanResults.value = null // Réinitialise les anciens résultats
    error.value = null
    try {
        // On appelle l'endpoint du backend avec l'ID de l'onglet actif et la colonne à vérifier
        const response = await axios.post(`${API_BASE_URL}/api/scan-folder/${activeTabId.value}?check_column=${activeTab.value.check_column}`)
        scanResults.value = response.data.results
    } catch (e) {
        console.error(`Erreur lors du scan par dossier de l'onglet '${activeTabId.value}'`, e)
        // Affiche une erreur plus spécifique si le backend la fournit
        if (e.response && e.response.data && e.response.data.detail) {
            error.value = `Erreur du scan : ${e.response.data.detail}`
        } else {
            error.value = "Une erreur est survenue lors du scan."
        }
    } finally {
        isScanning.value = false
    }
}

async function runScan() {
  isScanning.value = true
  scanResults.value = null // Réinitialise les anciens résultats
  error.value = null
  try {
    // On appelle l'endpoint du backend avec l'ID de l'onglet actif
    const response = await axios.post(`${API_BASE_URL}/api/scan/${activeTabId.value}`)
    scanResults.value = response.data.results
  } catch (e) {
    console.error(`Erreur lors du scan de l'onglet '${activeTabId.value}'`, e)
    // Affiche une erreur plus spécifique si le backend la fournit
    if (e.response && e.response.data && e.response.data.detail) {
        error.value = `Erreur du scan : ${e.response.data.detail}`
    } else {
        error.value = "Une erreur est survenue lors du scan."
    }
  } finally {
    isScanning.value = false
  }
}

// Fonctions pour la gestion des onglets
function startEditTabName(tabId, currentName) {
  editingTabId.value = tabId
  newTabName.value = currentName
  isEditingTabName.value = true
}

function cancelEditTabName() {
  isEditingTabName.value = false
  editingTabId.value = null
  newTabName.value = ''
}

function saveTabName() {
  if (editingTabId.value && newTabName.value.trim()) {
    const tab = config.value.tabs.find(t => t.id === editingTabId.value)
    if (tab) {
      tab.name = newTabName.value.trim()
    }
  }
  cancelEditTabName()
}

function startAddNewTab() {
  isAddingNewTab.value = true
  newTabName.value = ''
}

function cancelAddNewTab() {
  isAddingNewTab.value = false
  newTabName.value = ''
}

function addNewTab() {
  if (newTabName.value.trim()) {
    const newTabId = `tab_${Date.now()}`
    const newTab = {
      id: newTabId,
      name: newTabName.value.trim(),
      scan_mode: 'file',
      check_column: 'a',
      paths_a: [],
      paths_b: [],
      name_a: 'Colonne A',
      name_b: 'Colonne B'
    }
    config.value.tabs.push(newTab)
    activeTabId.value = newTabId
    cancelAddNewTab()
  }
}

function removeTab(tabId) {
  if (config.value.tabs.length > 1) {
    config.value.tabs = config.value.tabs.filter(t => t.id !== tabId)
    if (activeTabId.value === tabId) {
      activeTabId.value = config.value.tabs[0].id
    }
  }
}

function switchTab(tabId) {
  activeTabId.value = tabId
  scanResults.value = null
}

</script>

<template>
  <div class="bg-gray-900 text-gray-200 min-h-screen font-sans">
    <div class="max-w-7xl mx-auto p-4 md:p-8">
      <header>
        <h1 class="text-3xl font-bold text-center mb-2 text-emerald-400">
          Linkarr - Hardlink Sync Monitor
        </h1>
        <div class="text-center mb-6 flex flex-col items-center gap-4">
            <div class="flex flex-wrap justify-center items-center gap-4">
                <button @click="saveConfig" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
                  Sauvegarder la configuration
                </button>
                <button @click="runScan" :disabled="isScanning" class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded disabled:opacity-50 disabled:cursor-not-allowed">
                  {{ isScanning ? 'Scan en cours...' : `Lancer le scan '${activeTab?.name || ''}'` }}
                </button>
            </div>
            
            <!-- Options de scan -->
            <div v-if="activeTab" class="bg-gray-800 p-4 rounded-lg border border-gray-700 w-full max-w-2xl">
                <h3 class="text-lg font-semibold mb-3 text-center">Options de scan pour l'onglet "{{ activeTab.name }}"</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium mb-2">Mode de scan</label>
                        <div class="flex gap-2">
                            <button
                                @click="activeTab.scan_mode = 'file'"
                                :class="['px-3 py-2 rounded text-sm font-medium', activeTab.scan_mode === 'file' ? 'bg-emerald-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600']"
                            >
                                Par fichier
                            </button>
                            <button
                                @click="activeTab.scan_mode = 'folder'"
                                :class="['px-3 py-2 rounded text-sm font-medium', activeTab.scan_mode === 'folder' ? 'bg-emerald-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600']"
                            >
                                Par dossier
                            </button>
                        </div>
                    </div>
                    
                    <div v-if="activeTab.scan_mode === 'folder'">
                        <label class="block text-sm font-medium mb-2">Vérifier les dossiers synchronisés dans</label>
                        <div class="flex gap-2">
                            <button
                                @click="activeTab.check_column = 'a'"
                                :class="['px-3 py-2 rounded text-sm font-medium', activeTab.check_column === 'a' ? 'bg-emerald-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600']"
                            >
                                Colonne A
                            </button>
                            <button
                                @click="activeTab.check_column = 'b'"
                                :class="['px-3 py-2 rounded text-sm font-medium', activeTab.check_column === 'b' ? 'bg-emerald-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600']"
                            >
                                Colonne B
                            </button>
                            <button
                                @click="activeTab.check_column = 'both'"
                                :class="['px-3 py-2 rounded text-sm font-medium', activeTab.check_column === 'both' ? 'bg-emerald-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600']"
                            >
                                Les deux
                            </button>
                        </div>
                    </div>
                </div>
                
                <div v-if="activeTab.scan_mode === 'folder'" class="mt-4 text-center">
                    <button
                        @click="runScanFolder"
                        :disabled="isScanning"
                        class="bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {{ isScanning ? 'Scan en cours...' : `Lancer le scan par dossier '${activeTab.name}'` }}
                    </button>
                    <p class="text-xs text-gray-400 mt-2">
                        Un dossier est considéré comme synchronisé s'il contient au moins un fichier avec un hardlink
                    </p>
                </div>
            </div>
        </div>
        <p v-if="saveSuccessMessage" class="text-center text-green-400 mt-2">{{ saveSuccessMessage }}</p>
        <p v-if="error" class="text-center text-red-400 mt-2">{{ error }}</p>
      </header>
      
      <main>
        <div v-if="config">
          <div class="flex mb-4 border-b border-gray-700">
            <template v-for="tab in config.tabs" :key="tab.id">
              <div v-if="isEditingTabName && editingTabId === tab.id" class="flex items-center">
                <input
                  v-model="newTabName"
                  @keyup.enter="saveTabName"
                  @keyup.escape="cancelEditTabName"
                  class="bg-gray-700 text-white px-2 py-1 rounded text-sm"
                  placeholder="Nom de l'onglet"
                  ref="tabNameInput"
                >
                <button @click="saveTabName" class="ml-2 bg-green-600 hover:bg-green-700 text-white text-xs px-2 py-1 rounded">
                  ✓
                </button>
                <button @click="cancelEditTabName" class="ml-1 bg-red-600 hover:bg-red-700 text-white text-xs px-2 py-1 rounded">
                  ✗
                </button>
              </div>
              <div v-else class="flex items-center">
                <button
                  @click="switchTab(tab.id)"
                  :class="[
                    'px-4 py-2 font-semibold',
                    activeTabId === tab.id ? 'border-b-2 border-emerald-400 text-emerald-400' : 'text-gray-400 hover:bg-gray-800'
                  ]">
                  {{ tab.name }}
                </button>
                <button
                  @click="startEditTabName(tab.id, tab.name)"
                  class="ml-1 text-gray-500 hover:text-gray-300 text-xs"
                  title="Renommer l'onglet"
                >
                  ✏️
                </button>
                <button
                  v-if="config.tabs.length > 1"
                  @click="removeTab(tab.id)"
                  class="ml-1 text-gray-500 hover:text-red-400 text-xs"
                  title="Supprimer l'onglet"
                >
                  ✕
                </button>
              </div>
            </template>
            
            <div v-if="isAddingNewTab" class="flex items-center ml-2">
              <input
                v-model="newTabName"
                @keyup.enter="addNewTab"
                @keyup.escape="cancelAddNewTab"
                class="bg-gray-700 text-white px-2 py-1 rounded text-sm"
                placeholder="Nom de l'onglet"
                ref="newTabNameInput"
              >
              <button @click="addNewTab" class="ml-2 bg-green-600 hover:bg-green-700 text-white text-xs px-2 py-1 rounded">
                ✓
              </button>
              <button @click="cancelAddNewTab" class="ml-1 bg-red-600 hover:bg-red-700 text-white text-xs px-2 py-1 rounded">
                ✗
              </button>
            </div>
            <button
              v-else
              @click="startAddNewTab"
              class="ml-2 text-gray-500 hover:text-emerald-400 text-sm"
              title="Ajouter un onglet"
            >
              + Onglet
            </button>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
  <div class="bg-gray-800 p-4 rounded-lg border border-gray-700 flex flex-col">
    <div class="flex items-center justify-between mb-4 border-b border-gray-600 pb-2">
      <h2 class="text-xl font-bold">Colonne A</h2>
      <input
        type="text"
        :value="activeTab?.name_a || ''"
        @input="updateColumnName($event.target.value, 'a')"
        class="bg-gray-700 text-white px-2 py-1 rounded text-sm w-32"
        placeholder="Nom de la colonne"
      >
    </div>
    <div class="space-y-2 min-h-[200px] flex-grow">
      <div v-for="path in activeTab?.paths_a || []" :key="path" class="flex items-center justify-between bg-gray-700 p-2 rounded font-mono text-sm">
        <span>{{ path }}</span>
        <button @click="removePath(activeTabId, 'paths_a', path)" class="text-red-400 hover:text-red-300 font-bold px-2">X</button>
      </div>
    </div>
    <button @click="openBrowser(activeTabId, 'paths_a')" class="w-full mt-4 py-2 text-2xl bg-emerald-600 rounded hover:bg-emerald-700 transition-colors">+</button>
  </div>
  
  <div class="bg-gray-800 p-4 rounded-lg border border-gray-700 flex flex-col">
    <div class="flex items-center justify-between mb-4 border-b border-gray-600 pb-2">
      <h2 class="text-xl font-bold">Colonne B</h2>
      <input
        type="text"
        :value="activeTab?.name_b || ''"
        @input="updateColumnName($event.target.value, 'b')"
        class="bg-gray-700 text-white px-2 py-1 rounded text-sm w-32"
        placeholder="Nom de la colonne"
      >
    </div>
    <div class="space-y-2 min-h-[200px] flex-grow">
      <div v-for="path in activeTab?.paths_b || []" :key="path" class="flex items-center justify-between bg-gray-700 p-2 rounded font-mono text-sm">
        <span>{{ path }}</span>
        <button @click="removePath(activeTabId, 'paths_b', path)" class="text-red-400 hover:text-red-300 font-bold px-2">X</button>
      </div>
    </div>
    <button @click="openBrowser(activeTabId, 'paths_b')" class="w-full mt-4 py-2 text-2xl bg-emerald-600 rounded hover:bg-emerald-700 transition-colors">+</button>
  </div>
</div>

          <div v-if="scanResults" class="mt-8 bg-gray-800 p-4 rounded-lg border border-gray-700">
            <h2 class="text-2xl font-bold mb-4 border-b border-gray-600 pb-2">Résultats du Scan</h2>
            
            <!-- Calcul du nombre total de fichiers et du pourcentage de synchronisation -->
            <div v-if="scanResults" class="mb-4">
              <p class="text-sm text-gray-400">
                Total des fichiers analysés : {{ scanResults.synced.length + scanResults.orphans_a.length + scanResults.orphans_b.length + scanResults.conflicts.length }}
                ({{ Math.round((scanResults.synced.length / (scanResults.synced.length + scanResults.orphans_a.length + scanResults.orphans_b.length + scanResults.conflicts.length)) * 100) }}% synchronisés)
              </p>
            </div>
            
            <!-- Affichage en 3 colonnes -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <!-- Colonne 1: Synchronisés -->
              <div class="bg-gray-700/30 p-3 rounded-lg">
                <h3 class="text-xl font-semibold text-green-400 mb-2">✅ Synchronisés ({{ scanResults.synced.length }}/{{ scanResults.synced.length + scanResults.orphans_a.length + scanResults.orphans_b.length + scanResults.conflicts.length }})</h3>
                <div class="space-y-2 font-mono text-xs max-h-60 overflow-y-auto">
                  <div v-for="item in scanResults.synced" :key="item.path_a" class="p-2 bg-gray-700 rounded">
                    <div class="font-semibold text-green-300 mb-1">{{ activeTab?.name_a || 'Colonne A' }}:</div>
                    <div class="mb-2">{{ item.path_a }}</div>
                    <div class="font-semibold text-green-300 mb-1">{{ activeTab?.name_b || 'Colonne B' }}:</div>
                    <div class="text-gray-400">{{ item.path_b }}</div>
                  </div>
                </div>
                
                <!-- Afficher les dossiers synchronisés si on est en mode scan par dossier -->
                <div v-if="activeTab?.scan_mode === 'folder' && scanResults.synced_folders" class="mt-4">
                  <h4 class="text-md font-semibold text-green-300 mb-2">Dossiers synchronisés</h4>
                  <div class="space-y-1">
                    <div v-if="scanResults.synced_folders.A && scanResults.synced_folders.A.length > 0" class="mb-2">
                      <div class="font-semibold text-green-200 mb-1">{{ activeTab?.name_a || 'Colonne A' }}:</div>
                      <div v-for="folder in scanResults.synced_folders.A" :key="folder" class="p-1 bg-green-900/30 rounded text-xs">
                        {{ folder }}
                      </div>
                    </div>
                    <div v-if="scanResults.synced_folders.B && scanResults.synced_folders.B.length > 0">
                      <div class="font-semibold text-green-200 mb-1">{{ activeTab?.name_b || 'Colonne B' }}:</div>
                      <div v-for="folder in scanResults.synced_folders.B" :key="folder" class="p-1 bg-green-900/30 rounded text-xs">
                        {{ folder }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Colonne 2: Orphelins A -->
              <div class="bg-gray-700/30 p-3 rounded-lg">
                <div class="flex justify-between items-center mb-2">
                  <h3 class="text-xl font-semibold text-yellow-400">⚠️ Orphelins {{ activeTab?.name_a || 'Colonne A' }} ({{ scanResults.orphans_a.length }}/{{ scanResults.synced.length + scanResults.orphans_a.length + scanResults.orphans_b.length + scanResults.conflicts.length }})</h3>
                  <button
                    v-if="activeTab?.name === 'Séries' && scanResults.orphans_a.length > 0"
                    @click="openSeriesOrphansModal('a')"
                    class="bg-yellow-600 hover:bg-yellow-700 text-white text-xs px-2 py-1 rounded"
                  >
                    Voir par série
                  </button>
                </div>
                <div class="space-y-2 font-mono text-xs max-h-60 overflow-y-auto">
                   <div v-for="path in scanResults.orphans_a" :key="path" class="p-2 bg-yellow-900/50 rounded">
                     {{ path }}
                   </div>
                </div>
              </div>

              <!-- Colonne 3: Orphelins B -->
              <div class="bg-gray-700/30 p-3 rounded-lg">
                <div class="flex justify-between items-center mb-2">
                  <h3 class="text-xl font-semibold text-yellow-400">⚠️ Orphelins {{ activeTab?.name_b || 'Colonne B' }} ({{ scanResults.orphans_b.length }}/{{ scanResults.synced.length + scanResults.orphans_a.length + scanResults.orphans_b.length + scanResults.conflicts.length }})</h3>
                  <button
                    v-if="activeTab?.name === 'Séries' && scanResults.orphans_b.length > 0"
                    @click="openSeriesOrphansModal('b')"
                    class="bg-yellow-600 hover:bg-yellow-700 text-white text-xs px-2 py-1 rounded"
                  >
                    Voir par série
                  </button>
                </div>
                <div class="space-y-2 font-mono text-xs max-h-60 overflow-y-auto">
                  <div v-for="path in scanResults.orphans_b" :key="path" class="p-2 bg-yellow-900/50 rounded">
                    {{ path }}
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Section Conflits (en dessous des 3 colonnes) -->
            <div v-if="scanResults.conflicts.length > 0" class="mt-6 bg-gray-700/30 p-3 rounded-lg">
              <h3 class="text-xl font-semibold text-red-400 mb-2">❌ Conflits ({{ scanResults.conflicts.length }}/{{ scanResults.synced.length + scanResults.orphans_a.length + scanResults.orphans_b.length + scanResults.conflicts.length }})</h3>
              <p class="text-sm text-gray-400 mb-2">Cas anormaux (ex: plus de 2 hardlinks). À vérifier manuellement.</p>
              <div class="space-y-2 font-mono text-xs max-h-60 overflow-y-auto">
                <div v-for="(conflict, index) in scanResults.conflicts" :key="index" class="p-2 bg-red-900/50 rounded">
                  <div class="font-semibold text-red-300 mb-1">Paths {{ activeTab?.name_a || 'Colonne A' }}:</div>
                  <div v-for="path in conflict.paths_a" :key="path" class="mb-1">{{ path }}</div>
                  <div class="font-semibold text-red-300 mb-1">Paths {{ activeTab?.name_b || 'Colonne B' }}:</div>
                  <div v-for="path in conflict.paths_b" :key="path" class="mb-1">{{ path }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <FileBrowserModal
        v-if="isModalOpen"
        @close="isModalOpen = false"
        @select-folder="handleFolderSelect"
      />
      
      <SeriesOrphansModal
        v-if="isSeriesOrphansModalOpen"
        :is-open="isSeriesOrphansModalOpen"
        :orphans="seriesOrphansType === 'a' ? scanResults?.orphans_a || [] : scanResults?.orphans_b || []"
        :column-name="seriesOrphansType === 'a' ? (activeTab?.name_a || 'Colonne A') : (activeTab?.name_b || 'Colonne B')"
        @close="closeSeriesOrphansModal"
      />
    </div>
  </div>
</template>