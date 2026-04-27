// Image Converter JavaScript

class ImageConverter {
  constructor() {
    this.conversionResults = [];
    this.selectedFiles = [];
    this.previewObjectUrls = [];
    this.loadingMessages = [];
    this.loadingInterval = null;
    this.savedPresets = JSON.parse(localStorage.getItem('image_converter_presets') || '{}');
    
    // DOM elements
    this.elements = {
      imageUrls: document.getElementById('imageUrls'),
      targetFormat: document.getElementById('targetFormat'),
      quality: document.getElementById('quality'),
      qualityValue: document.getElementById('qualityValue'),
      convertBtn: document.getElementById('convertBtn'),
      previewBtn: document.getElementById('previewBtn'),
      clearBtn: document.getElementById('clearBtn'),
      downloadAllBtn: document.getElementById('downloadAllBtn'),
      savePresetBtn: document.getElementById('savePresetBtn'),
      resultsContainer: document.getElementById('resultsContainer'),
      emptyState: document.getElementById('emptyState'),
      batchSummary: document.getElementById('batchSummary'),
      summaryText: document.getElementById('summaryText'),
      successCount: document.getElementById('successCount'),
      failedCount: document.getElementById('failedCount'),
      darkMode: document.getElementById('darkMode'),
      alertBox: document.getElementById('alert'),
      overlay: document.getElementById('loading'),
      fileUpload: document.getElementById('fileUpload'),
      filePreviewArea: document.getElementById('filePreviewArea'),
      previewContainer: document.getElementById('previewContainer'),
      
      // Advanced options
      enableResize: document.getElementById('enableResize'),
      resizeOptions: document.getElementById('resizeOptions'),
      resizeMode: document.getElementById('resizeMode'),
      resizeWidth: document.getElementById('resizeWidth'),
      resizeHeight: document.getElementById('resizeHeight'),
      scalePercent: document.getElementById('scalePercent'),
      scalePercentContainer: document.getElementById('scalePercentContainer'),
      
      enableWatermark: document.getElementById('enableWatermark'),
      watermarkOptions: document.getElementById('watermarkOptions'),
      watermarkText: document.getElementById('watermarkText'),
      watermarkPosition: document.getElementById('watermarkPosition'),
      watermarkOpacity: document.getElementById('watermarkOpacity'),
      opacityValue: document.getElementById('opacityValue'),
      watermarkFontSize: document.getElementById('watermarkFontSize'),
      
      rotation: document.getElementById('rotation'),
      flipHorizontal: document.getElementById('flipHorizontal'),
      flipVertical: document.getElementById('flipVertical'),
      
      stripMetadata: document.getElementById('stripMetadata'),
      progressive: document.getElementById('progressive'),
      optimize: document.getElementById('optimize'),
      
      filenamePrefix: document.getElementById('filenamePrefix'),
      filenameSuffix: document.getElementById('filenameSuffix'),
      addTimestamp: document.getElementById('addTimestamp'),
      
      enableColorAdjust: document.getElementById('enableColorAdjust'),
      colorAdjustOptions: document.getElementById('colorAdjustOptions'),
      brightness: document.getElementById('brightness'),
      brightnessValue: document.getElementById('brightnessValue'),
      contrast: document.getElementById('contrast'),
      contrastValue: document.getElementById('contrastValue'),
      saturation: document.getElementById('saturation'),
      saturationValue: document.getElementById('saturationValue'),
      grayscale: document.getElementById('grayscale')
    };

    // Loading messages
    this.urlLoadingMessages = [
      { text: "Downloading Images...", sub: "Fetching images from URLs" },
      { text: "Analyzing Formats...", sub: "Detecting source image formats" },
      { text: "Converting Images...", sub: "Applying format transformations" },
      { text: "Optimizing Quality...", sub: "Fine-tuning image quality" },
      { text: "Almost Done...", sub: "Finalizing conversions" }
    ];

    this.fileLoadingMessages = [
      { text: "Reading Files...", sub: "Processing uploaded images" },
      { text: "Analyzing Images...", sub: "Detecting format and properties" },
      { text: "Converting Formats...", sub: "Transforming to target format" },
      { text: "Optimizing Output...", sub: "Enhancing image quality" },
      { text: "Preparing Downloads...", sub: "Getting everything ready" }
    ];

    this.initializeEventListeners();
    this.initializeTheme();
    this.updateResults();
  }

  initializeEventListeners() {
    // Quality slider
    this.elements.quality.addEventListener('input', () => {
      this.elements.qualityValue.textContent = this.elements.quality.value;
    });

    // File upload
    this.elements.fileUpload.addEventListener('change', () => this.handleFileUpload());

    // Convert button
    this.elements.convertBtn.addEventListener('click', () => this.convertImages());

    // Preview button
    this.elements.previewBtn.addEventListener('click', () => this.previewSettings());

    // Clear button
    this.elements.clearBtn.addEventListener('click', () => this.clearResults());

    // Download all button
    this.elements.downloadAllBtn.addEventListener('click', () => this.downloadAll());

    // Save preset button
    this.elements.savePresetBtn.addEventListener('click', () => this.savePreset());

    // Theme toggle
    this.elements.darkMode.addEventListener('change', (e) => this.toggleTheme(e));

    // Advanced options toggles
    this.elements.enableResize?.addEventListener('change', (e) => {
      this.elements.resizeOptions.style.display = e.target.checked ? 'block' : 'none';
    });

    this.elements.enableWatermark?.addEventListener('change', (e) => {
      this.elements.watermarkOptions.style.display = e.target.checked ? 'block' : 'none';
    });

    this.elements.enableColorAdjust?.addEventListener('change', (e) => {
      this.elements.colorAdjustOptions.style.display = e.target.checked ? 'block' : 'none';
    });

    // Resize mode change
    this.elements.resizeMode?.addEventListener('change', (e) => {
      const isScale = e.target.value === 'scale';
      this.elements.scalePercentContainer.style.display = isScale ? 'block' : 'none';
      this.elements.resizeWidth.disabled = isScale;
      this.elements.resizeHeight.disabled = isScale;
    });

    // Watermark opacity slider
    this.elements.watermarkOpacity?.addEventListener('input', (e) => {
      this.elements.opacityValue.textContent = e.target.value + '%';
    });

    // Color adjustment sliders
    this.elements.brightness?.addEventListener('input', (e) => {
      this.elements.brightnessValue.textContent = e.target.value;
    });

    this.elements.contrast?.addEventListener('input', (e) => {
      this.elements.contrastValue.textContent = e.target.value;
    });

    this.elements.saturation?.addEventListener('input', (e) => {
      this.elements.saturationValue.textContent = e.target.value;
    });
  }

  initializeTheme() {
    const savedTheme = sessionStorage.getItem('cy_theme');
    if (savedTheme) document.documentElement.setAttribute('data-bs-theme', savedTheme);
    this.elements.darkMode.checked = (savedTheme || 'dark') === 'dark';
  }

  toggleTheme(e) {
    const theme = e.target.checked ? 'dark' : 'light';
    document.documentElement.setAttribute('data-bs-theme', theme);
    sessionStorage.setItem('cy_theme', theme);
  }

  setLoading(on, isFileMode = false) {
    const loadingOverlay = document.getElementById('loading');
    const loadingText = loadingOverlay?.querySelector('.loading-text');
    const loadingMessage = loadingOverlay?.querySelector('.loading-message');
    
    if (on) {
      this.loadingMessages = isFileMode ? this.fileLoadingMessages : this.urlLoadingMessages;
      let messageIndex = 0;
      
      // Set initial message
      if (this.loadingMessages[messageIndex]) {
        if (loadingText) loadingText.textContent = this.loadingMessages[messageIndex].text;
        if (loadingMessage) loadingMessage.textContent = this.loadingMessages[messageIndex].sub;
      }
      
      // Cycle through messages
      this.loadingInterval = setInterval(() => {
        messageIndex = (messageIndex + 1) % this.loadingMessages.length;
        if (this.loadingMessages[messageIndex]) {
          if (loadingText) loadingText.textContent = this.loadingMessages[messageIndex].text;
          if (loadingMessage) loadingMessage.textContent = this.loadingMessages[messageIndex].sub;
        }
      }, 1500);
      
      if (loadingOverlay) loadingOverlay.classList.remove('d-none');
    } else {
      clearInterval(this.loadingInterval);
      if (loadingOverlay) loadingOverlay.classList.add('d-none');
    }
    this.elements.convertBtn.disabled = on;
  }

  showAlert(type, msg) {
    this.elements.alertBox.className = `alert cy-card p-3 alert-${type}`;
    this.elements.alertBox.textContent = msg;
    this.elements.alertBox.classList.remove('d-none');
    setTimeout(() => this.elements.alertBox.classList.add('d-none'), 5000);
  }

  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  handleFileUpload() {
    const files = Array.from(this.elements.fileUpload.files);
    this.selectedFiles = files;
    this.releasePreviewUrls();
    
    if (files.length === 0) {
      this.elements.filePreviewArea.style.display = 'none';
      return;
    }

    this.elements.previewContainer.innerHTML = '';
    this.elements.filePreviewArea.style.display = 'block';

    files.forEach((file, index) => {
      const objectUrl = URL.createObjectURL(file);
      this.previewObjectUrls.push(objectUrl);
      const previewCard = this.createFilePreviewCard(file, objectUrl, index);
      this.elements.previewContainer.appendChild(previewCard);
    });
  }

  releasePreviewUrls() {
    this.previewObjectUrls.forEach(url => URL.revokeObjectURL(url));
    this.previewObjectUrls = [];
  }

  createFilePreviewCard(file, dataUrl, index) {
    const col = document.createElement('div');
    col.className = 'col-md-3 col-sm-4 col-6';
    
    col.innerHTML = `
      <div class="file-preview-card position-relative">
        <button class="remove-file" onclick="imageConverter.removeFile(${index})" type="button">
          <i class="fas fa-times"></i>
        </button>
        <img src="${dataUrl}" alt="${file.name}" class="file-preview-image">
        <div class="file-info">
          <div class="file-name">${file.name}</div>
          <div>${this.formatFileSize(file.size)}</div>
        </div>
      </div>
    `;
    
    return col;
  }

  removeFile(index) {
    const dt = new DataTransfer();
    const files = Array.from(this.elements.fileUpload.files);
    
    files.forEach((file, i) => {
      if (i !== index) dt.items.add(file);
    });
    
    this.elements.fileUpload.files = dt.files;
    this.selectedFiles = Array.from(dt.files);
    this.handleFileUpload();
  }

  createImageResult(result, index) {
    const div = document.createElement('div');
    div.className = `conversion-result ${result.success ? 'success-result' : 'error-result'}`;
    
    if (result.success) {
      const previewHtml = result.preview_url
        ? `<img src="${result.preview_url}" alt="Converted image" class="image-preview" style="width: 120px;">`
        : `<div class="image-preview d-flex align-items-center justify-content-center" style="width:120px;height:120px;background:rgba(79,140,255,.08);border:1px solid var(--border);border-radius:12px;color:var(--muted);font-size:.8rem;">${result.target_format}</div>`;
      const downloadHref = result.download_url || result.preview_url || result.data_url || '#';
      div.innerHTML = `
        <div class="d-flex gap-3">
          <div class="flex-shrink-0">
            ${previewHtml}
          </div>
          <div class="flex-grow-1">
            <h5 style="color: var(--text); margin: 0 0 0.5rem 0;">Image ${index + 1}</h5>
            <p style="color: var(--muted); font-size: 0.85rem; margin: 0 0 0.5rem 0; word-break: break-all;">
              ${result.original_url || result.filename || 'Uploaded file'}
            </p>
            <div class="conversion-stats">
              <div class="stat-item">
                <span class="stat-label">From:</span>
                <span class="stat-value">${result.source_format}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">To:</span>
                <span class="stat-value">${result.target_format}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Size:</span>
                <span class="stat-value">${result.image_info.width}x${result.image_info.height}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">File Size:</span>
                <span class="stat-value">${this.formatFileSize(result.file_size)}</span>
              </div>
            </div>
            <div class="mt-2">
              <a href="${downloadHref}" download="${result.filename || `converted_image_${index + 1}`}.${result.target_format.toLowerCase()}" class="download-btn">
                Download ${result.target_format}
              </a>
            </div>
          </div>
        </div>
      `;
    } else {
      div.innerHTML = `
        <div class="d-flex gap-3">
          <div class="flex-shrink-0" style="width: 120px; height: 120px; background: rgba(255,118,118,0.1); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: var(--danger);">
            ERR
          </div>
          <div class="flex-grow-1">
            <h5 style="color: var(--danger); margin: 0 0 0.5rem 0;">Image ${index + 1} - Failed</h5>
            <p style="color: var(--muted); font-size: 0.85rem; margin: 0 0 0.5rem 0; word-break: break-all;">
              ${result.original_url || result.filename || 'Uploaded file'}
            </p>
            <p style="color: var(--danger); font-size: 0.9rem; margin: 0;">
              Error: ${result.error}
            </p>
          </div>
        </div>
      `;
    }
    
    return div;
  }

  updateResults() {
    const existingResults = this.elements.resultsContainer.querySelectorAll('.conversion-result');
    existingResults.forEach(el => el.remove());

    if (this.conversionResults.length === 0) {
      this.elements.emptyState.style.display = 'block';
      this.elements.batchSummary.classList.add('d-none');
      this.elements.downloadAllBtn.disabled = true;
      return;
    }

    this.elements.emptyState.style.display = 'none';

    // Add results
    this.conversionResults.forEach((result, index) => {
      this.elements.resultsContainer.appendChild(this.createImageResult(result, index));
    });

    // Update summary
    const successful = this.conversionResults.filter(r => r.success).length;
    const failed = this.conversionResults.length - successful;
    
    this.elements.summaryText.textContent = `${this.conversionResults.length} images processed`;
    this.elements.successCount.textContent = successful;
    this.elements.failedCount.textContent = failed;
    this.elements.batchSummary.classList.remove('d-none');
    
    this.elements.downloadAllBtn.disabled = successful === 0;
  }

  getActiveConversionTab() {
    return document.querySelector('#conversionTabs .nav-link.active')?.id || 'url-tab';
  }

  async convertImages() {
    const activeTab = this.getActiveConversionTab();
    let requestData, endpoint, isFileMode;

    if (activeTab === 'url-tab') {
      // URL-based conversion
      const urls = this.elements.imageUrls.value.trim().split('\n').map(url => url.trim()).filter(Boolean);
      
      if (urls.length === 0) {
        this.showAlert('warning', 'Please enter at least one image URL');
        return;
      }

      if (urls.length > 20) {
        this.showAlert('warning', 'Maximum 20 images allowed per batch');
        return;
      }

      requestData = {
        urls: urls,
        format: this.elements.targetFormat.value,
        quality: parseInt(this.elements.quality.value),
        ...this.getAdvancedOptions()
      };
      endpoint = '/api/convert-images-batch';
      isFileMode = false;

    } else {
      // File upload conversion
      if (this.selectedFiles.length === 0) {
        this.showAlert('warning', 'Please select at least one image file');
        return;
      }

      if (this.selectedFiles.length > 20) {
        this.showAlert('warning', 'Maximum 20 images allowed per batch');
        return;
      }

      const formData = new FormData();
      this.selectedFiles.forEach(file => formData.append('files', file));
      formData.append('format', this.elements.targetFormat.value);
      formData.append('quality', this.elements.quality.value);
      
      // Add advanced options to formData
      const advancedOptions = this.getAdvancedOptions();
      Object.keys(advancedOptions).forEach(key => {
        formData.append(key, JSON.stringify(advancedOptions[key]));
      });

      requestData = formData;
      endpoint = '/api/convert-files-batch';
      isFileMode = true;
    }

    this.setLoading(true, isFileMode);

    try {
      const fetchOptions = {
        method: 'POST'
      };

      if (activeTab === 'url-tab') {
        fetchOptions.headers = { 'Content-Type': 'application/json' };
        fetchOptions.body = JSON.stringify(requestData);
      } else {
        fetchOptions.body = requestData;
      }

      const response = await fetch(endpoint, fetchOptions);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      this.conversionResults = data.results;
      this.updateResults();

      const successful = data.successful;
      const total = data.total_processed;
      
      if (successful === total) {
        this.showAlert('success', `Successfully converted all ${total} images.`);
      } else if (successful > 0) {
        this.showAlert('warning', `Converted ${successful} of ${total} images. ${total - successful} failed.`);
      } else {
        this.showAlert('danger', 'Failed to convert any images. Check your inputs and try again.');
      }

    } catch (error) {
      console.error('Conversion error:', error);
      this.showAlert('danger', 'Failed to convert images. Please try again.');
    } finally {
      this.setLoading(false);
    }
  }

  getAdvancedOptions() {
    const options = {};

    // Resize options
    if (this.elements.enableResize?.checked) {
      options.resize = {
        enabled: true,
        mode: this.elements.resizeMode.value,
        width: parseInt(this.elements.resizeWidth.value) || null,
        height: parseInt(this.elements.resizeHeight.value) || null,
        scale_percent: this.elements.resizeMode.value === 'scale' ? parseInt(this.elements.scalePercent.value) : null
      };
    }

    // Watermark options
    if (this.elements.enableWatermark?.checked && this.elements.watermarkText.value) {
      options.watermark = {
        enabled: true,
        text: this.elements.watermarkText.value,
        position: this.elements.watermarkPosition.value,
        opacity: parseInt(this.elements.watermarkOpacity.value),
        font_size: parseInt(this.elements.watermarkFontSize.value)
      };
    }

    // Transform options
    const rotation = parseInt(this.elements.rotation.value);
    if (rotation !== 0 || this.elements.flipHorizontal.checked || this.elements.flipVertical.checked) {
      options.transform = {
        rotation: rotation,
        flip_horizontal: this.elements.flipHorizontal.checked,
        flip_vertical: this.elements.flipVertical.checked
      };
    }

    // Optimization options
    options.optimization = {
      strip_metadata: this.elements.stripMetadata.checked,
      progressive: this.elements.progressive.checked,
      optimize: this.elements.optimize.checked
    };

    // File naming options
    options.naming = {
      prefix: this.elements.filenamePrefix.value || '',
      suffix: this.elements.filenameSuffix.value || '',
      add_timestamp: this.elements.addTimestamp.checked
    };

    // Color adjustments
    if (this.elements.enableColorAdjust?.checked) {
      const brightness = parseInt(this.elements.brightness.value);
      const contrast = parseInt(this.elements.contrast.value);
      const saturation = parseInt(this.elements.saturation.value);
      
      if (brightness !== 0 || contrast !== 0 || saturation !== 0 || this.elements.grayscale.checked) {
        options.color_adjust = {
          enabled: true,
          brightness: brightness,
          contrast: contrast,
          saturation: saturation,
          grayscale: this.elements.grayscale.checked
        };
      }
    }

    return options;
  }

  previewSettings() {
    const options = this.getAdvancedOptions();
    const settings = {
      format: this.elements.targetFormat.value,
      quality: this.elements.quality.value,
      ...options
    };

    const settingsText = JSON.stringify(settings, null, 2);
    
    // Create modal to show settings
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
      <div class="modal-dialog modal-lg">
        <div class="modal-content cy-card">
          <div class="modal-header">
            <h5 class="modal-title"><i class="fas fa-cog"></i> Current Settings</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <pre style="background: var(--panel); padding: 1rem; border-radius: 8px; max-height: 400px; overflow-y: auto;"><code>${this.escapeHtml(settingsText)}</code></pre>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-ghost" data-bs-dismiss="modal">Close</button>
            <button type="button" class="btn btn-primary" id="copyJsonBtn">
              <i class="fas fa-copy"></i> Copy JSON
            </button>
          </div>
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // Add copy button handler after modal is added to DOM
    const copyBtn = modal.querySelector('#copyJsonBtn');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(settingsText).then(() => {
          copyBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
          setTimeout(() => {
            copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy JSON';
          }, 2000);
        }).catch(err => {
          console.error('Failed to copy:', err);
          copyBtn.innerHTML = '<i class="fas fa-times"></i> Failed';
          setTimeout(() => {
            copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy JSON';
          }, 2000);
        });
      });
    }
    
    modal.addEventListener('hidden.bs.modal', () => {
      modal.remove();
    });
  }

  savePreset() {
    const presetName = prompt('Enter a name for this preset:');
    if (!presetName) return;

    const settings = {
      format: this.elements.targetFormat.value,
      quality: this.elements.quality.value,
      ...this.getAdvancedOptions()
    };

    this.savedPresets[presetName] = settings;
    localStorage.setItem('image_converter_presets', JSON.stringify(this.savedPresets));
    
    this.showAlert('success', `Preset "${presetName}" saved successfully.`);
  }

  loadPreset(presetName) {
    const preset = this.savedPresets[presetName];
    if (!preset) {
      this.showAlert('danger', 'Preset not found');
      return;
    }

    // Apply settings from preset
    this.elements.targetFormat.value = preset.format;
    this.elements.quality.value = preset.quality;
    this.elements.qualityValue.textContent = preset.quality;

    // Apply advanced options if present
    if (preset.resize) {
      this.elements.enableResize.checked = true;
      this.elements.resizeOptions.style.display = 'block';
      this.elements.resizeMode.value = preset.resize.mode;
      this.elements.resizeWidth.value = preset.resize.width || '';
      this.elements.resizeHeight.value = preset.resize.height || '';
      if (preset.resize.scale_percent) {
        this.elements.scalePercent.value = preset.resize.scale_percent;
      }
    }

    // Apply watermark if present
    if (preset.watermark) {
      this.elements.enableWatermark.checked = true;
      this.elements.watermarkOptions.style.display = 'block';
      this.elements.watermarkText.value = preset.watermark.text;
      this.elements.watermarkPosition.value = preset.watermark.position;
      this.elements.watermarkOpacity.value = preset.watermark.opacity;
      this.elements.watermarkFontSize.value = preset.watermark.font_size;
    }

    this.showAlert('success', `Loaded preset "${presetName}".`);
  }

  escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
  }

  clearResults() {
    this.conversionResults = [];
    this.updateResults();
    this.showAlert('info', 'Results cleared');
  }

  downloadAll() {
    const successfulResults = this.conversionResults.filter(r => r.success);
    
    successfulResults.forEach((result, index) => {
      const href = result.download_url || result.preview_url || result.data_url;
      if (!href) return;
      const link = document.createElement('a');
      link.href = href;
      link.download = `${result.filename || `converted_image_${index + 1}`}.${result.target_format.toLowerCase()}`;
      link.click();
    });

    this.showAlert('success', `Started download of ${successfulResults.length} images`);
  }
}

// Initialize the image converter when the page loads
let imageConverter;
document.addEventListener('DOMContentLoaded', () => {
  imageConverter = new ImageConverter();
});
