// src/pages/Diagnostic.js
// Diagnostic page to test connection and display logs

import React, { useState, useEffect } from 'react';
import apiConfig from '../config/apiConfig';
import {
  Box,
  Typography,
  Paper,
  Button,
  Card,
  CardContent,
  Chip,
  Alert,
  Grid,
  Divider
} from '@mui/material';
import {
  Refresh,
  CheckCircle,
  Cancel,
  BugReport
} from '@mui/icons-material';
import useEFIOWebSocket from '../hooks/useEFIOWebSocket';

export default function Diagnostic() {
  const { connected, ioData, systemData, socket } = useEFIOWebSocket();
  const [restApiStatus, setRestApiStatus] = useState('Checking...');
  const [logs, setLogs] = useState([]);

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev.slice(-20), { timestamp, message, type }]);
  };

  useEffect(() => {
    // Test REST API
    fetch(`${apiConfig.baseUrl}/api/status`)
      .then(res => res.json())
      .then(data => {
        setRestApiStatus('✅ Connected');
        addLog(`REST API: ${JSON.stringify(data)}`, 'success');
      })
      .catch(err => {
        setRestApiStatus('❌ Failed');
        addLog(`REST API Error: ${err.message}`, 'error');
      });
  }, []);

  const testRestIO = () => {
    addLog('Testing REST API /api/io...', 'info');
    fetch(`${apiConfig.baseUrl}/api/io`)
      .then(res => res.json())
      .then(data => {
        addLog(`REST I/O: ${JSON.stringify(data)}`, 'success');
      })
      .catch(err => {
        addLog(`REST Error: ${err.message}`, 'error');
      });
  };

  const testRestSystem = () => {
    addLog('Testing REST API /api/system...', 'info');
    fetch(`${apiConfig.baseUrl}/api/system`)
      .then(res => res.json())
      .then(data => {
        addLog(`REST System: ${JSON.stringify(data)}`, 'success');
      })
      .catch(err => {
        addLog(`REST Error: ${err.message}`, 'error');
      });
  };

  const testWebSocketIO = () => {
    if (!socket) {
      addLog('Socket not initialized!', 'error');
      return;
    }
    if (!connected) {
      addLog('Socket not connected!', 'error');
      return;
    }
    addLog('Requesting I/O via WebSocket...', 'info');
    socket.emit('request_io');
  };

  const testWebSocketSystem = () => {
    if (!socket) {
      addLog('Socket not initialized!', 'error');
      return;
    }
    if (!connected) {
      addLog('Socket not connected!', 'error');
      return;
    }
    addLog('Requesting System via WebSocket...', 'info');
    socket.emit('request_system');
  };

  const testToggleDO = () => {
    if (!socket || !connected) {
      addLog('Cannot test: WebSocket not connected', 'error');
      return;
    }
    addLog('Testing DO0 toggle via WebSocket...', 'info');
    socket.emit('set_do', { channel: 0, value: 1 });
    setTimeout(() => {
      socket.emit('set_do', { channel: 0, value: 0 });
    }, 1000);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <BugReport sx={{ fontSize: 40 }} />
        <Typography variant="h4" fontWeight="bold">
          Connection Diagnostic
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {/* Connection Status */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Connection Status
              </Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography>REST API</Typography>
                  <Chip
                    label={restApiStatus}
                    color={restApiStatus.includes('✅') ? 'success' : 'error'}
                    size="small"
                  />
                </Box>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography>WebSocket</Typography>
                  <Chip
                    icon={connected ? <CheckCircle /> : <Cancel />}
                    label={connected ? 'Connected' : 'Disconnected'}
                    color={connected ? 'success' : 'error'}
                    size="small"
                  />
                </Box>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography>Socket ID</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {socket?.id || 'N/A'}
                  </Typography>
                </Box>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography>Transport</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {socket?.io?.engine?.transport?.name || 'N/A'}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Current Data */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Current Data
              </Typography>
              <Box display="flex" flexDirection="column" gap={1}>
                <Typography variant="body2">
                  <strong>DI:</strong> {JSON.stringify(ioData.di)}
                </Typography>
                <Typography variant="body2">
                  <strong>DO:</strong> {JSON.stringify(ioData.do)}
                </Typography>
                <Typography variant="body2">
                  <strong>CPU:</strong> {systemData.cpu.toFixed(1)}%
                </Typography>
                <Typography variant="body2">
                  <strong>RAM:</strong> {systemData.ram.toFixed(1)}%
                </Typography>
                <Typography variant="body2">
                  <strong>Temp:</strong> {systemData.temp.toFixed(1)}°C
                </Typography>
                <Typography variant="body2">
                  <strong>Uptime:</strong> {systemData.uptime}s
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Test Buttons */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Connection Tests
            </Typography>
            <Box display="flex" gap={2} flexWrap="wrap">
              <Button
                variant="contained"
                startIcon={<Refresh />}
                onClick={testRestIO}
              >
                Test REST I/O
              </Button>
              <Button
                variant="contained"
                startIcon={<Refresh />}
                onClick={testRestSystem}
              >
                Test REST System
              </Button>
              <Button
                variant="contained"
                startIcon={<Refresh />}
                onClick={testWebSocketIO}
                disabled={!connected}
              >
                Test WS I/O
              </Button>
              <Button
                variant="contained"
                startIcon={<Refresh />}
                onClick={testWebSocketSystem}
                disabled={!connected}
              >
                Test WS System
              </Button>
              <Button
                variant="contained"
                color="warning"
                startIcon={<Refresh />}
                onClick={testToggleDO}
                disabled={!connected}
              >
                Test DO Toggle
              </Button>
            </Box>
          </Paper>
        </Grid>

        {/* Logs */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Diagnostic Logs
            </Typography>
            <Alert severity="info" sx={{ mb: 2 }}>
              Open browser console (F12) for detailed WebSocket logs
            </Alert>
            <Box
              sx={{
                height: 300,
                overflowY: 'auto',
                bgcolor: 'grey.900',
                p: 2,
                borderRadius: 1,
                fontFamily: 'monospace',
                fontSize: 12
              }}
            >
              {logs.length === 0 ? (
                <Typography color="grey.500">No logs yet...</Typography>
              ) : (
                logs.map((log, idx) => (
                  <Box
                    key={idx}
                    sx={{
                      color: log.type === 'error' ? 'error.main' : 
                             log.type === 'success' ? 'success.main' : 'grey.300',
                      mb: 0.5
                    }}
                  >
                    [{log.timestamp}] {log.message}
                  </Box>
                ))
              )}
            </Box>
          </Paper>
        </Grid>

        {/* Instructions */}
        <Grid item xs={12}>
          <Alert severity="warning">
            <Typography variant="subtitle2" gutterBottom>
              If WebSocket is not connecting:
            </Typography>
            <ol style={{ marginLeft: 20, marginTop: 8 }}>
              <li>Check Flask backend is running: <code>python3 api/app.py</code></li>
              <li>Verify backend shows: "🚀 EFIO API Server with WebSocket"</li>
              <li>Check port 5000 is open: <code>sudo lsof -i :5000</code></li>
              <li>Check browser console (F12) for error messages</li>
              <li>Try disabling firewall: <code>sudo ufw disable</code></li>
            </ol>
          </Alert>
        </Grid>
      </Grid>
    </Box>
  );
}