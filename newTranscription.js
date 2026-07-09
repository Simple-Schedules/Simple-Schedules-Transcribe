document.addEventListener('DOMContentLoaded', function() {
    const fileDropZone = document.querySelector('.file-drop-zone');
    const fileDropContent = document.querySelector('.file-drop-content p');
    const fileInput = document.getElementById('fileInput');
    const fileUploadContainer = document.querySelector('.file-upload-container');
    
    // Store file data for tracking progress
    const fileData = new Map();
    let fileCardsContainer = null;

    // Function to create file cards container if it doesn't exist
    function ensureFileCardsContainer() {
        if (!fileCardsContainer) {
            fileCardsContainer = document.createElement('div');
            fileCardsContainer.className = 'file-cards-container';
            fileUploadContainer.insertBefore(fileCardsContainer, fileDropZone);
        }
        return fileCardsContainer;
    }

    // Function to remove file cards container if empty
    function cleanupFileCardsContainer() {
        if (fileCardsContainer && fileCardsContainer.children.length === 0) {
            fileCardsContainer.remove();
            fileCardsContainer = null;
        }
    }

    // Function to get file icon based on extension
    function getFileIcon(fileName) {
        const extension = fileName.split('.').pop().toLowerCase();
        const iconMap = {
            'mp3': 'fa-file-audio',
            'wav': 'fa-file-audio',
            'mp4': 'fa-file-video',
            'avi': 'fa-file-video',
            'mov': 'fa-file-video',
            'm4a': 'fa-file-audio',
            'flac': 'fa-file-audio',
            'ogg': 'fa-file-audio'
        };
        return iconMap[extension] || 'fa-file';
    }

    // Function to create a file card
    function createFileCard(fileName, filePath) {
        const fileCard = document.createElement('div');
        fileCard.className = 'file-card';
        fileCard.dataset.fileName = fileName;
        fileCard.dataset.filePath = filePath;
        
        const fileIcon = getFileIcon(fileName);
        
        fileCard.innerHTML = `
            <div class="file-card-info">
                <i class="fa-solid ${fileIcon} file-icon"></i>
                <span class="file-name">${fileName}</span>
            </div>
            <div class="file-status">
                <span class="progress-percentage">0%</span>
                <i class="fa-solid fa-check completion-checkmark"></i>
                <button class="remove-file-btn" title="${getTranslation('removeFile')}">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
        `;
        
        // Add click handler for remove button
        const removeBtn = fileCard.querySelector('.remove-file-btn');
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeFile(fileName);
        });
        
        return fileCard;
    }

    // Function to remove a file
    function removeFile(fileName) {
        // Remove from file data
        fileData.delete(fileName);
        
        // Remove the file card from DOM
        if (fileCardsContainer) {
            const fileCard = fileCardsContainer.querySelector(`[data-file-name="${fileName}"]`);
            if (fileCard) {
                fileCard.remove();
            }
            
            // Clean up container if empty
            cleanupFileCardsContainer();
        }
        
        console.log(`File removed: ${fileName}`);
    }

    // Function to update file progress
    function updateFileProgress(fileName, progress) {
        if (!fileCardsContainer) return;
        
        const fileCard = fileCardsContainer.querySelector(`[data-file-name="${fileName}"]`);
        if (fileCard) {
            const progressElement = fileCard.querySelector('.progress-percentage');
            if (progress >= 100) {
                fileCard.classList.add('completed');
                // Update file data
                if (fileData.has(fileName)) {
                    fileData.get(fileName).progress = 100;
                    fileData.get(fileName).completed = true;
                }
            } else {
                fileCard.classList.remove('completed');
                progressElement.textContent = `${Math.round(progress)}%`;
                // Update file data
                if (fileData.has(fileName)) {
                    fileData.get(fileName).progress = progress;
                    fileData.get(fileName).completed = false;
                }
            }
        }
    }

    // Function to handle file selection
    function handleFileSelect(filePath) {
        if (filePath && filePath.length > 0) {
            // In pywebview, the dialog returns a tuple/list. Handle multiple files.
            const fileNames = filePath.map(path => path.split('\\').pop().split('/').pop());
            
            // Ensure file cards container exists
            ensureFileCardsContainer();
            
            // Create file cards for each selected file
            fileNames.forEach((fileName, index) => {
                const fileCard = createFileCard(fileName, filePath[index]);
                fileCardsContainer.appendChild(fileCard);
                
                // Store file data
                fileData.set(fileName, {
                    path: filePath[index],
                    progress: 0,
                    completed: false
                });
            });
            
            console.log('Files selected:', filePath);
        } else {
            console.log('File selection cancelled.');
        }
    }

    // --- Event Listeners ---

    // Listen for clicks on the drop zone
    fileDropZone.addEventListener('click', () => {
        // Call the Python API to open a file dialog
        pywebview.api.openFileDialog().then(handleFileSelect);
    });

    // Basic drag-and-drop visual feedback
    fileDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileDropZone.classList.add('drag-over');
    });

    fileDropZone.addEventListener('dragleave', () => {
        fileDropZone.classList.remove('drag-over');
    });

    fileDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        fileDropZone.classList.remove('drag-over');
        // pywebview's drag-and-drop gives file paths directly
        if (e.dataTransfer.files.length > 0) {
            // The 'files' object on drop is a list of paths
            const paths = Array.from(e.dataTransfer.files).map(f => f.path);
            handleFileSelect(paths);
        }
    });

    // Make functions available globally for transcription progress updates
    window.updateFileProgress = updateFileProgress;
    window.getFileData = () => fileData;
    
    // Transcription functionality
    const startTranscribingBtn = document.querySelector('.start-transcribing-btn');
    const activityContent = document.querySelector('.activity-content');
    let progressInterval = null;
    const loggedErrors = new Set();  // Track which errors we've already logged
    
    // Add activity log message
    function addActivityLog(message, type = 'info') {
        if (!activityContent) return;
        
        const now = new Date();
        const timeString = now.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
        
        const logEntry = document.createElement('div');
        logEntry.className = `activity-log-entry activity-log-${type}`;
        logEntry.textContent = `[${timeString}] ${message}`;
        activityContent.appendChild(logEntry);
        activityContent.scrollTop = activityContent.scrollHeight;
    }
    
    // Start transcription
    async function startTranscription() {
        // Clear previous error logs
        loggedErrors.clear();
        
        if (fileData.size === 0) {
            addActivityLog(getTranslation('noFilesSelected'), 'error');
            return;
        }
        
        // Get language and model settings
        const languageSelect = document.getElementById('language-select');
        const modelSelect = document.getElementById('model-select');
        
        if (!languageSelect || !modelSelect) {
            addActivityLog(getTranslation('settingsNotFound'), 'error');
            return;
        }
        
        // Map UI selections to API values
        const languageMap = {
            'Svenska': 'sv',
            'Engelska': 'en',
            'Automatisk (Använder mer data)': 'auto',
            'Swedish': 'sv',
            'English': 'en',
            'Automatic (Uses more data)': 'auto'
        };
        
        const modelMap = {
            'Liten Modell (Snabb, mindre exakt)': 'tiny',
            'Medium Modell (Bra resultat, långsam)': 'medium',
            'Stor Modell (Bäst resultat, väldigt långsam)': 'large',
            'Small Model (Fast, less accurate)': 'tiny',
            'Medium Model (Good results, slow)': 'medium',
            'Big Model (Best results, very slow)': 'large'
        };
        
        const language = languageMap[languageSelect.value] || 'sv';
        let modelSize = modelMap[modelSelect.value];
        
        // Handle fallback if mapping fails
        if (!modelSize) {
            const modelIndex = modelSelect.selectedIndex;
            const modelSizes = ['tiny', 'medium', 'large'];
            modelSize = modelSizes[modelIndex] || 'medium';
        }
        
        // Get all file paths
        const filePaths = Array.from(fileData.values()).map(f => f.path);
        
        const fileCount = filePaths.length;
        const fileWord = fileCount === 1 ? getTranslation('file') : getTranslation('files');
        addActivityLog(`${getTranslation('startingTranscription')} ${fileCount} ${fileWord}...`);
        addActivityLog(`${getTranslation('language')}: ${languageSelect.value}, ${getTranslation('model')}: ${modelSelect.value}`);
        
        // Disable button
        startTranscribingBtn.disabled = true;
        startTranscribingBtn.textContent = getTranslation('transcribing');
        
        try {
            // Start transcription
            const result = await pywebview.api.startTranscription(filePaths, language, modelSize);
            
            if (result.success) {
                // Start polling for progress
                startProgressPolling();
            } else {
                addActivityLog(`${getTranslation('error')}: ${result.message}`, 'error');
                startTranscribingBtn.disabled = false;
                startTranscribingBtn.textContent = getTranslation('startTranscription');
            }
        } catch (error) {
            addActivityLog(`${getTranslation('errorStartingTranscription')}: ${error}`, 'error');
            startTranscribingBtn.disabled = false;
            startTranscribingBtn.textContent = getTranslation('startTranscription');
        }
    }
    
    // Poll for progress updates
    function startProgressPolling() {
        if (progressInterval) {
            clearInterval(progressInterval);
        }
        
        progressInterval = setInterval(async () => {
            try {
                const allProgress = await pywebview.api.getAllProgress();
                
                // Check if all jobs are complete
                let allComplete = true;
                let hasActive = false;
                
                for (const [filePath, progress] of Object.entries(allProgress)) {
                    const fileName = filePath.split('\\').pop().split('/').pop();
                    
                    if (progress.status === 'processing' || progress.status === 'pending') {
                        allComplete = false;
                        hasActive = true;
                        updateFileProgress(fileName, progress.progress);
                    } else if (progress.status === 'completed') {
                        updateFileProgress(fileName, 100);
                    } else if (progress.status === 'error') {
                        // Only log error once per file
                        const errorKey = `${filePath}:${progress.message}`;
                        if (!loggedErrors.has(errorKey)) {
                            addActivityLog(`${getTranslation('errorTranscribing')} ${fileName}: ${progress.message}`, 'error');
                            loggedErrors.add(errorKey);
                        }
                        allComplete = false;
                    }
                }
                
                // If all complete, stop polling
                if (!hasActive && allComplete) {
                    clearInterval(progressInterval);
                    progressInterval = null;
                    startTranscribingBtn.disabled = false;
                    startTranscribingBtn.textContent = getTranslation('startTranscription');
                    addActivityLog(getTranslation('allTranscriptionsCompleted'), 'success');
                }
            } catch (error) {
                console.error('Error polling progress:', error);
            }
        }, 1000); // Poll every second
    }
    
    // Handle transcription completion callback
    window.onTranscriptionComplete = function(fileName) {
        addActivityLog(`${getTranslation('transcriptionComplete')}: ${fileName}`, 'success');
        updateFileProgress(fileName, 100);
    };
    
    // Add event listener for start button
    if (startTranscribingBtn) {
        startTranscribingBtn.addEventListener('click', startTranscription);
    }
});