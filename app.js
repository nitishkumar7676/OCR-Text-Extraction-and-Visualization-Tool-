/**
 * OCR Web Application Frontend
 * Handles file upload, document management, and results display
 */

const API_BASE_URL = '/api/v1';
let currentPage = 1;
let currentDocumentId = null;
let currentDocumentResults = [];

// ==================== DOM Elements ====================

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const selectFileBtn = document.getElementById('selectFileBtn');
const uploadProgress = document.getElementById('uploadProgress');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const documentsList = document.getElementById('documentsList');
const statusFilter = document.getElementById('statusFilter');
const refreshBtn = document.getElementById('refreshBtn');
const resultModal = document.getElementById('resultModal');
const closeModal = document.getElementById('closeModal');
const toast = document.getElementById('toast');
const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

// ==================== Event Listeners ====================

// Upload area events
uploadArea.addEventListener('click', () => fileInput.click());
selectFileBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleFileSelect);

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('drag-over');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
    if (e.dataTransfer.files.length) {
        handleFiles(e.dataTransfer.files);
    }
});

// Filter and refresh
statusFilter.addEventListener('change', loadDocuments);
refreshBtn.addEventListener('click', () => {
    loadDocuments();
    loadStats();
});

// Modal events
closeModal.addEventListener('click', () => resultModal.style.display = 'none');
window.addEventListener('click', (e) => {
    if (e.target === resultModal) resultModal.style.display = 'none';
});

// Tab switching
tabButtons.forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.getAttribute('data-tab')));
});

// Page navigation
document.getElementById('prevPageBtn')?.addEventListener('click', previousPage);
document.getElementById('nextPageBtn')?.addEventListener('click', nextPage);

// ==================== File Handling ====================

function handleFileSelect(e) {
    const files = e.target.files;
    handleFiles(files);
}

function handleFiles(files) {
    for (let file of files) {
        if (file.size > 50 * 1024 * 1024) {
            showToast(`File ${file.name} is too large (> 50MB)`, 'error');
            continue;
        }

        const ext = file.name.toLowerCase().split('.').pop();
        if (!['pdf', 'tiff', 'tif'].includes(ext)) {
            showToast(`File type .${ext} not supported`, 'error');
            continue;
        }

        uploadFile(file);
    }
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    uploadProgress.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = `Uploading ${file.name}...`;

    try {
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progressFill.style.width = percentComplete + '%';
                progressText.textContent = `Uploading ${file.name}... ${Math.round(percentComplete)}%`;
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.response);
                showToast(`File uploaded successfully!`, 'success');
                document.getElementById('fileInput').value = '';
                uploadProgress.style.display = 'none';
                loadDocuments();
                loadStats();

                // Poll for completion
                pollFileProcessing(response.document_id);
            } else {
                const error = JSON.parse(xhr.response);
                showToast(`Upload failed: ${error.detail}`, 'error');
            }
        });

        xhr.addEventListener('error', () => {
            showToast('Upload failed', 'error');
        });

        xhr.open('POST', `${API_BASE_URL}/upload`);
        xhr.send(formData);
    } catch (error) {
        showToast(`Error uploading file: ${error.message}`, 'error');
        uploadProgress.style.display = 'none';
    }
}

// ==================== Document Management ====================

async function loadDocuments() {
    try {
        const status = statusFilter.value;
        const url = status ? 
            `${API_BASE_URL}/documents?status=${status}` : 
            `${API_BASE_URL}/documents`;

        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to load documents');

        const documents = await response.json();

        if (documents.length === 0) {
            documentsList.innerHTML = '<p class="empty-message">No documents uploaded yet</p>';
            return;
        }

        documentsList.innerHTML = documents.map(doc => `
            <div class="document-card">
                <div class="document-info">
                    <div class="document-name">${escapeHtml(doc.original_filename)}</div>
                    <div class="document-meta">
                        <span>📅 ${formatDate(doc.upload_date)}</span>
                        <span>📦 ${formatFileSize(doc.file_size)}</span>
                        <span>📄 ${doc.page_count} page${doc.page_count !== 1 ? 's' : ''}</span>
                        <span><span class="status-badge status-${doc.processing_status}">${doc.processing_status}</span></span>
                    </div>
                </div>
                <div class="document-actions">
                    ${doc.processing_status === 'completed' ? `
                        <button class="btn btn-primary btn-small" onclick="viewResults(${doc.id})">View Results</button>
                    ` : ''}
                    <button class="btn btn-danger btn-small" onclick="deleteDocument(${doc.id})">Delete</button>
                </div>
            </div>
        `).join('');

    } catch (error) {
    console.error('FULL ERROR:', error);
    alert(error.message);
    documentsList.innerHTML =
        '<p class="empty-message">Error loading documents</p>';

    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
        if (!response.ok) throw new Error('Failed to load stats');

        const stats = await response.json();

        document.getElementById('statTotal').textContent = stats.total_documents;
        document.getElementById('statCompleted').textContent = stats.completed;
        document.getElementById('statProcessing').textContent = stats.processing;
        document.getElementById('statFailed').textContent = stats.failed;

    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function viewResults(documentId) {
    try {
        const response = await fetch(`${API_BASE_URL}/documents/${documentId}`);
        if (!response.ok) throw new Error('Failed to load document');

        const docData = await response.json();

        currentDocumentId = documentId;
        currentDocumentResults = docData.ocr_results || [];
        currentPage = 1;

        document.getElementById('modalTitle').textContent =
          `OCR Results - ${escapeHtml(docData.original_filename)}`;

        resultModal.style.display = 'block';
        displayPageContent();
        displayBoundingBoxes();

    } catch (error) {
        console.error('Error loading results:', error);
        showToast('Error loading results', 'error');
    }
}

function displayPageContent() {
    if (currentDocumentResults.length === 0) {
        document.getElementById('extractedText').textContent = 'No text extracted';
        document.getElementById('confidenceScore').textContent = '0%';
        document.getElementById('pageIndicator').textContent = 'Page 0';
        return;
    }

    const pageData = currentDocumentResults[currentPage - 1];
    document.getElementById('extractedText').textContent = pageData.extracted_text || '[No text extracted]';
    document.getElementById('confidenceScore').textContent = 
        `${Math.round((pageData.confidence_score || 0) * 100)}%`;
    document.getElementById('pageIndicator').textContent = 
        `Page ${currentPage} of ${currentDocumentResults.length}`;

    updatePageButtons();
}

function displayBoundingBoxes() {
    const tbody = document.getElementById('boundingBoxesBody');
    
    if (currentDocumentResults.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6">No data</td></tr>';
        return;
    }

    const pageData = currentDocumentResults[currentPage - 1];
    const boxes = pageData.bounding_boxes || [];

    tbody.innerHTML = boxes.map((box, index) => {
    const width = box.x_max - box.x_min;
    const height = box.y_max - box.y_min;

    return `
        <tr>
            <td>${index + 1}</td>
            <td>${escapeHtml(box.text)}</td>
            <td>${Math.round(box.x_min)}</td>
            <td>${Math.round(box.y_min)}</td>
            <td>${Math.round(width)}</td>
            <td>${Math.round(height)}</td>
        </tr>
    `;
}).join('');

}

function updatePageButtons() {
    document.getElementById('prevPageBtn').disabled = currentPage <= 1;
    document.getElementById('nextPageBtn').disabled = currentPage >= currentDocumentResults.length;
}

function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        displayPageContent();
        displayBoundingBoxes();
    }
}

function nextPage() {
    if (currentPage < currentDocumentResults.length) {
        currentPage++;
        displayPageContent();
        displayBoundingBoxes();
    }
}

function switchTab(tabName) {
    tabButtons.forEach(btn => btn.classList.remove('active'));
    tabContents.forEach(content => content.classList.remove('active'));

    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(tabName).classList.add('active');
}

async function deleteDocument(documentId) {
    if (!confirm('Are you sure you want to delete this document? This action cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
            method: 'DELETE',
        });

        if (!response.ok) throw new Error('Failed to delete document');

        showToast('Document deleted successfully', 'success');
        loadDocuments();
        loadStats();

        if (currentDocumentId === documentId) {
            resultModal.style.display = 'none';
        }

    } catch (error) {
        console.error('Error deleting document:', error);
        showToast('Error deleting document', 'error');
    }
}

async function pollFileProcessing(documentId) {
    let retries = 0;
    const maxRetries = 120; // 10 minutes with 5-second intervals

    const poll = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/documents/${documentId}/status`);
            if (!response.ok) throw new Error('Failed to check status');

            const data = await response.json();

            if (data.status === 'completed') {
                showToast(`Processing completed for document #${documentId}`, 'success');
                loadDocuments();
                loadStats();
                return;
            } else if (data.status === 'failed') {
                showToast(`Processing failed: ${data.error}`, 'error');
                loadDocuments();
                loadStats();
                return;
            }

            retries++;
            if (retries < maxRetries) {
                setTimeout(poll, 5000); // Check again in 5 seconds
            }

        } catch (error) {
            console.error('Error checking processing status:', error);
        }
    };

    poll();
}

// ==================== Utility Functions ====================

function showToast(message, type = 'info') {
    toast.textContent = message;
    toast.className = `toast show ${type}`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// ==================== Initialization ====================

document.addEventListener('DOMContentLoaded', () => {
    loadDocuments();
    loadStats();

    // Refresh documents and stats every 30 seconds
    setInterval(() => {
        loadDocuments();
        loadStats();
    }, 30000);
});
