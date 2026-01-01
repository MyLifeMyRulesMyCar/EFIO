// efio-web/src/pages/ModbusMQTTBridge.js
// Modbus-MQTT Bridge Configuration UI

import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Grid, Card, CardContent, Button, IconButton,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Select, MenuItem, FormControl, InputLabel,
  Chip, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Alert, Switch, FormControlLabel, CircularProgress, Divider
} from '@mui/material';
import {
  Add, Edit, Delete, PlayArrow, Stop, Refresh, 
  CheckCircle, Cancel, Link as LinkIcon
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

export default function ModbusMQTTBridge() {
  const { getAuthHeader, hasRole } = useAuth();
  const [mappings, setMappings] = useState([]);
  const [availableDevices, setAvailableDevices] = useState([]);
  const [bridgeStatus, setBridgeStatus] = useState({
    running: false,
    mqtt_connected: false,
    mappings_count: 0,
    poll_interval: 1.0
  });
  const [openDialog, setOpenDialog] = useState(false);
  const [selectedMapping, setSelectedMapping] = useState(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [pollInterval, setPollInterval] = useState(1.0);

  const [formData, setFormData] = useState({
    device_id: '',
    device_name: '',
    register: 0,
    function_code: 3,
    topic: '',
    name: '',
    unit: '',
    enabled: true,
    scaling: {
      multiplier: 1.0,
      offset: 0.0,
      decimals: 0
    }
  });

  useEffect(() => {
    loadData();
    const interval = setInterval(loadStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    await Promise.all([
      loadMappings(),
      loadAvailableDevices(),
      loadStatus()
    ]);
    setLoading(false);
  };

  const loadMappings = async () => {
    try {
      const response = await fetch('http://192.168.5.103:5000/api/modbus-mqtt/mappings', {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setMappings(data.mappings || []);
      }
    } catch (error) {
      console.error('Error loading mappings:', error);
    }
  };

  const loadAvailableDevices = async () => {
    try {
      const response = await fetch('http://192.168.5.103:5000/api/modbus-mqtt/available-devices', {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setAvailableDevices(data.devices || []);
      }
    } catch (error) {
      console.error('Error loading devices:', error);
    }
  };

  const loadStatus = async () => {
    try {
      const response = await fetch('http://192.168.5.103:5000/api/modbus-mqtt/status', {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setBridgeStatus(data);
      }
    } catch (error) {
      console.error('Error loading status:', error);
    }
  };

  const handleSaveMapping = async () => {
    if (!hasRole('admin')) {
      setMessage({ type: 'error', text: 'Admin access required' });
      return;
    }

    try {
      // Add device name
      const device = availableDevices.find(d => d.id === formData.device_id);
      if (device) {
        formData.device_name = device.name;
      }

      const url = selectedMapping
        ? `http://192.168.5.103:5000/api/modbus-mqtt/mappings/${selectedMapping.id}`
        : 'http://192.168.5.103:5000/api/modbus-mqtt/mappings';

      const response = await fetch(url, {
        method: selectedMapping ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        setMessage({ 
          type: 'success', 
          text: selectedMapping ? 'Mapping updated' : 'Mapping created' 
        });
        setOpenDialog(false);
        loadMappings();
      } else {
        const data = await response.json();
        setMessage({ type: 'error', text: data.error || 'Failed to save mapping' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  const handleDeleteMapping = async (mappingId) => {
    if (!window.confirm('Delete this mapping?')) return;

    try {
      const response = await fetch(`http://192.168.5.103:5000/api/modbus-mqtt/mappings/${mappingId}`, {
        method: 'DELETE',
        headers: getAuthHeader()
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Mapping deleted' });
        loadMappings();
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  const handleStartBridge = async () => {
    try {
      const response = await fetch('http://192.168.5.103:5000/api/modbus-mqtt/start', {
        method: 'POST',
        headers: getAuthHeader()
      });

      const data = await response.json();

      if (response.ok) {
        setMessage({ type: 'success', text: 'Bridge started successfully' });
        loadStatus();
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to start bridge' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  const handleStopBridge = async () => {
    try {
      const response = await fetch('http://192.168.5.103:5000/api/modbus-mqtt/stop', {
        method: 'POST',
        headers: getAuthHeader()
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Bridge stopped' });
        loadStatus();
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
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
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" fontWeight="bold">Modbus-MQTT Bridge</Typography>
        <Box display="flex" gap={2}>
          {!bridgeStatus.running ? (
            <Button
              variant="contained"
              color="success"
              startIcon={<PlayArrow />}
              onClick={handleStartBridge}
              disabled={mappings.length === 0 || !hasRole('admin')}
            >
              Start Bridge
            </Button>
          ) : (
            <Button
              variant="contained"
              color="error"
              startIcon={<Stop />}
              onClick={handleStopBridge}
              disabled={!hasRole('admin')}
            >
              Stop Bridge
            </Button>
          )}
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={loadData}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => {
              setFormData({
                device_id: '',
                device_name: '',
                register: 0,
                function_code: 3,
                topic: '',
                name: '',
                unit: '',
                enabled: true,
                scaling: { multiplier: 1.0, offset: 0.0, decimals: 0 }
              });
              setSelectedMapping(null);
              setOpenDialog(true);
            }}
          >
            Add Mapping
          </Button>
        </Box>
      </Box>

      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      {/* Status Card */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Bridge Status</Typography>
              <Box display="flex" flexDirection="column" gap={1.5}>
                <Box display="flex" alignItems="center" gap={1}>
                  <Chip
                    icon={bridgeStatus.running ? <CheckCircle /> : <Cancel />}
                    label={bridgeStatus.running ? 'Running' : 'Stopped'}
                    color={bridgeStatus.running ? 'success' : 'default'}
                    size="small"
                  />
                  <Typography variant="body2" color="text.secondary">Service Status</Typography>
                </Box>
                <Box display="flex" alignItems="center" gap={1}>
                  <Chip
                    icon={bridgeStatus.mqtt_connected ? <LinkIcon /> : <Cancel />}
                    label={bridgeStatus.mqtt_connected ? 'Connected' : 'Disconnected'}
                    color={bridgeStatus.mqtt_connected ? 'success' : 'default'}
                    size="small"
                  />
                  <Typography variant="body2" color="text.secondary">MQTT Connection</Typography>
                </Box>
                <Divider />
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Active Mappings:</Typography>
                  <Typography variant="body2" fontWeight="bold">{bridgeStatus.mappings_count}</Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Poll Interval:</Typography>
                  <Typography variant="body2" fontWeight="bold">{bridgeStatus.poll_interval}s</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Available Devices</Typography>
              {availableDevices.length === 0 ? (
                <Alert severity="warning">
                  No connected Modbus devices. Connect devices in Modbus Manager first.
                </Alert>
              ) : (
                <Box display="flex" flexDirection="column" gap={1}>
                  {availableDevices.map((device) => (
                    <Box key={device.id} display="flex" alignItems="center" gap={1}>
                      <CheckCircle color="success" fontSize="small" />
                      <Typography variant="body2">{device.name}</Typography>
                      <Chip label={`ID: ${device.slave_id}`} size="small" />
                    </Box>
                  ))}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Mappings Table */}
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>Register-to-Topic Mappings ({mappings.length})</Typography>

        {mappings.length === 0 ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No mappings configured
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Add your first mapping to start publishing Modbus data to MQTT
            </Typography>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => setOpenDialog(true)}
              sx={{ mt: 2 }}
            >
              Add First Mapping
            </Button>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Device</TableCell>
                  <TableCell>Register</TableCell>
                  <TableCell>FC</TableCell>
                  <TableCell>MQTT Topic</TableCell>
                  <TableCell>Unit</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {mappings.map((mapping) => (
                  <TableRow key={mapping.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight="bold">
                        {mapping.name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {mapping.device_name || mapping.device_id}
                      </Typography>
                    </TableCell>
                    <TableCell>{mapping.register}</TableCell>
                    <TableCell>
                      <Chip 
                        label={`FC${mapping.function_code}`} 
                        size="small" 
                        color={mapping.function_code === 3 ? 'primary' : 'secondary'}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                        {mapping.topic}
                      </Typography>
                    </TableCell>
                    <TableCell>{mapping.unit || '-'}</TableCell>
                    <TableCell>
                      <Chip
                        label={mapping.enabled ? 'Enabled' : 'Disabled'}
                        size="small"
                        color={mapping.enabled ? 'success' : 'default'}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={() => {
                          setFormData({ ...mapping });
                          setSelectedMapping(mapping);
                          setOpenDialog(true);
                        }}
                      >
                        <Edit />
                      </IconButton>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleDeleteMapping(mapping.id)}
                      >
                        <Delete />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Add/Edit Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>{selectedMapping ? 'Edit Mapping' : 'Add New Mapping'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Modbus Device</InputLabel>
                <Select
                  value={formData.device_id}
                  label="Modbus Device"
                  onChange={(e) => setFormData({ ...formData, device_id: e.target.value })}
                >
                  {availableDevices.map((device) => (
                    <MenuItem key={device.id} value={device.id}>
                      {device.name} (Slave ID: {device.slave_id})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={6}>
              <TextField
                fullWidth
                type="number"
                label="Register Address"
                value={formData.register}
                onChange={(e) => setFormData({ ...formData, register: parseInt(e.target.value) })}
                inputProps={{ min: 0, max: 65535 }}
              />
            </Grid>

            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel>Function Code</InputLabel>
                <Select
                  value={formData.function_code}
                  label="Function Code"
                  onChange={(e) => setFormData({ ...formData, function_code: parseInt(e.target.value) })}
                >
                  <MenuItem value={3}>FC3 - Read Holding Registers</MenuItem>
                  <MenuItem value={4}>FC4 - Read Input Registers</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Mapping Name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Temperature Sensor 1"
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="MQTT Topic"
                value={formData.topic}
                onChange={(e) => setFormData({ ...formData, topic: e.target.value })}
                placeholder="e.g., H2Block/temp1 or factory/zone1/temperature"
                helperText="Topic where the value will be published"
              />
            </Grid>

            <Grid item xs={6}>
              <TextField
                fullWidth
                label="Unit (optional)"
                value={formData.unit}
                onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
                placeholder="e.g., °C, kW, m³/h"
              />
            </Grid>

            <Grid item xs={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.enabled}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  />
                }
                label="Enabled"
              />
            </Grid>

            <Grid item xs={12}>
              <Divider><Chip label="Scaling (optional)" size="small" /></Divider>
            </Grid>

            <Grid item xs={4}>
              <TextField
                fullWidth
                type="number"
                label="Multiplier"
                value={formData.scaling.multiplier}
                onChange={(e) => setFormData({
                  ...formData,
                  scaling: { ...formData.scaling, multiplier: parseFloat(e.target.value) }
                })}
                inputProps={{ step: 0.1 }}
              />
            </Grid>

            <Grid item xs={4}>
              <TextField
                fullWidth
                type="number"
                label="Offset"
                value={formData.scaling.offset}
                onChange={(e) => setFormData({
                  ...formData,
                  scaling: { ...formData.scaling, offset: parseFloat(e.target.value) }
                })}
                inputProps={{ step: 0.1 }}
              />
            </Grid>

            <Grid item xs={4}>
              <TextField
                fullWidth
                type="number"
                label="Decimals"
                value={formData.scaling.decimals}
                onChange={(e) => setFormData({
                  ...formData,
                  scaling: { ...formData.scaling, decimals: parseInt(e.target.value) }
                })}
                inputProps={{ min: 0, max: 4 }}
              />
            </Grid>

            <Grid item xs={12}>
              <Alert severity="info">
                Formula: (raw_value × multiplier) + offset, rounded to decimals
              </Alert>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleSaveMapping} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}