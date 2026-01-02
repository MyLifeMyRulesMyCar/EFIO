// src/contexts/AuthContext.js
// FIXED: Properly handle force_password_change

import React, { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode';
import apiConfig from '../config/apiConfig';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check for existing token on mount
  useEffect(() => {
    console.log('🔍 AuthContext: Checking for existing token...');
    const token = localStorage.getItem('access_token');
    
    if (token) {
      try {
        const decoded = jwtDecode(token);
        console.log('📜 Decoded token:', decoded);
        
        // Check if token is expired
        if (decoded.exp * 1000 > Date.now()) {
          const userData = {
            username: decoded.sub,
            role: decoded.role,
            email: decoded.email,
            full_name: decoded.full_name,
            force_password_change: decoded.force_password_change || false
          };
          
          console.log('✅ Valid token found, user:', userData);
          setUser(userData);
        } else {
          console.log('⏰ Token expired, attempting refresh...');
          refreshToken();
        }
      } catch (error) {
        console.error('❌ Invalid token:', error);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
      }
    } else {
      console.log('ℹ️ No token found');
    }
    
    setLoading(false);
  }, []);

  const login = async (username, password) => {
    console.log('🔐 Attempting login for:', username);
    
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();
      console.log('📥 Login response:', data);

      if (!response.ok) {
        throw new Error(data.error || 'Login failed');
      }

      // Store tokens
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      // Decode token to get user info
      const decoded = jwtDecode(data.access_token);
      console.log('📜 Decoded new token:', decoded);
      
      const userData = {
        username: decoded.sub,
        role: decoded.role,
        email: decoded.email,
        full_name: decoded.full_name,
        force_password_change: decoded.force_password_change || false
      };
      
      console.log('✅ Login successful, user data:', userData);
      setUser(userData);

      return { 
        success: true, 
        force_password_change: data.force_password_change || decoded.force_password_change || false
      };
    } catch (error) {
      console.error('❌ Login error:', error);
      return { success: false, error: error.message };
    }
  };

  const logout = () => {
    console.log('🚪 Logging out...');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  };

  const refreshToken = async () => {
    const refresh = localStorage.getItem('refresh_token');
    if (!refresh) {
      logout();
      return false;
    }

    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${refresh}`,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error('Refresh failed');
      }

      localStorage.setItem('access_token', data.access_token);

      const decoded = jwtDecode(data.access_token);
      setUser({
        username: decoded.sub,
        role: decoded.role,
        email: decoded.email,
        full_name: decoded.full_name,
        force_password_change: decoded.force_password_change || false
      });

      return true;
    } catch (error) {
      console.error('Token refresh error:', error);
      logout();
      return false;
    }
  };

  const getAuthHeader = () => {
    const token = localStorage.getItem('access_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  };

  const hasRole = (requiredRole) => {
    if (!user) return false;
    if (requiredRole === 'admin') return user.role === 'admin';
    if (requiredRole === 'operator') return ['admin', 'operator'].includes(user.role);
    return true;
  };

  const value = {
    user,
    loading,
    login,
    logout,
    refreshToken,
    getAuthHeader,
    hasRole,
    isAuthenticated: !!user
  };

  console.log('🔄 AuthContext state:', { user, loading, isAuthenticated: !!user });

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};