// efio-web/src/pages/MQTTSettings.js
// MQTT Broker Configuration UI

import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Paper, Grid, TextField, Button, Switch,
  FormControlLabel, Alert, CircularProgress, Chip
} from '@mui/material';
import { Save, Refresh, CheckCircle, Cancel, BugReport } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

export default function MQTTSettings() {
  const { getAuthHeader, hasRole } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [config, setConfig] = useState({
    broker: 'localhost',
    port: 1883,
    username: '',
    password: '',
    client_id: 'efio-daemon',
    use_tls: false,
    keepalive: 60,
    qos: 1
  });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const response = await fetch('http://192.168.5.103:5000/api/config/mqtt', {
        headers: getAuthHeader()
      });
      
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      }
    } catch (error) {
      console.error('Error loading config:', error);
      setMessage({ type: 'error', text: 'Failed to load configuration' });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!hasRole('admin')) {
      setMessage({ type: 'error', text: 'Admin access required' });
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const response = await fetch('http://192.168.5.103:5000/api/config/mqtt', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader()
        },
        body: JSON.stringify(config)
      });

      const data = await response.json();

      if (response.ok) {
        setMessage({ 
          type: 'success', 
          text: 'MQTT configuration saved. Restart service for changes to take effect.' 
        });
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to save configuration' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    setMessage(null);

    try {
      const response = await fetch('http://192.168.5.103:5000/api/config/mqtt/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader()
        },
        body: JSON.stringify(config)
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setTestResult({ success: true, message: data.message });
        setMessage({ type: 'success', text: 'Connection test successful!' });
      } else {
        setTestResult({ success: false, message: data.error });
        setMessage({ type: 'error', text: data.error || 'Connection test failed' });
      }
    } catch (error) {
      setTestResult({ success: false, message: error.message });
      setMessage({ type: 'error', text: 'Test failed: ' + error.message });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom fontWeight="bold">
        MQTT Broker Configuration
      </Typography>

      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Connection Settings */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom color="primary">
              Broker Connection
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 2 }}>
              Configure MQTT broker for I/O state publishing
            </Typography>

            <Grid container spacing={2}>
              <Grid item xs={12} md={8}>
                <TextField
                  fullWidth
                  label="Broker Host"
                  value={config.broker}
                  onChange={(e) => setConfig({ ...config, broker: e.target.value })}
                  placeholder="localhost or broker.example.com"
                  helperText="MQTT broker hostname or IP address"
                />
              </Grid>

              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  label="Port"
                  type="number"
                  value={config.port}
                  onChange={(e) => setConfig({ ...config, port: parseInt(e.target.value) })}
                  helperText="Default: 1883"
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Username (optional)"
                  value={config.username}
                  onChange={(e) => setConfig({ ...config, username: e.target.value })}
                  helperText="Leave empty if no authentication"
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Password (optional)"
                  type="password"
                  value={config.password}
                  onChange={(e) => setConfig({ ...config, password: e.target.value })}
                  helperText="Leave empty if no authentication"
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Client ID"
                  value={config.client_id}
                  onChange={(e) => setConfig({ ...config, client_id: e.target.value })}
                  helperText="Unique identifier for this device"
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Keep-Alive (seconds)"
                  type="number"
                  value={config.keepalive}
                  onChange={(e) => setConfig({ ...config, keepalive: parseInt(e.target.value) })}
                  helperText="Connection keepalive interval"
                />
              </Grid>

              <Grid item xs={12}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={config.use_tls}
                      onChange={(e) => setConfig({ ...config, use_tls: e.target.checked })}
                    />
                  }
                  label="Use TLS/SSL encryption (port 8883)"
                />
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Status & Test */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, mb: 2 }}>
            <Typography variant="h6" gutterBottom>
              Connection Status
            </Typography>
            <Box display="flex" alignItems="center" gap={1} mb={2}>
              <Chip
                icon={<CheckCircle />}
                label="Connected"
                color="success"
                size="small"
              />
            </Box>
            <Typography variant="body2" color="text.secondary">
              Broker: {config.broker}:{config.port}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Client: {config.client_id}
            </Typography>
          </Paper>

          {testResult && (
            <Paper sx={{ p: 3, mb: 2, bgcolor: testResult.success ? 'success.light' : 'error.light' }}>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                {testResult.success ? (
                  <CheckCircle color="success" />
                ) : (
                  <Cancel color="error" />
                )}
                <Typography variant="subtitle2">
                  {testResult.success ? 'Test Passed' : 'Test Failed'}
                </Typography>
              </Box>
              <Typography variant="body2">
                {testResult.message}
              </Typography>
            </Paper>
          )}

          <Button
            fullWidth
            variant="outlined"
            startIcon={testing ? <CircularProgress size={20} /> : <BugReport />}
            onClick={handleTestConnection}
            disabled={testing || !hasRole('admin')}
            sx={{ mb: 2 }}
          >
            {testing ? 'Testing...' : 'Test Connection'}
          </Button>
        </Grid>

        {/* Topics Published */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Published Topics
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              EFIO publishes the following topics:
            </Typography>
            <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.900', borderRadius: 1, fontFamily: 'monospace', fontSize: 12 }}>
              <Typography sx={{ color: 'success.light', mb: 1 }}>
                edgeforce/io/di/1-4 → Digital Input states (0/1)
              </Typography>
              <Typography sx={{ color: 'warning.light', mb: 1 }}>
                edgeforce/io/do/1-4 → Digital Output states (0/1)
              </Typography>
              <Typography sx={{ color: 'info.light', mb: 1 }}>
                edgeforce/system/cpu → CPU usage (%)
              </Typography>
              <Typography sx={{ color: 'info.light', mb: 1 }}>
                edgeforce/system/ram → RAM usage (%)
              </Typography>
              <Typography sx={{ color: 'error.light' }}>
                edgeforce/system/temp → Temperature (°C)
              </Typography>
            </Box>
          </Paper>
        </Grid>

        {/* Actions */}
        <Grid item xs={12}>
          <Box display="flex" gap={2}>
            <Button
              variant="contained"
              startIcon={saving ? <CircularProgress size={20} /> : <Save />}
              onClick={handleSave}
              disabled={saving || !hasRole('admin')}
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </Button>
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={loadConfig}
              disabled={saving}
            >
              Reload
            </Button>
          </Box>
          {!hasRole('admin') && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              Admin access required to modify MQTT settings
            </Alert>
          )}
        </Grid>
      </Grid>
    </Box>
  );
}