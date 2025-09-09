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
const scanProgress = ref(0)
const scanTotal = ref(0)
const scanCurrentFile = ref('')
let pollingInterval = null

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

// État pour la suppression des orphelins
const isDeletingOrphans = ref(false)
const deleteProgress = ref(0)
const deleteTotal = ref(0)
const deleteCurrentFile = ref('')
const deleteResults = ref(null)
const showDeleteConfirmModal = ref(false)
const deletePreview = ref(null)
const deleteColumn = ref('b') // 'a', 'b' ou 'both'
let deletePollingInterval = null

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

async function pollScanStatus(taskId) {
  let pollAttempts = 0
  const maxPollAttempts = 3600 // 1 heure maximum (3600 secondes)
  
  pollingInterval = setInterval(async () => {
    pollAttempts++
    
    // Arrêter le polling après le nombre maximum de tentatives
    if (pollAttempts > maxPollAttempts) {
      clearInterval(pollingInterval)
      error.value = "Timeout: Le scan a pris trop de temps. Veuillez relancer le scan."
      isScanning.value = false
      return
    }
    
    try {
      const response = await axios.get(`${API_BASE_URL}/api/scan/status/${taskId}`)
      const task = response.data
      scanProgress.value = task.progress
      scanTotal.value = task.total
      scanCurrentFile.value = task.current_file

      if (task.status === 'completed') {
        clearInterval(pollingInterval)
        scanResults.value = task.results
        isScanning.value = false
        console.log('✅ Scan terminé avec succès')
      } else if (task.status === 'error') {
        clearInterval(pollingInterval)
        error.value = `Erreur du scan: ${task.error || 'Erreur inconnue'}`
        isScanning.value = false
        console.error('❌ Erreur lors du scan:', task.error)
      } else if (task.status === 'timeout') {
        clearInterval(pollingInterval)
        error.value = "Le scan a expiré. Veuillez relancer le scan sur un dossier plus petit ou vérifier les logs."
        isScanning.value = false
        console.warn('⏰ Scan expiré')
      }
    } catch (e) {
      console.error('❌ Erreur lors de la récupération du statut:', e)
      
      // Si c'est une erreur 404 (tâche non trouvée), arrêter le polling
      if (e.response && e.response.status === 404) {
        clearInterval(pollingInterval)
        error.value = "Tâche de scan non trouvée. Cela peut indiquer un problème de configuration du serveur."
        isScanning.value = false
      } else {
        // Pour les autres erreurs, continuer le polling quelques fois avant d'abandonner
        if (pollAttempts % 5 === 0) { // Log d'erreur tous les 5 essais
          console.warn(`⚠️ Erreur de polling (tentative ${pollAttempts}/${maxPollAttempts}):`, e.message)
        }
        
        // Arrêter après 10 erreurs consécutives
        if (pollAttempts > 10 && pollAttempts % 10 === 0) {
          clearInterval(pollingInterval)
          error.value = "Erreurs répétées lors de la récupération de l'état du scan. Veuillez vérifier la connexion."
          isScanning.value = false
        }
      }
    }
  }, 1000)
}

async function startScan(url) {
    isScanning.value = true
    scanResults.value = null
    error.value = null
    scanProgress.value = 0
    scanTotal.value = 0
    scanCurrentFile.value = ''
    if (pollingInterval) clearInterval(pollingInterval)

    try {
        const response = await axios.post(url)
        const taskId = response.data.task_id
        pollScanStatus(taskId)
    } catch (e) {
        console.error('Erreur lors du lancement du scan', e)
        if (e.response && e.response.data && e.response.data.detail) {
            error.value = `Erreur du scan : ${e.response.data.detail}`
        } else {
            error.value = "Une erreur est survenue lors du lancement du scan."
        }
        isScanning.value = false
    }
}

function runScanFolder() {
    startScan(`${API_BASE_URL}/api/scan-folder/${activeTabId.value}`)
}

function runScan() {
    startScan(`${API_BASE_URL}/api/scan/${activeTabId.value}`)
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
      max_depth: -1,
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

// Fonctions pour la suppression des orphelins
async function previewDeleteOrphans(column = 'b') {
  try {
    deleteColumn.value = column
    const response = await axios.get(`${API_BASE_URL}/api/delete-orphans/${activeTabId.value}?column=${column}`)
    deletePreview.value = response.data
    showDeleteConfirmModal.value = true
  } catch (e) {
    console.error('Erreur lors de la prévisualisation', e)
    if (e.response && e.response.data && e.response.data.detail) {
      error.value = `Erreur de prévisualisation : ${e.response.data.detail}`
    } else {
      error.value = "Une erreur est survenue lors de la prévisualisation."
    }
  }
}

async function confirmDeleteOrphans() {
  showDeleteConfirmModal.value = false
  isDeletingOrphans.value = true
  deleteResults.value = null
  error.value = null
  deleteProgress.value = 0
  deleteTotal.value = 0
  deleteCurrentFile.value = ''
  if (deletePollingInterval) clearInterval(deletePollingInterval)

  try {
    const response = await axios.post(`${API_BASE_URL}/api/delete-orphans/${activeTabId.value}?column=${deleteColumn.value}&confirm=true`)
    const taskId = response.data.task_id
    pollDeleteStatus(taskId)
  } catch (e) {
    console.error('Erreur lors du lancement de la suppression', e)
    if (e.response && e.response.data && e.response.data.detail) {
      error.value = `Erreur de suppression : ${e.response.data.detail}`
    } else {
      error.value = "Une erreur est survenue lors du lancement de la suppression."
    }
    isDeletingOrphans.value = false
  }
}

async function pollDeleteStatus(taskId) {
  let pollAttempts = 0
  const maxPollAttempts = 3600 // 1 heure maximum
  
  deletePollingInterval = setInterval(async () => {
    pollAttempts++
    
    if (pollAttempts > maxPollAttempts) {
      clearInterval(deletePollingInterval)
      error.value = "Timeout: La suppression a pris trop de temps."
      isDeletingOrphans.value = false
      return
    }
    
    try {
      const response = await axios.get(`${API_BASE_URL}/api/scan/status/${taskId}`)
      const task = response.data
      deleteProgress.value = task.progress
      deleteTotal.value = task.total
      deleteCurrentFile.value = task.current_file

      if (task.status === 'completed') {
        clearInterval(deletePollingInterval)
        deleteResults.value = task.results
        isDeletingOrphans.value = false
        // Vider les résultats de scan pour forcer un nouveau scan
        scanResults.value = null
        console.log('✅ Suppression terminée avec succès')
      } else if (task.status === 'error') {
        clearInterval(deletePollingInterval)
        error.value = `Erreur de suppression: ${task.error || 'Erreur inconnue'}`
        isDeletingOrphans.value = false
        console.error('❌ Erreur lors de la suppression:', task.error)
      } else if (task.status === 'timeout') {
        clearInterval(deletePollingInterval)
        error.value = "La suppression a expiré."
        isDeletingOrphans.value = false
        console.warn('⏰ Suppression expirée')
      }
    } catch (e) {
      console.error('❌ Erreur lors de la récupération du statut de suppression:', e)
      
      if (e.response && e.response.status === 404) {
        clearInterval(deletePollingInterval)
        error.value = "Tâche de suppression non trouvée."
        isDeletingOrphans.value = false
      } else if (pollAttempts > 10 && pollAttempts % 10 === 0) {
        clearInterval(deletePollingInterval)
        error.value = "Erreurs répétées lors de la récupération de l'état de suppression."
        isDeletingOrphans.value = false
      }
    }
  }, 1000)
}

function cancelDeleteOrphans() {
  showDeleteConfirmModal.value = false
  deletePreview.value = null
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
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
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
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Profondeur maximale</label>
                        <div class="flex items-center gap-2">
                            <input
                                type="number"
                                v-model.number="activeTab.max_depth"
                                min="-1"
                                max="100"
                                class="bg-gray-700 text-white px-3 py-2 rounded text-sm w-20"
                                placeholder="-1"
                            />
                            <span class="text-xs text-gray-400">(-1 = illimitée)</span>
                        </div>
                        <p class="text-xs text-gray-500 mt-1">Limite la profondeur de parcours des dossiers</p>
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
       <!-- Section pour la barre de progression -->
       <div v-if="isScanning" class="my-4 p-4 bg-gray-800 rounded-lg border border-gray-700">
           <h3 class="text-lg font-semibold text-center mb-2">Scan en cours...</h3>
           <div class="w-full bg-gray-700 rounded-full h-4 mb-2">
               <div class="bg-emerald-500 h-4 rounded-full" :style="{ width: (scanTotal > 0 ? (scanProgress / scanTotal) * 100 : 0) + '%' }"></div>
           </div>
           <div class="text-center text-sm text-gray-400">
               <p>{{ scanProgress }} / {{ scanTotal }} fichiers scannés</p>
               <p v-if="scanCurrentFile" class="font-mono text-xs mt-1 truncate">{{ scanCurrentFile }}</p>
           </div>
       </div>

        <!-- Section pour la barre de progression de suppression -->
        <div v-if="isDeletingOrphans" class="my-4 p-4 bg-red-900/20 rounded-lg border border-red-700">
            <h3 class="text-lg font-semibold text-center mb-2 text-red-400">🗑️ Suppression des orphelins en cours...</h3>
            <div class="w-full bg-gray-700 rounded-full h-4 mb-2">
                <div class="bg-red-500 h-4 rounded-full" :style="{ width: (deleteTotal > 0 ? (deleteProgress / deleteTotal) * 100 : 0) + '%' }"></div>
            </div>
            <div class="text-center text-sm text-gray-400">
                <p>{{ deleteProgress }} / {{ deleteTotal }} fichiers traités</p>
                <p v-if="deleteCurrentFile" class="font-mono text-xs mt-1 truncate">{{ deleteCurrentFile }}</p>
            </div>
        </div>

        <!-- Section pour afficher les résultats de suppression -->
        <div v-if="deleteResults" class="my-4 p-4 bg-green-900/20 rounded-lg border border-green-700">
            <h3 class="text-lg font-semibold text-center mb-2 text-green-400">✅ Suppression terminée</h3>
            <div class="text-center text-sm text-gray-300">
                <p class="mb-2">{{ deleteResults.total_deleted }} fichier(s) supprimé(s)</p>
                <p v-if="deleteResults.total_errors > 0" class="text-red-400">{{ deleteResults.total_errors }} erreur(s) rencontrée(s)</p>
                <p class="text-xs text-gray-500 mt-2">Vous pouvez maintenant relancer un scan pour voir les changements ou demander à Radarr de retélécharger</p>
            </div>
        </div>

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
                  <div class="flex gap-2">
                    <button
                      v-if="scanResults.orphans_b.length > 0"
                      @click="previewDeleteOrphans('b')"
                      :disabled="isDeletingOrphans"
                      class="bg-red-600 hover:bg-red-700 text-white text-xs px-2 py-1 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Supprimer tous les fichiers orphelins de cette colonne"
                    >
                      🗑️ Supprimer
                    </button>
                    <button
                      v-if="activeTab?.name === 'Séries' && scanResults.orphans_b.length > 0"
                      @click="openSeriesOrphansModal('b')"
                      class="bg-yellow-600 hover:bg-yellow-700 text-white text-xs px-2 py-1 rounded"
                    >
                      Voir par série
                    </button>
                  </div>
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

      <!-- Modale de confirmation de suppression -->
      <div v-if="showDeleteConfirmModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-gray-800 p-6 rounded-lg border border-gray-700 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
          <h2 class="text-2xl font-bold text-red-400 mb-4">⚠️ Confirmation de suppression</h2>
          
          <div v-if="deletePreview" class="mb-6">
            <p class="text-lg text-gray-300 mb-4">
              Vous êtes sur le point de supprimer <strong class="text-red-400">{{ deletePreview.total_deleted }} fichier(s) orphelin(s)</strong>
              de la colonne <strong>{{ deleteColumn === 'a' ? (activeTab?.name_a || 'A') : (activeTab?.name_b || 'B') }}</strong>.
            </p>
            
            <div class="bg-red-900/20 p-4 rounded-lg border border-red-700 mb-4">
              <h3 class="text-lg font-semibold text-red-300 mb-2">⚠️ ATTENTION</h3>
              <ul class="text-sm text-gray-300 space-y-1">
                <li>• Cette action est <strong>irréversible</strong></li>
                <li>• Les fichiers seront définitivement supprimés du disque</li>
                <li>• Les dossiers vides seront également supprimés</li>
                <li>• Assurez-vous d'avoir une sauvegarde si nécessaire</li>
              </ul>
            </div>

            <div class="bg-gray-700/50 p-4 rounded-lg mb-4">
              <h4 class="text-md font-semibold text-gray-300 mb-2">Fichiers à supprimer ({{ deletePreview.deleted_files.length }}) :</h4>
              <div class="max-h-40 overflow-y-auto space-y-1">
                <div v-for="file in deletePreview.deleted_files.slice(0, 20)" :key="file.path" class="text-xs font-mono text-gray-400 p-1 bg-gray-800 rounded">
                  {{ file.path }}
                  <span class="text-gray-500">({{ Math.round(file.size / 1024 / 1024) }} MB)</span>
                </div>
                <div v-if="deletePreview.deleted_files.length > 20" class="text-xs text-gray-500 p-1">
                  ... et {{ deletePreview.deleted_files.length - 20 }} fichier(s) de plus
                </div>
              </div>
            </div>

            <div v-if="deletePreview.errors && deletePreview.errors.length > 0" class="bg-yellow-900/20 p-4 rounded-lg border border-yellow-700 mb-4">
              <h4 class="text-md font-semibold text-yellow-300 mb-2">⚠️ Fichiers avec des problèmes ({{ deletePreview.errors.length }}) :</h4>
              <div class="max-h-20 overflow-y-auto space-y-1">
                <div v-for="error in deletePreview.errors.slice(0, 10)" :key="error.path" class="text-xs font-mono text-yellow-400">
                  {{ error.path }} - {{ error.error }}
                </div>
              </div>
            </div>
          </div>

          <div class="flex justify-end space-x-4">
            <button
              @click="cancelDeleteOrphans"
              class="bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded"
            >
              Annuler
            </button>
            <button
              @click="confirmDeleteOrphans"
              class="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded"
            >
              🗑️ Confirmer la suppression
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>