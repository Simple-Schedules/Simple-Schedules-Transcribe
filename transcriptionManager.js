let transcriptionsData = [];
let selectedTranscription = null;

function translate(key) {
    if (typeof getTranslation === 'function') {
        return getTranslation(key);
    }
    return key;
}

// Format timestamp from HH:MM:SS to clean format (0:10, 10:00, 1:00:00, etc.)
function formatTimestamp(timestamp) {
    const parts = timestamp.split(':');
    const hours = parseInt(parts[0]);
    const minutes = parseInt(parts[1]);
    const seconds = parseInt(parts[2]);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    } else if (minutes >= 10) {
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
}

// Load transcription files from the folder
async function loadTranscriptions() {
    try {
        console.log('Starting to load transcriptions...');
        
        const fileList = await pywebview.api.getTranscriptionFiles();
        console.log('Found files:', fileList);
        
        transcriptionsData = [];
        for (const relativePath of fileList) {
            console.log('Loading file:', relativePath);
            const result = await pywebview.api.getTranscriptionFileContent(relativePath);
            if (!result.success) {
                console.error(`Failed to load ${relativePath}:`, result.message);
                continue;
            }
            const transcriptionData = result.content;
            // Store the relative path with the transcription data for saving later
            transcriptionData._relativePath = relativePath;
            transcriptionsData.push(transcriptionData);
        }
        
        console.log('Loaded transcriptions:', transcriptionsData.length);
        renderTranscriptionList();
    } catch (error) {
        console.error('Error loading transcriptions:', error);
    }
}

// Render the list of transcriptions in the left panel
function renderTranscriptionList() {
    console.log('Rendering transcription list with', transcriptionsData.length, 'items');
    const listContainer = document.getElementById('transcriptionList');
    listContainer.innerHTML = '';

    // Sort by recency (most recent first)
    const sortedTranscriptions = [...transcriptionsData].sort((a, b) => {
        // Compare by date first (YYYY-MM-DD format sorts correctly with localeCompare)
        const dateA = a.date || '0000-00-00';
        const dateB = b.date || '0000-00-00';
        if (dateA !== dateB) {
            return dateB.localeCompare(dateA); // Most recent date first
        }
        // If same date, compare by time (HH:MM format sorts correctly)
        const timeA = a.time || '00:00';
        const timeB = b.time || '00:00';
        return timeB.localeCompare(timeA); // Most recent time first
    });

    sortedTranscriptions.forEach((transcription, originalIndex) => {
        // Find original index for selection
        const index = transcriptionsData.indexOf(transcription);
        console.log('Creating card for:', transcription.title);
        const card = createTranscriptionCard(transcription, index);
        listContainer.appendChild(card);
    });
}

// Create a transcription card element
function createTranscriptionCard(transcription, index) {
    const card = document.createElement('div');
    card.className = 'transcription-card';
    card.setAttribute('data-index', index);
    card.onclick = () => selectTranscription(index);

    if (selectedTranscription === transcription) {
        card.classList.add('active');
    }
    
    const dateTime = transcription.time ? `${transcription.date} ${transcription.time}` : transcription.date;

    const info = document.createElement('div');
    info.innerHTML = `
        <div class="card-title">${transcription.title}</div>
        <div class="card-date">${dateTime}</div>
    `;

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'transcription-delete-btn';
    deleteBtn.title = translate('deleteTranscription');
    deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
    deleteBtn.addEventListener('click', (event) => handleDeleteTranscription(index, event));

    card.appendChild(info);
    card.appendChild(deleteBtn);
    
    return card;
}

async function handleDeleteTranscription(index, event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }

    const transcription = transcriptionsData[index];
    if (!transcription) return;

    const confirmMessage = `${translate('confirmDeleteTranscription')}\n\n"${transcription.title}"`;
    if (!window.confirm(confirmMessage)) {
        return;
    }

    // Release any audio resources pointing to this transcription to avoid file locks
    if (selectedTranscription === transcription) {
        const audioElement = document.getElementById('transcriptionAudio');
        if (audioElement) {
            try {
                audioElement.pause();
                audioElement.removeAttribute('src');
                audioElement.load();
            } catch (audioError) {
                console.warn('Unable to release audio element before deletion:', audioError);
            }
        }
    }

    try {
        if (typeof pywebview === 'undefined' || !pywebview.api || !pywebview.api.deleteTranscription) {
            window.alert(translate('deleteTranscriptionFailed'));
            return;
        }

        const result = await pywebview.api.deleteTranscription(transcription._relativePath);
        if (result && result.success) {
            transcriptionsData.splice(index, 1);
            if (selectedTranscription === transcription) {
                selectedTranscription = null;
            }
            renderTranscriptionList();
            renderTranscriptionContent();
            console.log(translate('transcriptionDeleted'));
        } else {
            window.alert(`${translate('deleteTranscriptionFailed')}: ${(result && result.message) || ''}`);
        }
    } catch (error) {
        console.error('Error deleting transcription:', error);
        window.alert(`${translate('deleteTranscriptionFailed')}: ${error}`);
    }
}

// Select and display a transcription
function selectTranscription(index) {
    selectedTranscription = transcriptionsData[index];
    
    // Selected card styling - match by data-index attribute
    document.querySelectorAll('.transcription-card').forEach((card) => {
        const cardIndex = parseInt(card.getAttribute('data-index'));
        card.classList.toggle('active', cardIndex === index);
    });
    
    renderTranscriptionContent();
}

// Show the selected transcription file in the right panel
function renderTranscriptionContent() {
    const contentContainer = document.getElementById('transcriptionContent');
    
    if (!selectedTranscription) {
        contentContainer.innerHTML = `
            <div class="empty-state">
                <h2 data-i18n="selectOrCreate">Välj eller skapa en transkribering</h2>
                <p data-i18n="selectOrCreateDesc">Välj eller skapa en transkribering i den vänstra panelen</p>
            </div>
        `;
        // Apply translations to the empty state
        if (typeof applyLanguage === 'function') {
            const settings = typeof Settings !== 'undefined' ? Settings.get() : { language: 'sv' };
            applyLanguage(settings.language);
        }
        // Remove audio player if it exists
        const existingPlayer = document.querySelector('.audio-player-container');
        if (existingPlayer) {
            existingPlayer.remove();
        }
        return;
    }
    
    const speakersHtml = selectedTranscription.speakers
        .map((speaker, index) => `<span class="speaker-tag editable-speaker" onclick="editSpeaker(this, ${index})">${speaker}</span>`)
        .join('');
    
    const transcriptionEntriesHtml = selectedTranscription.transcribedText
        .map((entry, index) => `
            <div class="transcription-entry">
                <div class="entry-timestamp">${formatTimestamp(entry.timestamp)}</div>
                <div class="entry-content">
                    <div class="entry-speaker">${selectedTranscription.speakers[entry.speakerIndex]}</div>
                    <div class="entry-text editable-text" onclick="editText(this, ${index})">${entry.text}</div>
                </div>
            </div>
        `).join('');
    
    const dateTime = selectedTranscription.time ? `${selectedTranscription.date} ${selectedTranscription.time}` : selectedTranscription.date;
    contentContainer.innerHTML = `
        <div class="content-header">
            <div class="title-with-button">
                <h1 class="content-title editable-title" onclick="editTitle(this)">${selectedTranscription.title}</h1>
                <button class="open-notepad-btn" onclick="openInNotepad()" title="${getTranslation('openInNotepad')}">
                    <i class="fa-solid fa-file-lines"></i>
                </button>
            </div>
            <span class="content-date">${dateTime}</span>
        </div>
        
        <div class="speakers-container">
            <div class="speakers-list">
                ${speakersHtml}
            </div>
        </div>
        
        <div class="transcription-content">
            ${transcriptionEntriesHtml}
        </div>
        
        <div class="audio-player-container">
            <audio id="transcriptionAudio" preload="metadata"></audio>
            <div class="audio-player">
                <button class="audio-skip-btn" id="audioSkipBackBtn" title="${getTranslation('skipBack')}">
                    <i class="fa-solid fa-backward"></i>
                </button>
                <button class="audio-play-pause-btn" id="audioPlayPauseBtn">
                    <i class="fa-solid fa-play"></i>
                </button>
                <button class="audio-skip-btn" id="audioSkipForwardBtn" title="${getTranslation('skipForward')}">
                    <i class="fa-solid fa-forward"></i>
                </button>
                <button class="audio-autoscroll-btn" id="audioAutoscrollBtn" title="${getTranslation('toggleAutoscroll')}">
                    <i class="fa-solid fa-arrows-up-down"></i>
                </button>
                <input type="range" class="audio-seekbar" id="audioSeekbar" min="0" max="0" value="0" step="0.1">
                <div class="audio-timestamps" id="audioTimestamps">
                    <span class="current-time">0:00</span>
                    <span class="time-separator"> / </span>
                    <span class="total-time">0:00</span>
                </div>
            </div>
        </div>
    `;
    
    // Initialize audio player after rendering (always, even without audio file for testing)
    initializeAudioPlayer(selectedTranscription);
    
    // Update dynamic translations (tooltips)
    if (typeof updateDynamicTranslations === 'function') {
        updateDynamicTranslations();
    }
}

// Open transcription in Notepad
async function openInNotepad() {
    if (!selectedTranscription) return;
    
    try {
        // Create a copy without the _relativePath property
        const transcriptionToOpen = { ...selectedTranscription };
        delete transcriptionToOpen._relativePath;
        
        const result = await pywebview.api.openTranscriptionAsText(transcriptionToOpen);
        if (!result.success) {
            console.error('Failed to open in Notepad:', result.message);
            alert(getTranslation('failedToOpenNotepad') + ': ' + result.message);
        }
    } catch (error) {
        console.error('Error opening in Notepad:', error);
        alert(getTranslation('errorOpeningNotepad') + ': ' + error);
    }
}

// Edit title functionality
function editTitle(titleElement) {
    const currentTitle = titleElement.textContent;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentTitle;
    input.className = 'title-editor';
    input.style.cssText = 'font-size: 24px; font-weight: 600; border: 2px solid #007bff; padding: 4px; border-radius: 4px; background: white;';
    
    titleElement.replaceWith(input);
    input.focus();
    input.select();
    
    function saveTitle() {
        const newTitle = input.value.trim();
        if (newTitle && newTitle !== currentTitle) {
            // Update the selected transcription
            selectedTranscription.title = newTitle;
            
            // Update the card in the left panel
            const activeCard = document.querySelector('.transcription-card.active .card-title');
            if (activeCard) {
                activeCard.textContent = newTitle;
            }
            
            // Save to JSON file
            saveTranscriptionToFile();
        }
        
        // Replace input with updated title
        const newTitleElement = document.createElement('h1');
        newTitleElement.className = 'content-title editable-title';
        newTitleElement.onclick = () => editTitle(newTitleElement);
        newTitleElement.textContent = selectedTranscription.title;
        input.replaceWith(newTitleElement);
    }
    
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            saveTitle();
        } else if (e.key === 'Escape') {
            // Cancel editing
            const titleElement = document.createElement('h1');
            titleElement.className = 'content-title editable-title';
            titleElement.onclick = () => editTitle(titleElement);
            titleElement.textContent = currentTitle;
            input.replaceWith(titleElement);
        }
    });
    
    input.addEventListener('blur', saveTitle);
}

// Edit text functionality
function editText(textElement, entryIndex) {
    const currentText = textElement.textContent;
    const textarea = document.createElement('textarea');
    textarea.value = currentText;
    textarea.className = 'text-editor';
    
    textElement.replaceWith(textarea);

    // Function to auto-resize the textarea
    function autoResize() {
        textarea.style.height = 'auto';
        textarea.style.height = `${textarea.scrollHeight}px`;
    }

    // Auto-resize on input
    textarea.addEventListener('input', autoResize);
    
    // Set initial size and focus
    textarea.focus();
    textarea.select();
    autoResize(); // Set initial height correctly
    
    function saveText() {
        const newText = textarea.value.trim();
        if (newText !== currentText) {
            // Update the text in the selected transcription (allow empty text)
            selectedTranscription.transcribedText[entryIndex].text = newText;
            
            // Save to JSON file
            saveTranscriptionToFile();
        }
        
        // Replace textarea with updated text element
        const newTextElement = document.createElement('div');
        newTextElement.className = 'entry-text editable-text';
        newTextElement.onclick = () => editText(newTextElement, entryIndex);
        newTextElement.textContent = selectedTranscription.transcribedText[entryIndex].text;
        textarea.replaceWith(newTextElement);
    }
    
    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveText();
        } else if (e.key === 'Escape') {
            // Cancel editing
            e.preventDefault();
            const textElement = document.createElement('div');
            textElement.className = 'entry-text editable-text';
            textElement.onclick = () => editText(textElement, entryIndex);
            textElement.textContent = currentText;
            textarea.replaceWith(textElement);
        }
    });
    
    textarea.addEventListener('blur', saveText);
}

// Edit speaker functionality
function editSpeaker(speakerElement, speakerIndex) {
    const currentName = speakerElement.textContent;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentName;
    input.className = 'speaker-editor';
    input.style.cssText = 'font-size: 14px; font-weight: 500; border: 2px solid #007bff; padding: 4px 8px; border-radius: 20px; background: white;';
    
    speakerElement.replaceWith(input);
    input.focus();
    input.select();
    
    function saveSpeaker() {
        const newName = input.value.trim();
        if (newName && newName !== currentName) {
            // Update the speaker in the selected transcription
            selectedTranscription.speakers[speakerIndex] = newName;
            
            // Re-render the transcription content to update all speaker references
            renderTranscriptionContent();
            
            // Save to JSON file
            saveTranscriptionToFile();
        } else {
            // Replace input with original speaker element
            const newSpeakerElement = document.createElement('span');
            newSpeakerElement.className = 'speaker-tag editable-speaker';
            newSpeakerElement.onclick = () => editSpeaker(newSpeakerElement, speakerIndex);
            newSpeakerElement.textContent = currentName;
            input.replaceWith(newSpeakerElement);
        }
    }
    
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            saveSpeaker();
        } else if (e.key === 'Escape') {
            // Cancel editing
            const speakerElement = document.createElement('span');
            speakerElement.className = 'speaker-tag editable-speaker';
            speakerElement.onclick = () => editSpeaker(speakerElement, speakerIndex);
            speakerElement.textContent = currentName;
            input.replaceWith(speakerElement);
        }
    });
    
    input.addEventListener('blur', saveSpeaker);
}

// Save transcription to JSON file
async function saveTranscriptionToFile() {
    if (!selectedTranscription) return;
    
    try {
        // Find the relative path for the current transcription
        const relativePath = getCurrentTranscriptionRelativePath();
        if (!relativePath) {
            console.error('Could not determine relative path for current transcription');
            return;
        }
        
        // Create a copy without the _relativePath property for saving
        const transcriptionToSave = { ...selectedTranscription };
        delete transcriptionToSave._relativePath;
        
        const result = await pywebview.api.saveTranscription(relativePath, transcriptionToSave);
        if (result.success) {
            console.log('Transcription saved successfully');
        } else {
            console.error('Failed to save transcription:', result.message);
        }
    } catch (error) {
        console.error('Error saving transcription:', error);
    }
}

// Get relative path for current transcription (use stored relative path)
function getCurrentTranscriptionRelativePath() {
    if (!selectedTranscription) return null;
    
    // Use the relative path that was stored when loading
    return selectedTranscription._relativePath || null;
}

// Auto-scroll state
let autoScrollEnabled = false;
let lastScrolledIndex = -1;
let scrollThrottle = null;
let scrollAnimationFrame = null;

// Initialize audio player functionality
async function initializeAudioPlayer(transcription) {
    const audio = document.getElementById('transcriptionAudio');
    const playPauseBtn = document.getElementById('audioPlayPauseBtn');
    const skipBackBtn = document.getElementById('audioSkipBackBtn');
    const skipForwardBtn = document.getElementById('audioSkipForwardBtn');
    const autoscrollBtn = document.getElementById('audioAutoscrollBtn');
    const seekbar = document.getElementById('audioSeekbar');
    const currentTimeSpan = document.querySelector('.current-time');
    const totalTimeSpan = document.querySelector('.total-time');
    
    if (!audio || !playPauseBtn || !seekbar) return;
    
    // Reset auto-scroll state
    autoScrollEnabled = false;
    lastScrolledIndex = -1;
    if (scrollThrottle !== null) {
        clearTimeout(scrollThrottle);
        scrollThrottle = null;
    }
    if (scrollAnimationFrame !== null) {
        cancelAnimationFrame(scrollAnimationFrame);
        scrollAnimationFrame = null;
    }
    
    // Auto-scroll toggle button
    if (autoscrollBtn) {
        autoscrollBtn.addEventListener('click', () => {
            autoScrollEnabled = !autoScrollEnabled;
            autoscrollBtn.classList.toggle('active', autoScrollEnabled);
            if (autoScrollEnabled) {
                lastScrolledIndex = -1; // Reset to allow immediate scroll
                if (!audio.paused && audio.currentTime > 0) {
                    scrollToCurrentTimestamp(audio.currentTime);
                }
            }
        });
    }
    
    // Set audio source if available
    if (transcription && transcription.audioPath && transcription._relativePath) {
        try {
            const audioPath = await pywebview.api.getAudioFilePath(
                transcription._relativePath,
                transcription.audioPath
            );
            // Use file:// protocol for local file access
            audio.src = `file:///${audioPath.replace(/\\/g, '/')}`;
        } catch (error) {
            console.error('Error loading audio file:', error);
        }
    }
    
    // Update total time when metadata is loaded
    audio.addEventListener('loadedmetadata', () => {
        if (audio.duration && !isNaN(audio.duration) && isFinite(audio.duration)) {
            if (totalTimeSpan) {
                totalTimeSpan.textContent = formatAudioTime(audio.duration);
            }
            if (seekbar) {
                seekbar.max = audio.duration;
            }
        }
    });
    
    // Update current time while playing
    audio.addEventListener('timeupdate', () => {
        const currentTime = audio.currentTime || 0;
        if (currentTimeSpan) {
            currentTimeSpan.textContent = formatAudioTime(currentTime);
        }
        if (seekbar && audio.duration) {
            seekbar.value = currentTime;
        }
        // Auto-scroll if enabled and playing (throttled for smooth scrolling)
        // Don't scroll if an animation is already running (manual scroll in progress)
        if (autoScrollEnabled && !audio.paused && scrollThrottle === null && scrollAnimationFrame === null) {
            scrollThrottle = setTimeout(() => {
                scrollToCurrentTimestamp(currentTime);
                scrollThrottle = null;
            }, 300);
        }
    });
    
    // Update button icon when playback state changes
    audio.addEventListener('play', () => {
        if (playPauseBtn) {
            playPauseBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
        }
        // Start scrolling if auto-scroll is enabled
        if (autoScrollEnabled) {
            lastScrolledIndex = -1; // Reset to allow immediate scroll
            scrollToCurrentTimestamp(audio.currentTime);
        }
    });
    
    audio.addEventListener('pause', () => {
        if (playPauseBtn) {
            playPauseBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
        }
    });
    
    // Play/pause button click handler
    playPauseBtn.addEventListener('click', () => {
        toggleAudioPlayPause(audio);
    });
    
    // Skip backward button (10 seconds)
    if (skipBackBtn) {
        skipBackBtn.addEventListener('click', () => {
            if (audio.src && audio.src !== window.location.href) {
                // Cancel any pending scroll from timeupdate
                if (scrollThrottle !== null) {
                    clearTimeout(scrollThrottle);
                    scrollThrottle = null;
                }
                audio.currentTime = Math.max(0, audio.currentTime - 10);
                if (autoScrollEnabled) {
                    lastScrolledIndex = -1;
                    scrollToCurrentTimestamp(audio.currentTime);
                }
            }
        });
    }
    
    // Skip forward button (10 seconds)
    if (skipForwardBtn) {
        skipForwardBtn.addEventListener('click', () => {
            if (audio.src && audio.src !== window.location.href) {
                // Cancel any pending scroll from timeupdate
                if (scrollThrottle !== null) {
                    clearTimeout(scrollThrottle);
                    scrollThrottle = null;
                }
                audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 10);
                if (autoScrollEnabled) {
                    lastScrolledIndex = -1;
                    scrollToCurrentTimestamp(audio.currentTime);
                }
            }
        });
    }
    
    // Helper function to toggle audio play/pause
    window.toggleAudioPlayPause = function() {
        const audioElement = document.getElementById('transcriptionAudio');
        if (audioElement) {
            toggleAudioPlayPause(audioElement);
        }
    };
    
    function toggleAudioPlayPause(audioElement) {
        if (audioElement.src && audioElement.src !== window.location.href) {
            if (audioElement.paused) {
                audioElement.play();
            } else {
                audioElement.pause();
            }
        }
    }
    
    // Seekbar change handler
    seekbar.addEventListener('input', () => {
        const seekTime = parseFloat(seekbar.value);
        // Cancel any pending scroll from timeupdate
        if (scrollThrottle !== null) {
            clearTimeout(scrollThrottle);
            scrollThrottle = null;
        }
        if (audio.src && audio.src !== window.location.href && audio.duration) {
            audio.currentTime = seekTime;
        }
        // Update scroll position if auto-scroll is enabled
        if (autoScrollEnabled) {
            lastScrolledIndex = -1;
            scrollToCurrentTimestamp(seekTime);
        }
    });
}

// Format time in seconds to MM:SS or H:MM:SS format
function formatAudioTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return '0:00';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}

// Convert timestamp string (HH:MM:SS) to seconds
function timestampToSeconds(timestamp) {
    const parts = timestamp.split(':').map(Number);
    if (parts.length !== 3) return 0;
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
}

// Find the transcription entry index for a given timestamp
function findEntryIndexForTimestamp(timestampSeconds) {
    if (!selectedTranscription || !selectedTranscription.transcribedText) {
        return -1;
    }
    
    let bestIndex = -1;
    let bestTime = -1;
    
    for (let i = 0; i < selectedTranscription.transcribedText.length; i++) {
        const entry = selectedTranscription.transcribedText[i];
        const entryTime = timestampToSeconds(entry.timestamp);
        
        // Find the entry where the timestamp is <= current time
        // This finds the most recent entry that has started
        if (entryTime <= timestampSeconds && entryTime > bestTime) {
            bestTime = entryTime;
            bestIndex = i;
        }
    }
    
    // If no match found, return first entry (for very early timestamps)
    if (bestIndex < 0) {
        return 0;
    }
    
    return bestIndex;
}

// Scroll to the transcription entry matching the current audio timestamp
function scrollToCurrentTimestamp(currentTimeSeconds) {
    const scrollableContainer = document.querySelector('.right-panel-content');
    const transcriptionContent = document.querySelector('.transcription-content');
    if (!scrollableContainer || !transcriptionContent || !selectedTranscription) return;
    
    const entryIndex = findEntryIndexForTimestamp(currentTimeSeconds);
    if (entryIndex < 0 || entryIndex === lastScrolledIndex) return;
    
    const entries = transcriptionContent.querySelectorAll('.transcription-entry');
    if (entryIndex >= entries.length) return;
    
    const targetEntry = entries[entryIndex];
    if (!targetEntry) return;
    
    // Calculate scroll position with padding offset
    const containerTop = scrollableContainer.getBoundingClientRect().top;
    const entryTop = targetEntry.getBoundingClientRect().top;
    const targetScroll = entryTop - containerTop + scrollableContainer.scrollTop - 24;
    
    // Only scroll if there's a meaningful difference
    if (Math.abs(targetScroll - scrollableContainer.scrollTop) > 50) {
        // Cancel any ongoing scroll animation
        if (scrollAnimationFrame !== null) {
            cancelAnimationFrame(scrollAnimationFrame);
        }
        
        // Smooth scroll animation
        const startScroll = scrollableContainer.scrollTop;
        const distance = targetScroll - startScroll;
        const duration = 400;
        const startTime = performance.now();
        
        function animate(currentTime) {
            const progress = Math.min((currentTime - startTime) / duration, 1);
            const easeOut = 1 - Math.pow(1 - progress, 3);
            scrollableContainer.scrollTop = startScroll + distance * easeOut;
            if (progress < 1) {
                scrollAnimationFrame = requestAnimationFrame(animate);
            } else {
                scrollAnimationFrame = null;
            }
        }
        
        scrollAnimationFrame = requestAnimationFrame(animate);
    }
    
    lastScrolledIndex = entryIndex;
}

// Update dynamic translations (tooltips, etc.)
function updateDynamicTranslations() {
    // Update audio player tooltips
    const skipBackBtn = document.getElementById('audioSkipBackBtn');
    const skipForwardBtn = document.getElementById('audioSkipForwardBtn');
    const autoscrollBtn = document.getElementById('audioAutoscrollBtn');
    const openNotepadBtn = document.querySelector('.open-notepad-btn');
    
    if (skipBackBtn) skipBackBtn.title = getTranslation('skipBack');
    if (skipForwardBtn) skipForwardBtn.title = getTranslation('skipForward');
    if (autoscrollBtn) autoscrollBtn.title = getTranslation('toggleAutoscroll');
    if (openNotepadBtn) openNotepadBtn.title = getTranslation('openInNotepad');
}

// Initialize the app when PyWebview is ready
document.addEventListener('DOMContentLoaded', function() {
    const newTranscriptionBtn = document.getElementById('newTranscriptionBtn');
    if (newTranscriptionBtn) {
        newTranscriptionBtn.addEventListener('click', () => {
            window.location.href = 'newTranscription.html';
        });
    }

    // Settings modal functionality
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

    // Wait for PyWebview to be ready before loading transcriptions
    if (typeof pywebview !== 'undefined' && pywebview.api) {
        loadTranscriptions();
    } else {
        // If pywebview isn't ready yet, wait for it
        window.addEventListener('pywebviewready', function() {
            console.log('PyWebview ready event fired');
            loadTranscriptions();
        });
    }
    
    // Spacebar to toggle play/pause when in right panel
    document.addEventListener('keydown', (e) => {
        // Only handle spacebar
        if (e.code !== 'Space' && e.key !== ' ') return;
        
        // Don't interfere with text input fields
        const activeElement = document.activeElement;
        if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
            return;
        }
        
        // Check if right panel is visible and has content
        const rightPanel = document.querySelector('.right-panel');
        const transcriptionContent = document.querySelector('.transcription-content');
        if (!rightPanel || !transcriptionContent) return;
        
        // Prevent default scrolling behavior
        e.preventDefault();
        
        // Toggle play/pause
        if (window.toggleAudioPlayPause) {
            window.toggleAudioPlayPause();
        }
    });
});
