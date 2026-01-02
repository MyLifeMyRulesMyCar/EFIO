// efio-web/src/config/apiConfig.js
// Centralized API configuration with auto-detection

/**
 * Get API base URL with auto-detection
 * Priority:
 * 1. Environment variable REACT_APP_API_URL (if not 'auto')
 * 2. Auto-detect from browser URL
 * 3. Fallback to localhost
 */
export const getApiBaseUrl = () => {
  const envUrl = process.env.REACT_APP_API_URL;
  
  // If explicitly set and not 'auto', use it
  if (envUrl && envUrl !== 'auto') {
    console.log('✅ API URL from env:', envUrl);
    return envUrl;
  }
  
  // Auto-detect from browser URL
  try {
    const hostname = window.location.hostname;
    const port = process.env.REACT_APP_API_PORT || '5000';
    
    // Don't use localhost/127.0.0.1 if accessed via IP
    if (hostname && hostname !== 'localhost' && hostname !== '127.0.0.1') {
      const apiUrl = `http://${hostname}:${port}`;
      console.log('✅ API URL auto-detected:', apiUrl);
      return apiUrl;
    }
  } catch (error) {
    console.warn('⚠️ API URL auto-detection failed:', error);
  }
  
  // Fallback to localhost
  const fallbackUrl = 'http://localhost:5000';
  console.log('⚠️ API URL fallback:', fallbackUrl);
  return fallbackUrl;
};

/**
 * Get WebSocket URL (same as API URL but ws:// protocol)
 */
export const getWebSocketUrl = () => {
  const apiUrl = getApiBaseUrl();
  return apiUrl.replace('http://', 'ws://').replace('https://', 'wss://');
};

// Export as default object
const apiConfig = {
  baseUrl: getApiBaseUrl(),
  wsUrl: getWebSocketUrl(),
  timeout: 10000, // 10 seconds
};

export default apiConfig;

/**
 * Usage in components:
 * 
 * import apiConfig from './config/apiConfig';
 * 
 * fetch(`${apiConfig.baseUrl}/api/status`)
 * 
 * Or use the hook:
 * const { apiUrl } = useApiConfig();
 */