// Settings management
const Settings = {
    // Default settings
    defaults: {
        language: 'sv',
        theme: 'light'
    },

    // Cache for current settings (loaded from .ini file)
    _cachedSettings: null,

    // Load settings from .ini file via Python API
    async load() {
        try {
            // Check if pywebview API is available
            if (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.getSettings) {
                const settings = await pywebview.api.getSettings();
                this._cachedSettings = settings;
                return settings;
            } else {
                // Fallback to defaults if API not available yet
                return { ...this.defaults };
            }
        } catch (error) {
            console.error('Error loading settings:', error);
            return { ...this.defaults };
        }
    },

    // Save settings to .ini file via Python API
    async save(settings) {
        try {
            if (typeof pywebview !== 'undefined' && pywebview.api && pywebview.api.saveSettings) {
                const result = await pywebview.api.saveSettings(settings);
                if (result.success) {
                    this._cachedSettings = settings;
                    return true;
                } else {
                    console.error('Error saving settings:', result.message);
                    return false;
                }
            } else {
                console.warn('Settings API not available');
                return false;
            }
        } catch (error) {
            console.error('Error saving settings:', error);
            return false;
        }
    },

    // Get current settings (synchronous - returns cached or defaults)
    get() {
        return this._cachedSettings || { ...this.defaults };
    },

    // Update a specific setting (async)
    async update(key, value) {
        const settings = await this.load();
        settings[key] = value;
        await this.save(settings);
        return settings;
    }
};

// Translation dictionary
const translations = {
    sv: {
        yourTranscriptions: 'Dina transkriberingar',
        newTranscription: 'Ny transkribering',
        selectOrCreate: 'Välj eller skapa en transkribering',
        selectOrCreateDesc: 'Välj eller skapa en transkribering i den vänstra panelen',
        settings: 'Inställningar',
        general: 'Allmänt',
        appLanguage: 'Språk för applikationen',
        themeMode: 'Tema',
        swedish: 'Svenska',
        english: 'English',
        lightMode: 'Ljust läge',
        darkMode: 'Mörkt läge',
        models: 'Modeller',
        modelsDesc: 'Se nedladdade AI-modeller och ta bort dem för att frigöra diskutrymme.',
        modelsNone: 'Inga modeller är nedladdade ännu.',
        modelsHeaderName: 'Modell',
        modelsHeaderLanguage: 'Språk',
        modelsHeaderSize: 'Storlek',
        deleteModel: 'Ta bort',
        modelsModelId: 'Modell-ID',
        modelsStorage: 'Lagring',
        modelsCachePath: 'Sökväg',
        confirmDeleteModel: 'Är du säker på att du vill ta bort denna modell? Detta frigör diskutrymme men modellen måste laddas ner igen vid nästa användning.',
        modelLangSv: 'Svenska',
        modelLangEn: 'Engelska',
        modelSizeTiny: 'Liten',
        modelSizeSmall: 'Small',
        modelSizeMedium: 'Medium',
        modelSizeLarge: 'Stor',
        backToOverview: 'Tillbaka till översikt',
        selectFile: 'Välj audio- eller videofil',
        languageAndModel: 'Välj Språk & Modell',
        startTranscription: 'Starta transkribering',
        activity: 'Aktivitet',
        languageOption1: 'Svenska',
        languageOption2: 'Engelska',
        modelOption1: 'Liten Modell (Snabb, mindre exakt)',
        modelOption2: 'Medium Modell (Bra resultat, långsam)',
        modelOption3: 'Stor Modell (Bäst resultat, väldigt långsam)',
        openInNotepad: 'Öppna som textfil',
        skipBack: 'Spola tillbaka 10 sekunder',
        skipForward: 'Spola fram 10 sekunder',
        toggleAutoscroll: 'Auto-skroll',
        transcribing: 'Transkriberar...',
        noFilesSelected: 'Inga filer valda. Vänligen lägg till filer först.',
        settingsNotFound: 'Inställningar hittades inte',
        startingTranscription: 'Startar transkribering för',
        file: 'fil',
        files: 'filer',
        language: 'Språk',
        model: 'Modell',
        error: 'Fel',
        errorTranscribing: 'Fel vid transkribering',
        transcriptionComplete: 'Transkribering klar',
        allTranscriptionsCompleted: 'Alla transkriberingar är klara!',
        errorStartingTranscription: 'Fel vid start av transkribering',
        removeFile: 'Ta bort fil',
        failedToOpenNotepad: 'Misslyckades med att öppna transkriberingen som textfil',
        errorOpeningNotepad: 'Fel vid öppning av transkriberingen som textfil',
        deleteTranscription: 'Ta bort transkribering',
        confirmDeleteTranscription: 'Är du säker på att du vill ta bort den här transkriberingen? Detta tar bort alla tillhörande filer från din dator.',
        transcriptionDeleted: 'Transkriberingen togs bort.',
        deleteTranscriptionFailed: 'Misslyckades med att ta bort transkriberingen'
    },
    en: {
        yourTranscriptions: 'Your Transcriptions',
        newTranscription: 'New Transcription',
        selectOrCreate: 'Select or create a transcription',
        selectOrCreateDesc: 'Select or create a transcription in the left panel',
        settings: 'Settings',
        general: 'General',
        appLanguage: 'Application Language',
        themeMode: 'Theme',
        swedish: 'Svenska',
        english: 'English',
        lightMode: 'Light Mode',
        darkMode: 'Dark Mode',
        models: 'Models',
        modelsDesc: 'View downloaded AI models and remove them to free up disk space.',
        modelsNone: 'No models have been downloaded yet.',
        modelsHeaderName: 'Model',
        modelsHeaderLanguage: 'Language',
        modelsHeaderSize: 'Size',
        deleteModel: 'Delete',
        modelsModelId: 'Model ID',
        modelsStorage: 'Storage',
        modelsCachePath: 'Path',
        confirmDeleteModel: 'Are you sure you want to delete this model? This will free disk space but the model must be downloaded again next time you use it.',
        modelLangSv: 'Swedish',
        modelLangEn: 'English',
        modelSizeTiny: 'Tiny',
        modelSizeSmall: 'Small',
        modelSizeMedium: 'Medium',
        modelSizeLarge: 'Large',
        backToOverview: 'Back to overview',
        selectFile: 'Choose audio or video file',
        languageAndModel: 'Select Language & Model',
        startTranscription: 'Start Transcription',
        activity: 'Activity',
        languageOption1: 'Swedish',
        languageOption2: 'English',
        modelOption1: 'Small Model (Fast, less accurate)',
        modelOption2: 'Medium Model (Good results, slow)',
        modelOption3: 'Big Model (Best results, very slow)',
        openInNotepad: 'Open as text file',
        skipBack: 'Skip back 10 seconds',
        skipForward: 'Skip forward 10 seconds',
        toggleAutoscroll: 'Toggle auto-scroll',
        transcribing: 'Transcribing...',
        noFilesSelected: 'No files selected. Please add files first.',
        settingsNotFound: 'Settings not found',
        startingTranscription: 'Starting transcription for',
        file: 'file',
        files: 'files',
        language: 'Language',
        model: 'Model',
        error: 'Error',
        errorTranscribing: 'Error transcribing',
        transcriptionComplete: 'Transcription complete',
        allTranscriptionsCompleted: 'All transcriptions completed!',
        errorStartingTranscription: 'Error starting transcription',
        removeFile: 'Remove file',
        failedToOpenNotepad: 'Failed to open transcription as text file',
        errorOpeningNotepad: 'Error opening transcription as text file',
        deleteTranscription: 'Delete transcription',
        confirmDeleteTranscription: 'Are you sure you want to delete this transcription? This removes its files from your computer.',
        transcriptionDeleted: 'Transcription deleted.',
        deleteTranscriptionFailed: 'Failed to delete transcription'
    }
};

// Apply theme
function applyTheme(theme) {
    if (theme === 'dark') {
        document.body.classList.add('dark-mode');
    } else {
        document.body.classList.remove('dark-mode');
    }
}

// Helper function to get translation for a key
function getTranslation(key) {
    const settings = Settings.get();
    const langKey = settings.language || 'sv';
    const t = translations[langKey] || translations['sv'];
    return t[key] || key;
}

// Apply language
function applyLanguage(lang) {
    const t = translations[lang] || translations['sv'];
    
    // Update all translatable elements
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (t[key]) {
            element.textContent = t[key];
        }
    });

    // Re-render models list (if present) so labels/buttons use the current language
    if (typeof renderModelsList === 'function') {
        renderModelsList();
    }
    
    // Update dynamically generated content that uses translations
    if (typeof updateDynamicTranslations === 'function') {
        updateDynamicTranslations();
    }
}

// Cache for downloaded models shown in the settings modal
let _downloadedModels = [];

// Format number of bytes as a human readable string
function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let value = bytes;
    while (value >= 1024 && i < units.length - 1) {
        value /= 1024;
        i++;
    }
    return `${value.toFixed(1)} ${units[i]}`;
}

// Map model info to localized display strings
function getModelDisplayStrings(model) {
    const settings = Settings.get();
    const langKey = settings.language || 'sv';
    const t = translations[langKey] || translations['sv'];

    const languageLabel =
        model.language === 'sv' ? t.modelLangSv :
        model.language === 'en' ? t.modelLangEn :
        model.language;

    let sizeKey = 'modelSizeMedium';
    switch (model.modelSize) {
        case 'tiny':
            sizeKey = 'modelSizeTiny';
            break;
        case 'small':
            sizeKey = 'modelSizeSmall';
            break;
        case 'medium':
            sizeKey = 'modelSizeMedium';
            break;
        case 'large':
            sizeKey = 'modelSizeLarge';
            break;
        default:
            sizeKey = 'modelSizeMedium';
    }

    const sizeLabel = t[sizeKey] || model.modelSize;

    return {
        languageLabel,
        sizeLabel,
        deleteLabel: t.deleteModel || 'Delete',
        noneLabel: t.modelsNone || 'No models downloaded.',
        modelIdLabel: t.modelsModelId || 'Model ID',
        storageLabel: t.modelsStorage || 'Storage',
        pathLabel: t.modelsCachePath || 'Path'
    };
}

// Render the list of downloaded models inside the settings modal
function renderModelsList() {
    const container = document.getElementById('modelsList');
    if (!container) return;

    container.innerHTML = '';
    const placeholderStrings = getModelDisplayStrings({ language: 'sv', modelSize: 'medium' });
    const noneLabel = placeholderStrings.noneLabel;

    if (!_downloadedModels || _downloadedModels.length === 0) {
        const emptyEl = document.createElement('div');
        emptyEl.className = 'models-empty';
        emptyEl.textContent = noneLabel;
        container.appendChild(emptyEl);
        return;
    }

    _downloadedModels.forEach(model => {
        const {
            languageLabel,
            sizeLabel,
            deleteLabel,
            modelIdLabel,
            storageLabel,
            pathLabel
        } = getModelDisplayStrings(model);

        const modelName = model.modelId.split('/').pop() || model.modelId;
        const card = document.createElement('div');
        card.className = 'model-card';
        card.innerHTML = `
            <div class="model-card-header">
                <div>
                    <div class="model-card-title">${modelName}</div>
                    <div class="model-card-id">
                        <span class="model-card-label">${modelIdLabel}:</span>
                        <span class="model-card-value">${model.modelId}</span>
                    </div>
                </div>
                <button class="models-delete-btn" data-model-id="${model.modelId}">
                    ${deleteLabel}
                </button>
            </div>
            <div class="model-card-chips">
                <span class="model-chip">${sizeLabel}</span>
                <span class="model-chip model-chip-secondary">${languageLabel}</span>
            </div>
            <div class="model-meta-grid">
                <div class="model-meta-item">
                    <div class="model-meta-label">${storageLabel}</div>
                    <div class="model-meta-value">${formatBytes(model.sizeBytes)}</div>
                </div>
                <div class="model-meta-item model-meta-path">
                    <div class="model-meta-label">${pathLabel}</div>
                    <div class="model-meta-value" title="${model.cachePath}">${model.cachePath}</div>
                </div>
            </div>
        `;

        const deleteBtn = card.querySelector('.models-delete-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => handleDeleteModel(model.modelId));
        }

        container.appendChild(card);
    });
}

// Load downloaded models from backend
async function loadDownloadedModels() {
    try {
        if (typeof pywebview === 'undefined' || !pywebview.api || !pywebview.api.getDownloadedModels) {
            return [];
        }
        const result = await pywebview.api.getDownloadedModels();
        if (result && result.success && Array.isArray(result.models)) {
            return result.models;
        }
        return [];
    } catch (error) {
        console.error('Error loading downloaded models:', error);
        return [];
    }
}

// Handle delete model action
async function handleDeleteModel(modelId) {
    const settings = Settings.get();
    const langKey = settings.language || 'sv';
    const t = translations[langKey] || translations['sv'];
    const confirmText =
        t.confirmDeleteModel ||
        'Are you sure you want to delete this model? This will free disk space but the model must be downloaded again next time you use it.';

    const ok = window.confirm(confirmText);
    if (!ok) return;

    try {
        if (typeof pywebview === 'undefined' || !pywebview.api || !pywebview.api.deleteModel) {
            console.warn('deleteModel API not available');
            return;
        }
        const result = await pywebview.api.deleteModel(modelId);
        if (result && result.success) {
            _downloadedModels = _downloadedModels.filter(m => m.modelId !== modelId);
            renderModelsList();
        } else if (result) {
            console.error('Failed to delete model:', result.message);
        }
    } catch (error) {
        console.error('Error deleting model:', error);
    }
}

// Initialize settings on page load
async function initializeSettings() {
    // Load settings from .ini file
    const settings = await Settings.load();
    
    // Apply theme
    applyTheme(settings.theme);
    
    // Apply language
    applyLanguage(settings.language);

    // Initialize models section if present
    const modelsContainer = document.getElementById('modelsList');
    if (modelsContainer) {
        _downloadedModels = await loadDownloadedModels();
        renderModelsList();
    }
    
    // Update settings form if it exists
    const languageSelect = document.getElementById('languageSelect');
    const themeSelect = document.getElementById('themeSelect');
    
    if (languageSelect) {
        languageSelect.value = settings.language;
        languageSelect.addEventListener('change', async (e) => {
            const newSettings = await Settings.update('language', e.target.value);
            applyLanguage(newSettings.language);
        });
    }
    
    if (themeSelect) {
        themeSelect.value = settings.theme;
        themeSelect.addEventListener('change', async (e) => {
            const newSettings = await Settings.update('theme', e.target.value);
            applyTheme(newSettings.theme);
        });
    }
}

// Modal functionality
function initializeSettingsModal() {
    const settingsBtn = document.getElementById('settingsBtn');
    const settingsModal = document.getElementById('settingsModal');
    const closeModalBtn = document.getElementById('closeModalBtn');

    if (settingsBtn && settingsModal) {
        settingsBtn.addEventListener('click', () => {
            settingsModal.classList.add('show');
        });
    }

    if (closeModalBtn && settingsModal) {
        closeModalBtn.addEventListener('click', () => {
            settingsModal.classList.remove('show');
        });
    }

    // Close modal when clicking outside
    if (settingsModal) {
        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) {
                settingsModal.classList.remove('show');
            }
        });
    }
}

// Initialize when DOM is ready and pywebview is available
async function waitForPyWebview() {
    // Wait for pywebview to be available
    if (typeof pywebview === 'undefined' || !pywebview.api) {
        return new Promise((resolve) => {
            if (typeof window.addEventListener !== 'undefined') {
                window.addEventListener('pywebviewready', resolve, { once: true });
            } else {
                // Fallback: poll for pywebview
                const checkInterval = setInterval(() => {
                    if (typeof pywebview !== 'undefined' && pywebview.api) {
                        clearInterval(checkInterval);
                        resolve();
                    }
                }, 100);
            }
        });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    // Wait for pywebview to be ready before initializing settings
    await waitForPyWebview();
    await initializeSettings();
    initializeSettingsModal();
});