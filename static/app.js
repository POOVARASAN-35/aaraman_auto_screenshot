// Application State
const state = {
    activeTaskId: null,
    activeRunId: null,
    pollIntervalId: null,
    history: [],
    screenshots: [],
    lightboxIndex: -1,
    previewImgElement: null
};

// DOM Elements
const elements = {
    sidebar: document.querySelector('.sidebar'),
    historyList: document.getElementById('history-list'),
    configSection: document.getElementById('config-section'),
    extractionForm: document.getElementById('extraction-form'),
    videoUrl: document.getElementById('video-url'),
    presenterName: document.getElementById('presenter-name'),
    presentationDate: document.getElementById('presentation-date'),
    
    // Settings toggles & sliders
    toggleSettings: document.getElementById('toggle-settings'),
    advancedSettingsPanel: document.getElementById('advanced-settings-panel'),
    threshold: document.getElementById('threshold'),
    thresholdVal: document.getElementById('threshold-val'),
    sampleInterval: document.getElementById('sample-interval'),
    sampleIntervalVal: document.getElementById('sample-interval-val'),
    cooldown: document.getElementById('cooldown'),
    cooldownVal: document.getElementById('cooldown-val'),
    cropMode: document.getElementById('crop-mode'),
    
    // Manual crop
    manualCropSettings: document.getElementById('manual-crop-settings'),
    cropTop: document.getElementById('crop-top'),
    cropTopVal: document.getElementById('crop-top-val'),
    cropBottom: document.getElementById('crop-bottom'),
    cropBottomVal: document.getElementById('crop-bottom-val'),
    cropLeft: document.getElementById('crop-left'),
    cropLeftVal: document.getElementById('crop-left-val'),
    cropRight: document.getElementById('crop-right'),
    cropRightVal: document.getElementById('crop-right-val'),
    btnLoadPreview: document.getElementById('btn-load-preview'),
    cropCanvas: document.getElementById('crop-canvas'),
    cropOverlay: document.getElementById('crop-overlay'),
    canvasContainer: document.querySelector('.preview-canvas-container'),
    
    // Active task console
    taskSection: document.getElementById('task-section'),
    btnCancel: document.getElementById('btn-cancel'),
    taskStatusText: document.getElementById('task-status-text'),
    taskSavedCount: document.getElementById('task-saved-count'),
    taskDuration: document.getElementById('task-duration'),
    taskElapsed: document.getElementById('task-elapsed'),
    progressFill: document.getElementById('progress-fill'),
    progressPercent: document.getElementById('progress-percent'),
    progressDetail: document.getElementById('progress-detail'),
    consoleLog: document.getElementById('console-log'),
    btnClearLogs: document.getElementById('btn-clear-logs'),
    
    // Results
    resultsSection: document.getElementById('results-section'),
    galleryTitle: document.getElementById('gallery-title'),
    gallerySubtitle: document.getElementById('gallery-subtitle'),
    btnDownloadZip: document.getElementById('btn-download-zip'),
    btnBackToForm: document.getElementById('btn-back-to-form'),
    galleryGrid: document.getElementById('gallery-grid'),
    galleryEmpty: document.getElementById('gallery-empty'),
    
    // Lightbox
    lightbox: document.getElementById('lightbox'),
    lightboxClose: document.getElementById('lightbox-close'),
    lightboxImg: document.getElementById('lightbox-img'),
    lightboxCaption: document.getElementById('lightbox-caption'),
    lightboxPrev: document.getElementById('lightbox-prev'),
    lightboxNext: document.getElementById('lightbox-next')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initDefaultDate();
    initSettingsSliders();
    initSettingsAccordion();
    initCropMode();
    initAutoPrefill();
    initFormSubmit();
    initConsoleClear();
    initLightbox();
    initHistoryControls();
    
    // Initial history fetch
    fetchHistory();
});

// 1. Setup Defaults & Simple Sliders UI
function initDefaultDate() {
    const today = new Date();
    const dd = String(today.getDate()).padStart(2, '0');
    const mm = String(today.getMonth() + 1).padStart(2, '0'); // January is 0
    const yyyy = today.getFullYear();
    elements.presentationDate.value = `${dd}-${mm}-${yyyy}`;
}

function initSettingsSliders() {
    // Difference Threshold Slider
    elements.threshold.addEventListener('input', (e) => {
        elements.thresholdVal.textContent = parseFloat(e.target.value).toFixed(1);
    });
    
    // Sample Interval Slider
    elements.sampleInterval.addEventListener('input', (e) => {
        elements.sampleIntervalVal.textContent = parseFloat(e.target.value).toFixed(1) + 's';
    });
    
    // Cooldown Slider
    elements.cooldown.addEventListener('input', (e) => {
        elements.cooldownVal.textContent = e.target.value + 's';
    });

    // Manual Crop Sliders
    const cropInputs = [elements.cropTop, elements.cropBottom, elements.cropLeft, elements.cropRight];
    const cropVals = [elements.cropTopVal, elements.cropBottomVal, elements.cropLeftVal, elements.cropRightVal];
    
    cropInputs.forEach((input, idx) => {
        input.addEventListener('input', (e) => {
            cropVals[idx].textContent = e.target.value + '%';
            updateCropOverlay();
        });
    });
}

function initSettingsAccordion() {
    elements.toggleSettings.addEventListener('click', () => {
        elements.advancedSettingsPanel.classList.toggle('open');
        const arrow = elements.toggleSettings.querySelector('.arrow');
        if (elements.advancedSettingsPanel.classList.contains('open')) {
            arrow.innerHTML = '&#9652;'; // up arrow
        } else {
            arrow.innerHTML = '&#9662;'; // down arrow
        }
    });
}

// 2. Crop Configuration Control
function initCropMode() {
    elements.cropMode.addEventListener('change', () => {
        if (elements.cropMode.value === 'manual') {
            elements.manualCropSettings.classList.remove('hidden');
        } else {
            elements.manualCropSettings.classList.add('hidden');
        }
    });
    
    elements.btnLoadPreview.addEventListener('click', generateCropPreviewFrame);
}

function updateCropOverlay() {
    if (!state.previewImgElement) return;
    
    const top = parseFloat(elements.cropTop.value);
    const bottom = parseFloat(elements.cropBottom.value);
    const left = parseFloat(elements.cropLeft.value);
    const right = parseFloat(elements.cropRight.value);
    
    elements.cropOverlay.style.top = top + '%';
    elements.cropOverlay.style.bottom = bottom + '%';
    elements.cropOverlay.style.left = left + '%';
    elements.cropOverlay.style.right = right + '%';
}

async function generateCropPreviewFrame() {
    const videoUrl = elements.videoUrl.value.trim();
    if (!videoUrl) {
        alert('Please enter a Google Drive Link or Video Path first.');
        elements.videoUrl.focus();
        return;
    }
    
    elements.btnLoadPreview.disabled = true;
    elements.btnLoadPreview.textContent = 'Loading Frame...';
    
    try {
        const response = await fetch('/api/preview/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_path: videoUrl })
        });
        
        const data = await response.json();
        
        if (response.ok && data.preview_url) {
            // Load image
            const img = new Image();
            img.src = data.preview_url + '?t=' + Date.now(); // cache breaker
            img.onload = () => {
                state.previewImgElement = img;
                const canvas = elements.cropCanvas;
                const ctx = canvas.getContext('2d');
                
                // Set canvas size to match image aspect ratio
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                ctx.drawImage(img, 0, 0);
                
                elements.canvasContainer.classList.add('active');
                updateCropOverlay();
                
                elements.btnLoadPreview.textContent = 'Reload Frame';
                elements.btnLoadPreview.disabled = false;
            };
            img.onerror = () => {
                alert('Failed to load the generated frame image.');
                elements.btnLoadPreview.textContent = 'Load Reference Frame';
                elements.btnLoadPreview.disabled = false;
            };
        } else {
            alert('Failed to generate preview frame. Reason: ' + (data.detail || 'Unknown error'));
            elements.btnLoadPreview.textContent = 'Load Reference Frame';
            elements.btnLoadPreview.disabled = false;
        }
    } catch (err) {
        console.error(err);
        alert('Server error occurred while generating crop preview.');
        elements.btnLoadPreview.textContent = 'Load Reference Frame';
        elements.btnLoadPreview.disabled = false;
    }
}

// 3. Smart Auto-Prefilling inputs when typing URL
function initAutoPrefill() {
    elements.videoUrl.addEventListener('change', () => {
        const urlValue = elements.videoUrl.value.trim();
        if (!urlValue) return;
        
        // Match dates in filename like 04.06.26 or 04-06-2026 or 2026_06_04
        const datePattern = /(\d{2})[._\-](\d{2})[._\-](\d{2,4})/;
        const match = urlValue.match(datePattern);
        
        if (match) {
            let dd = match[1];
            let mm = match[2];
            let yy = match[3];
            
            // Format year to 4 digits if 2 digits
            if (yy.length === 2) {
                yy = '20' + yy;
            }
            
            elements.presentationDate.value = `${dd}-${mm}-${yy}`;
        }
        
        // Try to guess a presenter name if filename contains one
        // e.g. path like /Output/SARAVANAKUMAR_31-05-2026/ or file name containing letters
        const parts = urlValue.split(/[\\/]/);
        const filename = parts[parts.length - 1];
        
        // Remove file extension and numbers/dates to see if there's a clean name
        let nameGuess = filename.replace(/\.[a-zA-Z0-9]+$/, '') // extension
                                .replace(/\d+/g, '')            // numbers
                                .replace(/[._\-]/g, ' ')        // separators
                                .trim();
                                
        if (nameGuess.length > 2 && nameGuess.length < 20) {
            // Title case the name
            nameGuess = nameGuess.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
            elements.presenterName.value = nameGuess.toUpperCase();
        } else {
            // Default placeholder if we couldn't parse
            if (!elements.presenterName.value) {
                elements.presenterName.value = 'PRESENTER';
            }
        }
    });
}

// 4. Form Submission and Task Flow
function initFormSubmit() {
    elements.extractionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const payload = {
            video_path: elements.videoUrl.value.trim(),
            presenter_name: elements.presenterName.value.trim(),
            presentation_date: elements.presentationDate.value.trim(),
            threshold: parseFloat(elements.threshold.value),
            sample_interval: parseFloat(elements.sampleInterval.value),
            cooldown: parseFloat(elements.cooldown.value),
            crop_mode: elements.cropMode.value,
            crop_left: parseFloat(elements.cropLeft.value),
            crop_right: parseFloat(elements.cropRight.value),
            crop_top: parseFloat(elements.cropTop.value),
            crop_bottom: parseFloat(elements.cropBottom.value)
        };
        
        // Reset Status Details
        elements.taskStatusText.textContent = 'Initializing...';
        elements.taskStatusText.style.color = 'var(--primary)';
        elements.taskSavedCount.textContent = '0';
        elements.taskDuration.textContent = '00:00:00';
        elements.taskElapsed.textContent = '0s';
        elements.progressFill.style.width = '0%';
        elements.progressPercent.textContent = '0%';
        elements.progressDetail.textContent = 'Connecting to background worker...';
        elements.consoleLog.textContent = 'Process started...\n';
        state.screenshots = [];
        renderScreenshots();
        
        // Transition Views
        elements.configSection.classList.add('hidden');
        elements.taskSection.classList.remove('hidden');
        elements.resultsSection.classList.remove('hidden');
        
        elements.galleryTitle.textContent = `Extracted Screenshots for ${payload.presenter_name}`;
        elements.gallerySubtitle.textContent = `Folder: Output/${payload.presenter_name.replace(/[^a-zA-Z0-9]/g, '_')}_${payload.presentation_date.replace(/[^a-zA-Z0-9]/g, '_')}`;
        elements.btnDownloadZip.classList.add('hidden'); // Hide download zip until complete
        
        try {
            const response = await fetch('/api/extract/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            
            if (response.ok && data.task_id) {
                state.activeTaskId = data.task_id;
                state.activeRunId = data.run_id;
                
                // Start Polling status
                state.pollIntervalId = setInterval(pollTaskStatus, 1000);
            } else {
                appendLog('Error starting extraction task: ' + (data.detail || 'Unknown server error'));
                elements.taskStatusText.textContent = 'Failed to Start';
                elements.taskStatusText.style.color = 'var(--danger)';
                elements.progressDetail.textContent = 'Job initialization failed.';
            }
        } catch (err) {
            console.error(err);
            appendLog('Network error connecting to the extraction server.');
            elements.taskStatusText.textContent = 'Connection Error';
            elements.taskStatusText.style.color = 'var(--danger)';
        }
    });
    
    // Cancel Task Click
    elements.btnCancel.addEventListener('click', cancelActiveTask);
    
    // Back to form
    elements.btnBackToForm.addEventListener('click', () => {
        elements.resultsSection.classList.add('hidden');
        elements.taskSection.classList.add('hidden');
        elements.configSection.classList.remove('hidden');
        elements.extractionForm.reset();
        initDefaultDate();
        if (state.pollIntervalId) {
            clearInterval(state.pollIntervalId);
            state.pollIntervalId = null;
        }
        state.activeTaskId = null;
        state.activeRunId = null;
        state.previewImgElement = null;
        elements.canvasContainer.classList.remove('active');
        elements.btnLoadPreview.textContent = 'Load Reference Frame';
        elements.btnLoadPreview.disabled = false;
    });
}

function initConsoleClear() {
    elements.btnClearLogs.addEventListener('click', () => {
        elements.consoleLog.textContent = '';
    });
}

function appendLog(message) {
    if (!message) return;
    elements.consoleLog.textContent += message + '\n';
    elements.consoleLog.scrollTop = elements.consoleLog.scrollHeight;
}

// 5. Polling Task Status
async function pollTaskStatus() {
    if (!state.activeTaskId) return;
    
    try {
        const response = await fetch(`/api/extract/status/${state.activeTaskId}`);
        const data = await response.json();
        
        if (!response.ok) {
            appendLog('Warning: Failed to fetch task status updates.');
            return;
        }
        
        // Update stats
        elements.taskStatusText.textContent = data.status.toUpperCase();
        elements.taskSavedCount.textContent = data.screenshots_saved;
        elements.taskDuration.textContent = data.video_duration || '00:00:00';
        elements.taskElapsed.textContent = Math.round(data.elapsed_time) + 's';
        
        // Color match status
        if (data.status === 'downloading') {
            elements.taskStatusText.style.color = 'var(--warning)';
        } else if (data.status === 'analyzing') {
            elements.taskStatusText.style.color = 'var(--primary)';
        } else if (data.status === 'completed') {
            elements.taskStatusText.style.color = 'var(--success)';
        } else if (data.status === 'failed' || data.status === 'cancelled') {
            elements.taskStatusText.style.color = 'var(--danger)';
        }
        
        // Progress bar
        const progress = Math.round(data.progress || 0);
        elements.progressFill.style.width = progress + '%';
        elements.progressPercent.textContent = progress + '%';
        elements.progressDetail.textContent = data.progress_detail || '';
        
        // Append new logs
        if (data.logs && data.logs.length > 0) {
            // Find logs that aren't already displayed
            const currentLogText = elements.consoleLog.textContent;
            data.logs.forEach(logLine => {
                if (!currentLogText.includes(logLine)) {
                    appendLog(logLine);
                }
            });
        }
        
        // Update live screenshots gallery
        if (data.screenshots && data.screenshots.length > state.screenshots.length) {
            state.screenshots = data.screenshots.map(filename => ({
                name: filename,
                url: `/output/${state.activeRunId}/${filename}`,
                time: parseTimestamp(filename)
            }));
            renderScreenshots();
        }
        
        // Complete states check
        if (data.status === 'completed') {
            clearInterval(state.pollIntervalId);
            state.pollIntervalId = null;
            appendLog('\nTask completed successfully!');
            
            // Enable download zip
            elements.btnDownloadZip.href = `/api/history/${state.activeRunId}/download-zip`;
            elements.btnDownloadZip.classList.remove('hidden');
            
            fetchHistory(); // refresh sidebar runs
        } else if (data.status === 'failed') {
            clearInterval(state.pollIntervalId);
            state.pollIntervalId = null;
            appendLog('\nTask failed: ' + (data.error || 'Check logs above.'));
            
            fetchHistory(); // refresh sidebar runs
        } else if (data.status === 'cancelled') {
            clearInterval(state.pollIntervalId);
            state.pollIntervalId = null;
            appendLog('\nTask cancelled by user.');
            
            fetchHistory(); // refresh sidebar runs
        }
        
    } catch (err) {
        console.error(err);
        appendLog('Error polling status update from server.');
    }
}

async function cancelActiveTask() {
    if (!state.activeTaskId) return;
    
    if (!confirm('Are you sure you want to stop the screenshot extraction?')) return;
    
    elements.btnCancel.disabled = true;
    elements.btnCancel.textContent = 'Cancelling...';
    
    try {
        const response = await fetch(`/api/extract/cancel/${state.activeTaskId}`, { method: 'POST' });
        if (response.ok) {
            appendLog('Sending cancellation request...');
        } else {
            alert('Failed to send cancel command.');
            elements.btnCancel.disabled = false;
            elements.btnCancel.textContent = 'Cancel Task';
        }
    } catch (err) {
        console.error(err);
        alert('Server error while sending cancel command.');
        elements.btnCancel.disabled = false;
        elements.btnCancel.textContent = 'Cancel Task';
    }
}

// 6. Screenshots Gallery Render
function parseTimestamp(filename) {
    // E.g. Screenshot_001.png or we can extract time metadata if we had it
    // For now we just return a sequential slide number
    const match = filename.match(/Screenshot_(\d+)\.png/);
    return match ? `Slide #${parseInt(match[1])}` : 'Slide';
}

function renderScreenshots() {
    elements.galleryGrid.innerHTML = '';
    
    if (state.screenshots.length === 0) {
        elements.galleryEmpty.classList.remove('hidden');
        return;
    }
    
    elements.galleryEmpty.classList.add('hidden');
    
    state.screenshots.forEach((slide, idx) => {
        const card = document.createElement('div');
        card.className = 'screenshot-card';
        card.innerHTML = `
            <div class="screenshot-img-wrapper">
                <img src="${slide.url}" alt="${slide.name}" loading="lazy">
                <div class="screenshot-hover-overlay">
                    <button class="overlay-btn btn-view" title="View Fullscreen">&#128269;</button>
                    <a href="${slide.url}" download="${slide.name}" class="overlay-btn btn-dl" title="Download Image" onclick="event.stopPropagation()">&#8595;</a>
                </div>
            </div>
            <div class="screenshot-info">
                <span class="screenshot-name">${slide.name}</span>
                <span class="screenshot-time">${slide.time}</span>
            </div>
        `;
        
        // Lightbox view bind
        card.addEventListener('click', () => openLightbox(idx));
        elements.galleryGrid.appendChild(card);
    });
}

// 7. Lightbox Functionality
function initLightbox() {
    elements.lightboxClose.addEventListener('click', closeLightbox);
    elements.lightboxPrev.addEventListener('click', showPrevLightbox);
    elements.lightboxNext.addEventListener('click', showNextLightbox);
    
    // Keyboard navigate
    document.addEventListener('keydown', (e) => {
        if (elements.lightbox.classList.contains('hidden')) return;
        
        if (e.key === 'Escape') closeLightbox();
        else if (e.key === 'ArrowLeft') showPrevLightbox();
        else if (e.key === 'ArrowRight') showNextLightbox();
    });
    
    // Close on clicking backdrop
    elements.lightbox.addEventListener('click', (e) => {
        if (e.target === elements.lightbox) closeLightbox();
    });
}

function openLightbox(index) {
    if (index < 0 || index >= state.screenshots.length) return;
    
    state.lightboxIndex = index;
    const slide = state.screenshots[index];
    
    elements.lightboxImg.src = slide.url;
    elements.lightboxCaption.textContent = `${slide.name} - ${slide.time}`;
    elements.lightbox.classList.remove('hidden');
}

function closeLightbox() {
    elements.lightbox.classList.add('hidden');
    elements.lightboxImg.src = '';
    state.lightboxIndex = -1;
}

function showPrevLightbox() {
    if (state.lightboxIndex <= 0) return;
    openLightbox(state.lightboxIndex - 1);
}

function showNextLightbox() {
    if (state.lightboxIndex >= state.screenshots.length - 1) return;
    openLightbox(state.lightboxIndex + 1);
}

// 8. Previous Run History Sidebar
async function fetchHistory() {
    try {
        const response = await fetch('/api/history');
        if (!response.ok) return;
        
        const data = await response.json();
        state.history = data.runs || [];
        renderHistoryList();
    } catch (err) {
        console.error('Error fetching history:', err);
    }
}

function renderHistoryList() {
    elements.historyList.innerHTML = '';
    
    if (state.history.length === 0) {
        elements.historyList.innerHTML = '<div class="empty-history">No runs found.</div>';
        return;
    }
    
    state.history.forEach(run => {
        const item = document.createElement('div');
        item.className = 'history-item';
        if (state.activeRunId === run.id) {
            item.classList.add('active');
        }
        
        // Humanized Title
        const titleParts = run.id.split('_');
        let datePart = '';
        let nameParts = [];
        
        // Find Date part in title elements (DD-MM-YYYY format)
        titleParts.forEach(p => {
            if (/^\d{2}-\d{2}-\d{4}$/.test(p)) {
                datePart = p;
            } else if (!/^\d+$/.test(p)) { // skip digits counters
                nameParts.push(p);
            }
        });
        
        const presenterNameStr = nameParts.join(' ').toUpperCase();
        const dateStr = datePart || 'Unknown Date';
        
        item.innerHTML = `
            <div class="history-info">
                <span class="history-title" title="${run.id}">${presenterNameStr}</span>
                <span class="history-meta">${dateStr} &bull; ${run.file_count} slides</span>
            </div>
            <div class="history-actions">
                <button type="button" class="btn-delete-run" title="Delete Run Folder" onclick="event.stopPropagation(); deleteRun('${run.id}')">&times;</button>
            </div>
        `;
        
        item.addEventListener('click', () => loadRunDetails(run.id));
        elements.historyList.appendChild(item);
    });
}

async function loadRunDetails(runId) {
    state.activeRunId = runId;
    
    // Highlight item in sidebar
    document.querySelectorAll('.history-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const clickedItem = Array.from(elements.historyList.children).find(item => 
        item.querySelector('.history-title').getAttribute('title') === runId
    );
    if (clickedItem) clickedItem.classList.add('active');
    
    try {
        const response = await fetch(`/api/history/${runId}`);
        if (!response.ok) {
            alert('Failed to load run details.');
            return;
        }
        
        const data = await response.json();
        
        // Populate Gallery
        state.screenshots = data.screenshots.map(filename => ({
            name: filename,
            url: `/output/${runId}/${filename}`,
            time: parseTimestamp(filename)
        }));
        
        // UI Layout adjust
        elements.configSection.classList.add('hidden');
        elements.taskSection.classList.add('hidden'); // Hide console
        elements.resultsSection.classList.remove('hidden');
        
        // Update Title labels
        const titleParts = runId.split('_');
        let datePart = '';
        let nameParts = [];
        titleParts.forEach(p => {
            if (/^\d{2}-\d{2}-\d{4}$/.test(p)) datePart = p;
            else if (!/^\d+$/.test(p)) nameParts.push(p);
        });
        
        elements.galleryTitle.textContent = `${nameParts.join(' ').toUpperCase()} - Slides`;
        elements.gallerySubtitle.textContent = `Extracted Run: ${runId}`;
        
        // Show download zip link
        elements.btnDownloadZip.href = `/api/history/${runId}/download-zip`;
        elements.btnDownloadZip.classList.remove('hidden');
        
        renderScreenshots();
        
    } catch (err) {
        console.error(err);
        alert('Server error loading run screenshots.');
    }
}

async function deleteRun(runId) {
    if (!confirm(`Are you sure you want to permanently delete run "${runId}"? All screenshot files in it will be lost.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/history/${runId}`, { method: 'DELETE' });
        if (response.ok) {
            if (state.activeRunId === runId) {
                // Return to form if we deleted the current run
                elements.btnBackToForm.click();
            }
            fetchHistory();
        } else {
            alert('Failed to delete the run folder.');
        }
    } catch (err) {
        console.error(err);
        alert('Server error while deleting run folder.');
    }
}

function initHistoryControls() {
    // History list elements binds automatically inside renderHistoryList
}
