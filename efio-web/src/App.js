// src/App.js
// Main application component with routing

import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Box, CssBaseline, Toolbar } from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';

import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import IOStatus from './pages/IOStatus';
import Metrics from './pages/Metrics';
import Diagnostic from './pages/Diagnostic';
import useEFIOWebSocket from './hooks/useEFIOWebSocket';

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
  const { connected, lastUpdate } = useEFIOWebSocket();

  return (
    <ThemeProvider theme={theme}>
      <BrowserRouter>
        <Box sx={{ display: 'flex' }}>
          <CssBaseline />
          
          {/* Sidebar Navigation */}
          <Sidebar />
          
          {/* Main Content Area */}
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
            <Toolbar /> {/* Spacer for fixed header */}
            
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/io" element={<IOStatus />} />
              <Route path="/metrics" element={<Metrics />} />
              <Route path="/diagnostic" element={<Diagnostic />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Box>
        </Box>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;