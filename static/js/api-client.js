/**
 * FormatNormalizer API Client
 * 
 * JavaScript client for interacting with the FormatNormalizer API
 */

class FormatNormalizerClient {
  /**
   * Initialize the FormatNormalizer API client
   * 
   * @param {string} apiUrl - Base URL of the FormatNormalizer API
   */
  constructor(apiUrl) {
    this.apiUrl = apiUrl || window.location.origin;
    this.endpoints = {
      normalize: '/api/normalize',
      jobs: '/api/jobs',
      presets: '/api/presets',
      formats: '/api/formats'
    };
  }

  /**
   * Submit a normalization job with file upload
   * 
   * @param {File} file - File object to upload
   * @param {Object} options - Normalization options
   * @returns {Promise<Object>} - Job submission result
   */
  async normalizeFile(file, options) {
    const formData = new FormData();
    formData.append('file', file);
    
    // Add options to form data
    formData.append('target_format', JSON.stringify(options.target || {}));
    
    if (options.preset) {
      formData.append('preset', options.preset);
    }
    
    if (options.enable_ai !== undefined) {
      formData.append('enable_ai', options.enable_ai);
    }
    
    if (options.validate_output !== undefined) {
      formData.append('validate_output', options.validate_output);
    }
    
    if (options.priority) {
      formData.append('priority', options.priority);
    }
    
    const response = await fetch(`${this.apiUrl}${this.endpoints.normalize}`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  }

  /**
   * Submit a normalization job with source URL
   * 
   * @param {string} sourceUrl - URL of the source media
   * @param {Object} options - Normalization options
   * @returns {Promise<Object>} - Job submission result
   */
  async normalizeUrl(sourceUrl, options) {
    const formData = new FormData();
    formData.append('source_url', sourceUrl);
    
    // Add options to form data
    formData.append('target_format', JSON.stringify(options.target || {}));
    
    if (options.preset) {
      formData.append('preset', options.preset);
    }
    
    if (options.enable_ai !== undefined) {
      formData.append('enable_ai', options.enable_ai);
    }
    
    if (options.validate_output !== undefined) {
      formData.append('validate_output', options.validate_output);
    }
    
    if (options.priority) {
      formData.append('priority', options.priority);
    }
    
    const response = await fetch(`${this.apiUrl}${this.endpoints.normalize}`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  }

  /**
   * Get job status by ID
   * 
   * @param {string} jobId - Job ID to check
   * @returns {Promise<Object>} - Job status
   */
  async getJobStatus(jobId) {
    const response = await fetch(`${this.apiUrl}${this.endpoints.jobs}/${jobId}`, {
      method: 'GET'
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  }

  /**
   * List normalization jobs
   * 
   * @param {string} status - Optional status filter
   * @param {number} limit - Maximum number of jobs to return
   * @returns {Promise<Array>} - List of jobs
   */
  async listJobs(status, limit = 100) {
    let url = `${this.apiUrl}${this.endpoints.jobs}?limit=${limit}`;
    if (status) {
      url += `&status=${status}`;
    }
    
    const response = await fetch(url, {
      method: 'GET'
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  }

  /**
   * Get available presets
   * 
   * @returns {Promise<Object>} - Available presets
   */
  async getPresets() {
    const response = await fetch(`${this.apiUrl}${this.endpoints.presets}`, {
      method: 'GET'
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  }

  /**
   * Get supported formats
   * 
   * @returns {Promise<Object>} - Supported formats
   */
  async getFormats() {
    const response = await fetch(`${this.apiUrl}${this.endpoints.formats}`, {
      method: 'GET'
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  }

  /**
   * Poll for job status until completion
   * 
   * @param {string} jobId - Job ID to poll
   * @param {function} onUpdate - Callback for status updates
   * @param {number} interval - Polling interval in milliseconds
   * @param {number} timeout - Maximum time to poll in milliseconds
   * @returns {Promise<Object>} - Final job status
   */
  async pollJobStatus(jobId, onUpdate, interval = 2000, timeout = 3600000) {
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeout) {
      const status = await this.getJobStatus(jobId);
      
      if (onUpdate) {
        onUpdate(status);
      }
      
      if (status.status === 'completed' || status.status === 'failed') {
        return status;
      }
      
      await new Promise(resolve => setTimeout(resolve, interval));
    }
    
    throw new Error('Job polling timed out');
  }
}