// src/pages/Diagnostic.js
// UPDATED: Shows component-level health status (GPIO, MQTT, Modbus)

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
  Divider,
  LinearProgress
} from '@mui/material';
import {
  Refresh,
  CheckCircle,
  Cancel,
  Warning,
  BugReport,
  Memory,
  Wifi,
  SettingsInputComponent
} from '@mui/icons-material';
import useEFIOWebSocket from '../hooks/useEFIOWebSocket';

export default function Diagnostic() {
  const { connected, ioData, systemData, socket } = useEFIOWebSocket();
  const [restApiStatus, setRestApiStatus] = useState('Checking...');
  const [logs, setLogs] = useState([]);
  const [healthStatus, setHealthStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev.slice(-20), { timestamp, message, type }]);
  };

  // Fetch health status every 3 seconds
  useEffect(() => {
    fetchHealthStatus();
    const interval = setInterval(fetchHealthStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchHealthStatus = async () => {
    try {
      // Fetch main detailed health
      const respMain = await fetch(`${apiConfig.baseUrl}/api/health/detailed`);
      const main = await respMain.json();

      // Fetch MQTT and Modbus endpoints (optional; backend may not include them in detailed)
      const [respMqtt, respModbus] = await Promise.allSettled([
        fetch(`${apiConfig.baseUrl}/api/health/mqtt`),
        fetch(`${apiConfig.baseUrl}/api/health/modbus`)
      ]);

      const components = {};

      if (respMqtt.status === 'fulfilled') {
        try {
          const mqttData = await respMqtt.value.json();
          components.mqtt = {
            status: mqttData.connected ? 'healthy' : 'unhealthy',
            message: mqttData.broker ? `${mqttData.broker}:${mqttData.port}` : 'MQTT status',
            last_update: mqttData.timestamp || null,
            details: mqttData
          };
        } catch (e) {
          // ignore
        }
      }

      if (respModbus.status === 'fulfilled') {
        try {
          const modbusData = await respModbus.value.json();
          components.modbus = {
            status: modbusData.count && modbusData.count > 0 ? 'healthy' : 'degraded',
            message: `${modbusData.count || 0} devices`,
            last_update: modbusData.timestamp || null,
            details: modbusData
          };
        } catch (e) {
          // ignore
        }
      }

      // Normalize the healthStatus expected by the UI
      setHealthStatus({
        ...main,
        components: {
          // keep any existing components in main if present
          ...(main.components || {}),
          ...components
        }
      });
      setLoading(false);
    } catch (error) {
      console.error('Health check failed:', error);
      setHealthStatus(null);
      setLoading(false);
    }
  };

  // Test REST API on mount
  useEffect(() => {
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
    if (!socket || !connected) {
      addLog('Socket not connected!', 'error');
      return;
    }
    addLog('Requesting I/O via WebSocket...', 'info');
    socket.emit('request_io');
  };

  const testWebSocketSystem = () => {
    if (!socket || !connected) {
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

  // Helper: Get status color
  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'degraded': return 'warning';
      case 'unhealthy': return 'error';
      default: return 'default';
    }
  };

  // Helper: Get status icon
  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircle />;
      case 'degraded': return <Warning />;
      case 'unhealthy': return <Cancel />;
      default: return <Cancel />;
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <BugReport sx={{ fontSize: 40 }} />
        <Typography variant="h4" fontWeight="bold">
          System Diagnostic
        </Typography>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={fetchHealthStatus}
          sx={{ ml: 'auto' }}
        >
          Refresh Health
        </Button>
      </Box>

      <Grid container spacing={3}>
        {/* Overall Health Status */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                <Typography variant="h6">Overall System Health</Typography>
                {loading ? (
                  <LinearProgress sx={{ width: 100 }} />
                ) : (
                  <Chip
                    icon={healthStatus ? getStatusIcon(healthStatus.status) : <Cancel />}
                    label={healthStatus ? healthStatus.status.toUpperCase() : 'UNKNOWN'}
                    color={healthStatus ? getStatusColor(healthStatus.status) : 'default'}
                    size="large"
                  />
                )}
              </Box>
              
              {healthStatus && healthStatus.system && (
                <Grid container spacing={2}>
                  <Grid item xs={3}>
                    <Typography variant="body2" color="text.secondary">CPU Usage</Typography>
                    <Typography variant="h6">{healthStatus.system.cpu_percent}%</Typography>
                  </Grid>
                  <Grid item xs={3}>
                    <Typography variant="body2" color="text.secondary">Memory</Typography>
                    <Typography variant="h6">{healthStatus.system.memory_percent}%</Typography>
                  </Grid>
                  <Grid item xs={3}>
                    <Typography variant="body2" color="text.secondary">Temperature</Typography>
                    <Typography variant="h6">{healthStatus.system.temperature_celsius}°C</Typography>
                  </Grid>
                  <Grid item xs={3}>
                    <Typography variant="body2" color="text.secondary">Uptime</Typography>
                    <Typography variant="h6">
                      {Math.floor(healthStatus.uptime / 3600)}h {Math.floor((healthStatus.uptime % 3600) / 60)}m
                    </Typography>
                  </Grid>
                </Grid>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Component Health Status */}
        {/* <Grid item xs={12}>
          <Typography variant="h6" gutterBottom>
            Component Health Status
          </Typography>
        </Grid>

        {/* GPIO Status 
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <Memory sx={{ fontSize: 32, color: 'primary.main' }} />
                <Typography variant="h6">GPIO (I/O)</Typography>
              </Box>
              
              {loading ? (
                <LinearProgress />
              ) : healthStatus?.components?.gpio ? (
                <>
                  <Chip
                    icon={getStatusIcon(healthStatus.components.gpio.status)}
                    label={healthStatus.components.gpio.status.toUpperCase()}
                    color={getStatusColor(healthStatus.components.gpio.status)}
                    size="small"
                    sx={{ mb: 1 }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    {healthStatus.components.gpio.message}
                  </Typography>
                  {healthStatus.components.gpio.last_update && (
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                      Last update: {new Date(healthStatus.components.gpio.last_update).toLocaleTimeString()}
                    </Typography>
                  )}
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No data available
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid> */}

        {/* MQTT Status */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <Wifi sx={{ fontSize: 32, color: 'secondary.main' }} />
                <Typography variant="h6">MQTT Broker</Typography>
              </Box>
              
              {loading ? (
                <LinearProgress />
              ) : healthStatus?.components?.mqtt ? (
                <>
                  <Chip
                    icon={getStatusIcon(healthStatus.components.mqtt.status)}
                    label={healthStatus.components.mqtt.status.toUpperCase()}
                    color={getStatusColor(healthStatus.components.mqtt.status)}
                    size="small"
                    sx={{ mb: 1 }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    {healthStatus.components.mqtt.message}
                  </Typography>
                  {healthStatus.components.mqtt.last_update && (
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                      Last update: {new Date(healthStatus.components.mqtt.last_update).toLocaleTimeString()}
                    </Typography>
                  )}
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No data available
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Modbus Status */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <SettingsInputComponent sx={{ fontSize: 32, color: 'success.main' }} />
                <Typography variant="h6">Modbus</Typography>
              </Box>
              
              {loading ? (
                <LinearProgress />
              ) : healthStatus?.components?.modbus ? (
                <>
                  <Chip
                    icon={getStatusIcon(healthStatus.components.modbus.status)}
                    label={healthStatus.components.modbus.status.toUpperCase()}
                    color={getStatusColor(healthStatus.components.modbus.status)}
                    size="small"
                    sx={{ mb: 1 }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    {healthStatus.components.modbus.message}
                  </Typography>
                  {healthStatus.components.modbus.last_update && (
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                      Last update: {new Date(healthStatus.components.modbus.last_update).toLocaleTimeString()}
                    </Typography>
                  )}
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No devices connected
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Connection Status (Original) */}
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
          <Alert severity="info">
            <Typography variant="subtitle2" gutterBottom>
              <strong>🧪 Testing I/O Resilience:</strong>
            </Typography>
            <ol style={{ marginLeft: 20, marginTop: 8 }}>
              <li>Watch the I/O and Connection cards above</li>
              <li>If you have physical I/O, toggle or disconnect to observe behavior</li>
              <li>The system may enter simulation mode automatically on hardware faults</li>
              <li>Recovery attempts run in background and will resume hardware when possible</li>
            </ol>
          </Alert>
        </Grid>
      </Grid>
    </Box>
  );
}