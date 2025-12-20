// src/App.js
// Main application component with routing

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Box, CssBaseline, Toolbar } from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';

import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import IOStatus from './pages/IOStatus';
import Metrics from './pages/Metrics';
import Diagnostic from './pages/Diagnostic';
import NetworkSettings from './pages/NetworkSettings';
import IOConfiguration from './pages/IOConfiguration';
import useEFIOWebSocket from './hooks/useEFIOWebSocket';
import ModbusManager from './pages/ModbusManager';

const drawerWidth = 240;

// Create Material-UI theme
const theme = createTheme({
  palette: {
    primary: {
      main: '#667eea',
    },
    secondary: {
      main: '#764ba2',
    },
    success: {
      main: '#10b981',
      light: '#d1fae5',
    },
    warning: {
      main: '#f59e0b',
      light: '#fef3c7',
    },
    error: {
      main: '#ef4444',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
});

// Settings page placeholder
function Settings() {
  return (
    <Box sx={{ p: 3 }}>
      <h2>Settings</h2>
      <p>Settings page coming soon in Week 2...</p>
    </Box>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<Login />} />
            
            {/* Protected routes */}
            <Route path="/*" element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            } />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

// Main layout with sidebar and header
function MainLayout() {
  const { connected, lastUpdate } = useEFIOWebSocket();

  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />
      <Sidebar />
      
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          bgcolor: 'background.default',
          minHeight: '100vh',
          ml: `${drawerWidth}px`,
        }}
      >
        <Header connected={connected} title="EdgeForce-1000 Dashboard" lastUpdate={lastUpdate} />
        <Toolbar />
        
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/io" element={<IOStatus />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/diagnostic" element={<Diagnostic />} />
          <Route path="/modbus" element={<ModbusManager />} />
          
          {/* Configuration routes */}
          <Route path="/config/network" element={
            <ProtectedRoute requiredRole="admin">
              <NetworkSettings />
            </ProtectedRoute>
          } />
          <Route path="/config/io" element={<IOConfiguration />} />
          
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Box>
    </Box>
  );
}

export default App;