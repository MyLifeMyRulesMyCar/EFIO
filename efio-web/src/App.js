// src/App.js - UPDATED: Handle forced password changes

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Box, CssBaseline, Toolbar, Alert } from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';

import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Login from './pages/Login';
import ChangePassword from './pages/ChangePassword';  // NEW IMPORT
import Dashboard from './pages/Dashboard';
import IOStatus from './pages/IOStatus';
import Metrics from './pages/Metrics';
import Diagnostic from './pages/Diagnostic';
import NetworkSettings from './pages/NetworkSettings';
import IOConfiguration from './pages/IOConfiguration';
import useEFIOWebSocket from './hooks/useEFIOWebSocket';
import ModbusManager from './pages/ModbusManager';
import BackupRestore from './pages/BackupRestore'; 
import MQTTSettings from './pages/MQTTSettings';
import ModbusMQTTBridge from './pages/ModbusMQTTBridge';
import CANManager from './pages/CANManager';

const drawerWidth = 240;

const theme = createTheme({
  palette: {
    primary: { main: '#667eea' },
    secondary: { main: '#764ba2' },
    success: { main: '#10b981', light: '#d1fae5' },
    warning: { main: '#f59e0b', light: '#fef3c7' },
    error: { main: '#ef4444' },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
});

function Settings() {
  return (
    <Box sx={{ p: 3 }}>
      <h2>Settings</h2>
      <p>Settings page coming soon...</p>
    </Box>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            
            {/* NEW: Password change route (allow access immediately after login) */}
            <Route path="/change-password" element={<ChangePassword />} />
            
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

// NEW: Password change guard component
function PasswordChangeGuard({ children }) {
  const { user } = useAuth();
  
  if (user?.force_password_change) {
    return <Navigate to="/change-password" replace />;
  }
  
  return children;
}

function MainLayout() {
  const { connected, lastUpdate } = useEFIOWebSocket();
  const { user } = useAuth();  // NEW: Access user to check password status

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
        
        {/* NEW: Show warning if password needs to be changed */}
        {user?.force_password_change && (
          <Box sx={{ p: 2 }}>
            <Alert severity="error">
              <strong>Action Required:</strong> You are using a default password. 
              You will be redirected to change it.
            </Alert>
          </Box>
        )}
        
        {/* NEW: Wrap routes in PasswordChangeGuard */}
        <PasswordChangeGuard>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/io" element={<IOStatus />} />
            <Route path="/metrics" element={<Metrics />} />
            <Route path="/diagnostic" element={<Diagnostic />} />
            <Route path="/modbus" element={<ModbusManager />} />
            <Route path="/can" element={<CANManager />} />
            <Route path="/modbus-mqtt-bridge" element={<ModbusMQTTBridge />} />
            
            <Route path="/backup" element={
              <ProtectedRoute requiredRole="admin">
                <BackupRestore />
              </ProtectedRoute>
            } />
            
            <Route path="/config/network" element={
              <ProtectedRoute requiredRole="admin">
                <NetworkSettings />
              </ProtectedRoute>
            } />
            
            <Route path="/config/mqtt" element={
              <ProtectedRoute requiredRole="admin">
                <MQTTSettings />
              </ProtectedRoute>
            } />
            
            <Route path="/config/io" element={<IOConfiguration />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </PasswordChangeGuard>
      </Box>
    </Box>
  );
}

export default App;