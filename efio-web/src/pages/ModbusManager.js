// efio-web/src/pages/ModbusManager.js
// Modbus Device Manager UI - Clean Version

import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Grid, Card, CardContent, Button, IconButton,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Select, MenuItem, FormControl, InputLabel,
  Chip, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Alert, Tabs, Tab, Switch, FormControlLabel, CircularProgress,
  List, ListItem, ListItemText, Divider
} from '@mui/material';
import {
  Add, Edit, Delete, Link as LinkIcon, LinkOff, Refresh,
  PlayArrow, Stop, Search, ReadMore, Create, BugReport
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import apiConfig from '../config/apiConfig';

export default function ModbusManager() {
  const { getAuthHeader } = useAuth();
  const [devices, setDevices] = useState([]);
  const [ports, setPorts] = useState({});
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [openScanDialog, setOpenScanDialog] = useState(false);
  const [openTestDialog, setOpenTestDialog] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const [logs, setLogs] = useState([]);
  
  const [formData, setFormData] = useState({
    name: '', description: '', port: 'ttyS2', slave_id: 1,
    baudrate: 9600, parity: 'N', stopbits: 1, enabled: true
  });
  
  const [scanForm, setScanForm] = useState({
    port: 'ttyS2', start_id: 1, end_id: 10, baudrate: 9600
  });
  const [scanResults, setScanResults] = useState([]);
  const [scanning, setScanning] = useState(false);
  
  const [testForm, setTestForm] = useState({
    register: 0, count: 1, function_code: 3, value: 0
  });
  const [testResults, setTestResults] = useState(null);

  useEffect(() => {
    loadPorts();
    loadDevices();
    loadLogs();
    const interval = setInterval(loadDevices, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadPorts = async () => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/modbus/ports`, {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setPorts(data.ports);
      }
    } catch (error) {
      console.error('Error loading ports:', error);
    }
  };

  const loadDevices = async () => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/modbus/devices`, {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setDevices(data.devices);
      }
    } catch (error) {
      console.error('Error loading devices:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadLogs = async () => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/modbus/logs`, {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setLogs(data.logs.reverse());
      }
    } catch (error) {
      console.error('Error loading logs:', error);
    }
  };

  const handleSaveDevice = async () => {
    try {
      const url = selectedDevice
        ? `${apiConfig.baseUrl}/api/modbus/devices/${selectedDevice.id}`
        : `${apiConfig.baseUrl}/api/modbus/devices`;
      
      const response = await fetch(url, {
        method: selectedDevice ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify(formData)
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: selectedDevice ? 'Device updated' : 'Device created' });
        setOpenDialog(false);
        loadDevices();
      } else {
        const data = await response.json();
        setMessage({ type: 'error', text: data.error || 'Failed to save device' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  const handleDeleteDevice = async (deviceId) => {
    if (!window.confirm('Delete this device?')) return;
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/modbus/devices/${deviceId}`, {
        method: 'DELETE',
        headers: getAuthHeader()
      });
      if (response.ok) {
        setMessage({ type: 'success', text: 'Device deleted' });
        loadDevices();
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  const handleConnect = async (deviceId) => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/modbus/devices/${deviceId}/connect`, {
        method: 'POST',
        headers: getAuthHeader()
      });
      if (response.ok) {
        setMessage({ type: 'success', text: 'Connected' });
        loadDevices();
        loadLogs();
      } else {
        const data = await response.json();
        setMessage({ type: 'error', text: data.error || 'Connection failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  const handleDisconnect = async (deviceId) => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/modbus/devices/${deviceId}/disconnect`, {
        method: 'POST',
        headers: getAuthHeader()
      });
      if (response.ok) {
        setMessage({ type: 'success', text: 'Disconnected' });
        loadDevices();
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  const handleScan = async () => {
    setScanning(true);
    setScanResults([]);
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/modbus/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify(scanForm)
      });
      const data = await response.json();
      if (response.ok) {
        setScanResults(data.devices);
        setMessage({ type: 'success', text: `Found ${data.found} device(s)` });
      } else {
        setMessage({ type: 'error', text: data.error || 'Scan failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    } finally {
      setScanning(false);
    }
  };

  const handleTestRead = async () => {
    if (!selectedDevice?.connected) {
      setMessage({ type: 'error', text: 'Device not connected' });
      return;
    }
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/modbus/devices/${selectedDevice.id}/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify(testForm)
      });
      const data = await response.json();
      if (response.ok) {
        setTestResults(data.registers);
        setMessage({ type: 'success', text: 'Read successful' });
        loadLogs();
      } else {
        setMessage({ type: 'error', text: data.error || 'Read failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  const handleTestWrite = async () => {
    if (!selectedDevice?.connected) {
      setMessage({ type: 'error', text: 'Device not connected' });
      return;
    }
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/modbus/devices/${selectedDevice.id}/write`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify(testForm)
      });
      if (response.ok) {
        setMessage({ type: 'success', text: 'Write successful' });
        loadLogs();
      } else {
        const data = await response.json();
        setMessage({ type: 'error', text: data.error || 'Write failed' });
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
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" fontWeight="bold">Modbus Device Manager</Typography>
        <Box display="flex" gap={2}>
          <Button variant="outlined" startIcon={<Search />} onClick={() => setOpenScanDialog(true)}>
            Scan Devices
          </Button>
          <Button variant="contained" startIcon={<Add />} onClick={() => {
            setFormData({ name: '', description: '', port: 'ttyS2', slave_id: 1, baudrate: 9600, parity: 'N', stopbits: 1, enabled: true });
            setSelectedDevice(null);
            setOpenDialog(true);
          }}>
            Add Device
          </Button>
        </Box>
      </Box>

      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      <Tabs value={activeTab} onChange={(e, val) => setActiveTab(val)} sx={{ mb: 3 }}>
        <Tab label="Devices" />
        <Tab label="Communication Logs" />
      </Tabs>

      {activeTab === 0 && (
        <Grid container spacing={3}>
          {devices.length === 0 ? (
            <Grid item xs={12}>
              <Paper sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h6" color="text.secondary" gutterBottom>
                  No Modbus devices configured
                </Typography>
                <Button variant="contained" startIcon={<Add />} onClick={() => setOpenDialog(true)}>
                  Add First Device
                </Button>
              </Paper>
            </Grid>
          ) : (
            devices.map((device) => (
              <Grid item xs={12} md={6} lg={4} key={device.id}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" mb={2}>
                      <Box>
                        <Typography variant="h6">{device.name}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {device.description || 'No description'}
                        </Typography>
                      </Box>
                      <Chip
                        icon={device.connected ? <LinkIcon /> : <LinkOff />}
                        label={device.connected ? 'Connected' : 'Disconnected'}
                        color={device.connected ? 'success' : 'default'}
                        size="small"
                      />
                    </Box>

                    <Divider sx={{ my: 2 }} />

                    <Box display="flex" flexDirection="column" gap={1}>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body2" color="text.secondary">Port:</Typography>
                        <Typography variant="body2">{ports[device.port]?.name || device.port}</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body2" color="text.secondary">Slave ID:</Typography>
                        <Typography variant="body2">{device.slave_id}</Typography>
                      </Box>
                      <Box display="flex" justifyContent="space-between">
                        <Typography variant="body2" color="text.secondary">Baudrate:</Typography>
                        <Typography variant="body2">{device.baudrate}</Typography>
                      </Box>
                    </Box>

                    <Box display="flex" gap={1} mt={2}>
                      {!device.connected ? (
                        <Button size="small" variant="contained" startIcon={<LinkIcon />}
                          onClick={() => handleConnect(device.id)} fullWidth>
                          Connect
                        </Button>
                      ) : (
                        <>
                          <Button size="small" variant="outlined" startIcon={<LinkOff />}
                            onClick={() => handleDisconnect(device.id)}>
                            Disconnect
                          </Button>
                          <Button size="small" variant="outlined" startIcon={<BugReport />}
                            onClick={() => {
                              setSelectedDevice(device);
                              setOpenTestDialog(true);
                            }}>
                            Test
                          </Button>
                        </>
                      )}
                      <IconButton size="small" onClick={() => {
                        setFormData({ ...device });
                        setSelectedDevice(device);
                        setOpenDialog(true);
                      }}>
                        <Edit />
                      </IconButton>
                      <IconButton size="small" color="error" onClick={() => handleDeleteDevice(device.id)}>
                        <Delete />
                      </IconButton>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))
          )}
        </Grid>
      )}

      {activeTab === 1 && (
        <Paper sx={{ p: 2 }}>
          <Box display="flex" justifyContent="space-between" mb={2}>
            <Typography variant="h6">Communication Logs</Typography>
            <Button size="small" startIcon={<Refresh />} onClick={loadLogs}>Refresh</Button>
          </Box>
          <TableContainer sx={{ maxHeight: 600 }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Time</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Device</TableCell>
                  <TableCell>Message</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {logs.map((log, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Typography variant="caption">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </Typography>
                    </TableCell>
                    <TableCell><Chip label={log.type} size="small" /></TableCell>
                    <TableCell>{log.device_id}</TableCell>
                    <TableCell>{log.message}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Device Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>{selectedDevice ? 'Edit Device' : 'Add New Device'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField fullWidth label="Device Name" value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })} />
            </Grid>
            <Grid item xs={12}>
              <TextField fullWidth label="Description" multiline rows={2} value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel>Port</InputLabel>
                <Select value={formData.port} label="Port"
                  onChange={(e) => setFormData({ ...formData, port: e.target.value })}>
                  {Object.entries(ports).map(([key, port]) => (
                    <MenuItem key={key} value={key}>{port.name} ({key})</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <TextField fullWidth type="number" label="Slave ID" value={formData.slave_id}
                onChange={(e) => setFormData({ ...formData, slave_id: parseInt(e.target.value) })}
                inputProps={{ min: 1, max: 247 }} />
            </Grid>
            <Grid item xs={4}>
              <FormControl fullWidth>
                <InputLabel>Baudrate</InputLabel>
                <Select value={formData.baudrate} label="Baudrate"
                  onChange={(e) => setFormData({ ...formData, baudrate: parseInt(e.target.value) })}>
                  <MenuItem value={9600}>9600</MenuItem>
                  <MenuItem value={19200}>19200</MenuItem>
                  <MenuItem value={115200}>115200</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={4}>
              <FormControl fullWidth>
                <InputLabel>Parity</InputLabel>
                <Select value={formData.parity} label="Parity"
                  onChange={(e) => setFormData({ ...formData, parity: e.target.value })}>
                  <MenuItem value="N">None</MenuItem>
                  <MenuItem value="E">Even</MenuItem>
                  <MenuItem value="O">Odd</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={4}>
              <FormControl fullWidth>
                <InputLabel>Stop Bits</InputLabel>
                <Select value={formData.stopbits} label="Stop Bits"
                  onChange={(e) => setFormData({ ...formData, stopbits: parseInt(e.target.value) })}>
                  <MenuItem value={1}>1</MenuItem>
                  <MenuItem value={2}>2</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleSaveDevice} variant="contained">Save</Button>
        </DialogActions>
      </Dialog>

      {/* Scan Dialog */}
      <Dialog open={openScanDialog} onClose={() => setOpenScanDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Scan for Modbus Devices</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <Alert severity="info">
                Configure scan parameters to match your Modbus network settings
              </Alert>
            </Grid>
            
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Port</InputLabel>
                <Select value={scanForm.port} label="Port"
                  onChange={(e) => setScanForm({ ...scanForm, port: e.target.value })}>
                  {Object.entries(ports).map(([key, port]) => (
                    <MenuItem key={key} value={key}>{port.name} ({key})</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={6}>
              <TextField fullWidth type="number" label="Start Slave ID" value={scanForm.start_id}
                onChange={(e) => setScanForm({ ...scanForm, start_id: parseInt(e.target.value) })}
                inputProps={{ min: 1, max: 247 }} />
            </Grid>
            <Grid item xs={6}>
              <TextField fullWidth type="number" label="End Slave ID" value={scanForm.end_id}
                onChange={(e) => setScanForm({ ...scanForm, end_id: parseInt(e.target.value) })}
                inputProps={{ min: 1, max: 247 }} />
            </Grid>
            
            <Grid item xs={12}>
              <Divider><Chip label="Serial Parameters" size="small" /></Divider>
            </Grid>
            
            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel>Baudrate</InputLabel>
                <Select value={scanForm.baudrate} label="Baudrate"
                  onChange={(e) => setScanForm({ ...scanForm, baudrate: parseInt(e.target.value) })}>
                  <MenuItem value={4800}>4800 bps</MenuItem>
                  <MenuItem value={9600}>9600 bps (Most Common)</MenuItem>
                  <MenuItem value={19200}>19200 bps</MenuItem>
                  <MenuItem value={38400}>38400 bps</MenuItem>
                  <MenuItem value={57600}>57600 bps</MenuItem>
                  <MenuItem value={115200}>115200 bps</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel>Parity</InputLabel>
                <Select value={scanForm.parity} label="Parity"
                  onChange={(e) => setScanForm({ ...scanForm, parity: e.target.value })}>
                  <MenuItem value="N">None (Most Common)</MenuItem>
                  <MenuItem value="E">Even</MenuItem>
                  <MenuItem value="O">Odd</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel>Stop Bits</InputLabel>
                <Select value={scanForm.stopbits} label="Stop Bits"
                  onChange={(e) => setScanForm({ ...scanForm, stopbits: parseInt(e.target.value) })}>
                  <MenuItem value={1}>1 (Standard)</MenuItem>
                  <MenuItem value={2}>2</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel>Timeout</InputLabel>
                <Select value={scanForm.timeout} label="Timeout"
                  onChange={(e) => setScanForm({ ...scanForm, timeout: parseFloat(e.target.value) })}>
                  <MenuItem value={0.2}>0.2s (Fast)</MenuItem>
                  <MenuItem value={0.5}>0.5s (Normal)</MenuItem>
                  <MenuItem value={1.0}>1.0s (Slow/Reliable)</MenuItem>
                  <MenuItem value={2.0}>2.0s (Very Slow)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <Alert severity="warning" sx={{ mt: 1 }}>
                <Typography variant="caption" display="block" gutterBottom>
                  <strong>Tip:</strong> If unsure, try these common configurations:
                </Typography>
                <ul style={{ margin: 0, paddingLeft: 20, fontSize: '0.75rem' }}>
                  <li><strong>Standard Industrial:</strong> 9600 bps, None, 1 stop</li>
                  <li><strong>Energy Meters:</strong> 9600 bps, Even, 1 stop</li>
                  <li><strong>High Speed:</strong> 115200 bps, None, 1 stop</li>
                </ul>
              </Alert>
            </Grid>
            
            {scanning && (
              <Grid item xs={12}>
                <Box display="flex" alignItems="center" gap={2} sx={{ p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
                  <CircularProgress size={20} />
                  <Box>
                    <Typography variant="body2">Scanning Slave IDs {scanForm.start_id} to {scanForm.end_id}...</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {scanForm.baudrate} bps, Parity: {scanForm.parity}, Stop: {scanForm.stopbits}
                    </Typography>
                  </Box>
                </Box>
              </Grid>
            )}
            
            {scanResults.length > 0 && (
              <Grid item xs={12}>
                <Paper sx={{ p: 2, bgcolor: 'success.light' }}>
                  <Typography variant="subtitle2" gutterBottom fontWeight="bold">
                    ✅ Found {scanResults.length} Device(s):
                  </Typography>
                  <List dense>
                    {scanResults.map((result, index) => (
                      <ListItem key={index} sx={{ bgcolor: 'white', mb: 0.5, borderRadius: 1 }}>
                        <ListItemText
                          primary={
                            <Box display="flex" alignItems="center" gap={1}>
                              <Chip label={`Slave ID ${result.slave_id}`} size="small" color="success" />
                              <Typography variant="body2">{result.response}</Typography>
                            </Box>
                          }
                          secondary={`${result.baudrate} bps on ${result.port}`}
                        />
                      </ListItem>
                    ))}
                  </List>
                </Paper>
              </Grid>
            )}
            
            {!scanning && scanResults.length === 0 && scanForm.start_id > 0 && (
              <Grid item xs={12}>
                <Alert severity="info">
                  Ready to scan. Click "Start Scan" to begin searching for devices.
                </Alert>
              </Grid>
            )}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setOpenScanDialog(false);
            setScanResults([]);
          }}>Close</Button>
          <Button onClick={handleScan} variant="contained" disabled={scanning}
            startIcon={scanning ? <CircularProgress size={20} /> : <Search />}>
            {scanning ? 'Scanning...' : 'Start Scan'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Test Dialog */}
      <Dialog open={openTestDialog} onClose={() => setOpenTestDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Test Communication: {selectedDevice?.name}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <Alert severity="info">Test read/write operations with this device</Alert>
            </Grid>
            <Grid item xs={4}>
              <TextField fullWidth type="number" label="Register Address" value={testForm.register}
                onChange={(e) => setTestForm({ ...testForm, register: parseInt(e.target.value) })} />
            </Grid>
            <Grid item xs={4}>
              <TextField fullWidth type="number" label="Count" value={testForm.count}
                onChange={(e) => setTestForm({ ...testForm, count: parseInt(e.target.value) })}
                inputProps={{ min: 1, max: 125 }} />
            </Grid>
            <Grid item xs={4}>
              <FormControl fullWidth>
                <InputLabel>Function Code</InputLabel>
                <Select value={testForm.function_code} label="Function Code"
                  onChange={(e) => setTestForm({ ...testForm, function_code: parseInt(e.target.value) })}>
                  <MenuItem value={3}>FC3 - Read Holding</MenuItem>
                  <MenuItem value={4}>FC4 - Read Input</MenuItem>
                  <MenuItem value={6}>FC6 - Write Register</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            {testForm.function_code === 6 && (
              <Grid item xs={12}>
                <TextField fullWidth type="number" label="Value to Write" value={testForm.value}
                  onChange={(e) => setTestForm({ ...testForm, value: parseInt(e.target.value) })} />
              </Grid>
            )}
            <Grid item xs={12}>
              <Box display="flex" gap={2}>
                <Button variant="contained" startIcon={<ReadMore />} onClick={handleTestRead}
                  disabled={testForm.function_code > 4}>
                  Test Read
                </Button>
                <Button variant="contained" color="warning" startIcon={<Create />} onClick={handleTestWrite}
                  disabled={testForm.function_code < 5}>
                  Test Write
                </Button>
              </Box>
            </Grid>
            {testResults && (
              <Grid item xs={12}>
                <Paper sx={{ p: 2, bgcolor: 'grey.100' }}>
                  <Typography variant="subtitle2" gutterBottom>Read Results:</Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Register</TableCell>
                          <TableCell>Value</TableCell>
                          <TableCell>Hex</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {testResults.map((result, index) => (
                          <TableRow key={index}>
                            <TableCell>{result.register}</TableCell>
                            <TableCell>{result.value}</TableCell>
                            <TableCell>0x{result.value.toString(16).toUpperCase()}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              </Grid>
            )}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenTestDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}