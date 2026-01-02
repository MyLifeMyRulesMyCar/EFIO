// src/utils/api.js
// Centralized API utility functions - USE THIS EVERYWHERE

/**
 * Get API base URL with auto-detection
 * This detects the backend URL from browser URL
 */
export const getApiBaseUrl = () => {
  // Check environment variable first
  const envUrl = process.env.REACT_APP_API_URL;
  
  if (envUrl && envUrl !== 'auto') {
    return envUrl;
  }
  
  // Auto-detect from browser
  const hostname = window.location.hostname;
  const port = process.env.REACT_APP_API_PORT || '5000';
  
  // If accessed via IP or hostname (not localhost), use same host
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    return `http://${hostname}:${port}`;
  }
  
  // Fallback to localhost
  return `http://localhost:${port}`;
};

/**
 * Get WebSocket URL
 */
export const getWebSocketUrl = () => {
  return getApiBaseUrl();
};

/**
 * Make authenticated API call
 */
export const fetchApi = async (endpoint, options = {}) => {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint}`;
  
  // Add auth header if token exists
  const token = localStorage.getItem('access_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` }),
    ...options.headers
  };
  
  const response = await fetch(url, {
    ...options,
    headers
  });
  
  return response;
};

/**
 * Export singleton config
 */
export const API_CONFIG = {
  get baseUrl() {
    return getApiBaseUrl();
  },
  get wsUrl() {
    return getWebSocketUrl();
  }
};

export default API_CONFIG;