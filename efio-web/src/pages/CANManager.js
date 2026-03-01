// efio-web/src/pages/CANManager.js
// UPDATED: Proper connect/disconnect state management with health monitoring

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Grid, Card, CardContent, Button, IconButton,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Select, MenuItem, FormControl, InputLabel,
  Chip, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Alert, Tabs, Tab, Switch, FormControlLabel, CircularProgress,
  List, ListItem, ListItemText, Divider, ToggleButton, ToggleButtonGroup,
  LinearProgress
} from '@mui/material';
import {
  Add, Edit, Delete, Link as LinkIcon, LinkOff, Refresh, Send as SendIcon,
  PlayArrow, Stop, Search, ReadMore, Create, BugReport, Visibility, VisibilityOff,
  FilterList, GetApp, DeleteSweep, Pause, FiberManualRecord, Settings,
  Warning, CheckCircle, Error as ErrorIcon, PowerSettingsNew
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import apiConfig from '../config/apiConfig';
import useEFIOWebSocket from '../hooks/useEFIOWebSocket';

// Supported bitrates for MCP2515 with 8MHz crystal
const SUPPORTED_BITRATES = [
  { value: 10000, label: '10 Kbps' },
  { value: 20000, label: '20 Kbps' },
  { value: 50000, label: '50 Kbps' },
  { value: 100000, label: '100 Kbps' },
  { value: 125000, label: '125 Kbps' },
  { value: 250000, label: '250 Kbps' },
  { value: 500000, label: '500 Kbps' },
  { value: 1000000, label: '1 Mbps' }
];

export default function CANManager() {
  const { socket } = useEFIOWebSocket();
  const { getAuthHeader, hasRole } = useAuth();
  
  // State management
  const [devices, setDevices] = useState([]);
  const [status, setStatus] = useState(null);
  const [health, setHealth] = useState(null);
  const [messages, setMessages] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  
  // Dialog states
  const [deviceDialog, setDeviceDialog] = useState(false);
  const [sendDialog, setSendDialog] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  
  // Sniffer controls
  const [sniffing, setSniffing] = useState(false);
  const [filterById, setFilterById] = useState('');
  const [filterDirection, setFilterDirection] = useState('ALL');
  const [displayFormat, setDisplayFormat] = useState('HEX');
  
  // Forms
  const [deviceForm, setDeviceForm] = useState({
    name: '', can_id: '', extended: false, enabled: true, 
    description: '', timeout_threshold: 30
  });
  
  const [sendForm, setSendForm] = useState({
    can_id: '', data: '', extended: false
  });

  // CAN Configuration states
  const [config, setConfig] = useState(null);
  const [saving, setSaving] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [detectedBitrate, setDetectedBitrate] = useState(null);
  const [activeNodes, setActiveNodes] = useState([]);

  // Connection state
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  // Add WebSocket listener for CAN messages
  useEffect(() => {
    if (!socket) return;
    
    const handleCanMessage = (message) => {
      console.log('CAN message via WebSocket:', message);
      
      setMessages(prev => {
        const updated = [message, ...prev];
        return updated.slice(0, 100);
      });
    };
    
    socket.on('can_message', handleCanMessage);
    
    return () => {
      socket.off('can_message', handleCanMessage);
    };
  }, [socket]);

  // Load data on mount
  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      loadStatus();
      loadHealth();
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Auto-refresh messages when sniffing
  useEffect(() => {
    if (sniffing && activeTab === 1) {
      const interval = setInterval(loadMessages, 500);
      return () => clearInterval(interval);
    }
  }, [sniffing, activeTab]);

  // ================================
  // Data Loading Functions
  // ================================

  const loadData = async () => {
    await Promise.all([
      loadDevices(), 
      loadStatus(), 
      loadHealth(),
      loadStatistics(), 
      loadConfig()
    ]);
    setLoading(false);
  };

  const loadDevices = async () => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/can/devices`, {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setDevices(data.devices || []);
      }
    } catch (error) {
      console.error('Error loading devices:', error);
    }
  };

  const loadStatus = async () => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/can/status`, {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      }
    } catch (error) {
      console.error('Error loading status:', error);
    }
  };

  const loadHealth = async () => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/can/health`, {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setHealth(data);
      }
    } catch (error) {
      console.error('Error loading health:', error);
    }
  };

  const loadMessages = async () => {
    try {
      let url = `${apiConfig.baseUrl}/api/can/messages?count=100`;
      if (filterById) url += `&filter_id=${filterById}`;
      if (filterDirection !== 'ALL') url += `&direction=${filterDirection}`;
      
      const response = await fetch(url, { headers: getAuthHeader() });
      if (response.ok) {
        const data = await response.json();
        setMessages(data.messages || []);
      }
    } catch (error) {
      console.error('Error loading messages:', error);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/can/statistics`, {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setStatistics(data);
      }
    } catch (error) {
      console.error('Error loading statistics:', error);
    }
  };

  const loadConfig = async () => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/can/config`, {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      }
    } catch (error) {
      console.error('Error loading CAN config:', error);
    }
  };

  // ================================
  // CAN Bus Control (Updated)
  // ================================

  const handleConnect = async () => {
    if (!hasRole('admin')) {
      setMessage({ type: 'error', text: 'Admin access required' });
      return;
    }

    setConnecting(true);
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/can/connect`, {
        method: 'POST',
        headers: getAuthHeader()
      });
      
      const data = await response.json();
      if (response.ok) {
        setMessage({ type: 'success', text: 'CAN bus connected successfully' });
        await loadData();
      } else {
        setMessage({ 
          type: 'error', 
          text: data.error || 'Connection failed. Check hardware and try again.' 
        });
      }
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: 'Network error. Please check connection and try again.' 
      });
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!hasRole('admin')) {
      setMessage({ type: 'error', text: 'Admin access required' });
      return;
    }

    setDisconnecting(true);
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/can/disconnect`, {
        method: 'POST',
        headers: getAuthHeader()
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: 'CAN bus disconnected' });
        await loadData();
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to disconnect' });
    } finally {
      setDisconnecting(false);
    }
  };

  // ================================
  // Configuration Management
  // ================================

  const handleSaveConfig = async () => {
    if (!hasRole('admin')) {
      setMessage({ type: 'error', text: 'Admin access required' });
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/can/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify(config)
      });

      if (response.ok) {
        setMessage({ 
          type: 'success', 
          text: 'Configuration saved. Reconnect CAN bus for changes to take effect.' 
        });
        await loadConfig();
      } else {
        const data = await response.json();
        setMessage({ type: 'error', text: data.error || 'Save failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    } finally {
      setSaving(false);
    }
  };

  const handleAutoDetectBitrate = async () => {
    setDetecting(true);
    setDetectedBitrate(null);
    setMessage({ 
      type: 'info', 
      text: 'Detecting bitrate... This may take up to 30 seconds.' 
    });

    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/can/detect-bitrate`, {
        method: 'POST',
        headers: getAuthHeader()
      });

      const data = await response.json();
      if (response.ok && data.detected) {
        setDetectedBitrate(data.bitrate);
        setMessage({ 
          type: 'success', 
          text: `Detected ${data.bitrate} bps (quality: ${data.quality.toFixed(1)})` 
        });
      } else {
        setMessage({ 
          type: 'warning', 
          text: 'No CAN traffic detected. Make sure bus is active.' 
        });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Detection failed' });
    } finally {
      setDetecting(false);
    }
  };

  const applyDetectedBitrate = () => {
    if (detectedBitrate && config) {
      setConfig({
        ...config,
        controller: { ...config.controller, bitrate: detectedBitrate }
      });
      setMessage({ 
        type: 'success', 
        text: 'Bitrate applied. Click Save to persist.' 
      });
    }
  };

  // ================================
  // Device Management
  // ================================

  const handleSaveDevice = async () => {
    const url = selectedDevice
      ? `${apiConfig.baseUrl}/api/can/devices/${selectedDevice.id}`
      : `${apiConfig.baseUrl}/api/can/devices`;
    
    const method = selectedDevice ? 'PUT' : 'POST';

    try {
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify({
          ...deviceForm,
          can_id: parseInt(deviceForm.can_id)
        })
      });

      if (response.ok) {
        setMessage({ 
          type: 'success', 
          text: selectedDevice ? 'Device updated' : 'Device created' 
        });
        setDeviceDialog(false);
        await loadDevices();
      } else {
        const data = await response.json();
        setMessage({ type: 'error', text: data.error });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  const handleDeleteDevice = async (deviceId) => {
    if (!window.confirm('Delete this device?')) return;

    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/can/devices/${deviceId}`, {
        method: 'DELETE',
        headers: getAuthHeader()
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Device deleted' });
        await loadDevices();
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  // ================================
  // Message Transmission
  // ================================

  const handleSendMessage = async () => {
    try {
      const dataBytes = sendForm.data
        .split(/[\s,]+/)
        .filter(b => b)
        .map(b => {
          const hex = b.startsWith('0x') ? b : `0x${b}`;
          return parseInt(hex, 16);
        });

      if (dataBytes.length === 0 || dataBytes.length > 8) {
        setMessage({ type: 'error', text: 'Data must be 1-8 bytes' });
        return;
      }

      const response = await fetch(`${apiConfig.baseUrl}/api/can/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify({
          can_id: parseInt(sendForm.can_id),
          data: dataBytes,
          extended: sendForm.extended
        })
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Message sent' });
        setSendDialog(false);
        await loadMessages();
      } else {
        const data = await response.json();
        setMessage({ type: 'error', text: data.error });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Invalid data format' });
    }
  };

  // ================================
  // Utility Functions
  // ================================

  const formatData = (data, format) => {
    if (format === 'HEX') {
      return data.map(b => `0x${b.toString(16).toUpperCase().padStart(2, '0')}`).join(' ');
    } else if (format === 'DEC') {
      return data.join(' ');
    } else {
      return data.map(b => (b >= 32 && b <= 126) ? String.fromCharCode(b) : '.').join('');
    }
  };

  const exportMessages = () => {
    const csv = [
      ['Timestamp', 'Direction', 'CAN ID', 'DLC', 'Data'].join(','),
      ...messages.map(m => [
        m.timestamp,
        m.direction,
        `0x${m.can_id.toString(16).toUpperCase()}`,
        m.dlc,
        formatData(m.data, 'HEX')
      ].join(','))
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `can_messages_${Date.now()}.csv`;
    a.click();
  };

  const getHealthIcon = (healthStatus) => {
    if (!healthStatus) return <FiberManualRecord sx={{ color: 'grey.500' }} />;
    
    switch (healthStatus) {
      case 'healthy':
        return <CheckCircle sx={{ color: 'success.main' }} />;
      case 'degraded':
        return <Warning sx={{ color: 'warning.main' }} />;
      case 'unhealthy':
        return <ErrorIcon sx={{ color: 'error.main' }} />;
      default:
        return <FiberManualRecord sx={{ color: 'grey.500' }} />;
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  // ================================
  // Render
  // ================================

  return (
    <Box sx={{ p: 3 }}>
      {/* Header with Connection Controls */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight="bold">CAN Bus Manager</Typography>
          {health && (
            <Box display="flex" alignItems="center" gap={1} mt={1}>
              {getHealthIcon(health.health)}
              <Typography variant="body2" color="text.secondary">
                System Health: {health.health || 'Unknown'}
              </Typography>
            </Box>
          )}
        </Box>
        <Box display="flex" gap={2}>
          {!status?.connected ? (
            <Button
              variant="contained"
              color="success"
              size="large"
              startIcon={connecting ? <CircularProgress size={20} color="inherit" /> : <PowerSettingsNew />}
              onClick={handleConnect}
              disabled={!hasRole('admin') || connecting}
            >
              {connecting ? 'Connecting...' : 'Connect CAN Bus'}
            </Button>
          ) : (
            <Button
              variant="contained"
              color="error"
              size="large"
              startIcon={disconnecting ? <CircularProgress size={20} color="inherit" /> : <PowerSettingsNew />}
              onClick={handleDisconnect}
              disabled={!hasRole('admin') || disconnecting}
            >
              {disconnecting ? 'Disconnecting...' : 'Disconnect'}
            </Button>
          )}
          <Button variant="outlined" startIcon={<Refresh />} onClick={loadData}>
            Refresh
          </Button>
        </Box>
      </Box>

      {/* Alert Messages */}
      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      {/* Hardware Disconnection Warning */}
      {health?.health === 'unhealthy' && health?.warnings?.some(w => w.includes('Hardware')) && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <Typography variant="body2" fontWeight="bold" gutterBottom>
            CAN Hardware Disconnected
          </Typography>
          <Typography variant="caption" display="block">
            {health.warnings.join('. ')}
          </Typography>
          <Typography variant="caption" display="block" sx={{ mt: 1 }}>
            Please check hardware connection and click "Connect CAN Bus" to retry.
          </Typography>
        </Alert>
      )}

      {/* Status Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Bus Status</Typography>
              <Box display="flex" alignItems="center" gap={1}>
                <FiberManualRecord 
                  sx={{ 
                    color: status?.connected ? 'success.main' : 'error.main',
                    fontSize: 20 
                  }} 
                />
                <Typography variant="body1" fontWeight="bold">
                  {status?.connected ? 'Connected' : 'Disconnected'}
                </Typography>
              </Box>
              {status?.connected && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  {status.bitrate.toLocaleString()} bps
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Messages</Typography>
              <Typography variant="h4" color="primary.main">
                {(status?.rx_total || 0) + (status?.tx_total || 0)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                RX: {status?.rx_total || 0} | TX: {status?.tx_total || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Devices</Typography>
              <Typography variant="h4" color="secondary.main">
                {devices.length}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Alive: {status?.alive_devices || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Errors</Typography>
              <Typography variant="h4" color="error.main">
                {status?.errors || 0}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Timeouts: {status?.device_timeouts || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* CAN Configuration Section */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <Settings />
            <Typography variant="h6">CAN Configuration</Typography>
          </Box>
          <Box display="flex" gap={1}>
            <Button
              variant="outlined"
              startIcon={detecting ? <CircularProgress size={18} /> : <Search />}
              onClick={handleAutoDetectBitrate}
              disabled={detecting || status?.connected}
            >
              {detecting ? 'Detecting...' : 'Auto-Detect Bitrate'}
            </Button>
            <Button
              variant="contained"
              startIcon={<Settings />}
              onClick={handleSaveConfig}
              disabled={saving || !hasRole('admin') || status?.connected}
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </Button>
          </Box>
        </Box>

        {status?.connected && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Disconnect CAN bus to modify configuration settings
          </Alert>
        )}

        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth disabled={status?.connected}>
              <InputLabel>CAN Bitrate</InputLabel>
              <Select
                value={config?.controller?.bitrate || 125000}
                label="CAN Bitrate"
                onChange={(e) => setConfig({
                  ...config,
                  controller: { ...config?.controller, bitrate: e.target.value }
                })}
              >
                {SUPPORTED_BITRATES.map((br) => (
                  <MenuItem key={br.value} value={br.value}>{br.label}</MenuItem>
                ))}
              </Select>
            </FormControl>

            {detectedBitrate && (
              <Alert severity="success" sx={{ mt: 2 }} action={
                <Button size="small" onClick={applyDetectedBitrate}>Apply</Button>
              }>
                Detected: {detectedBitrate.toLocaleString()} bps
              </Alert>
            )}
          </Grid>

          <Grid item xs={12} md={8}>
            <FormControlLabel
              control={
                <Switch
                  checked={config?.auto_connect || false}
                  onChange={(e) => setConfig({
                    ...config,
                    auto_connect: e.target.checked
                  })}
                  disabled={status?.connected}
                />
              }
              label="Auto-connect on startup"
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ mb: 2 }}>
        <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)}>
          <Tab label="Devices" />
          <Tab label="Message Sniffer" />
          <Tab label="Send Message" />
          <Tab label="Statistics" />
        </Tabs>
      </Paper>

      {/* Tab 0: Devices */}
      {activeTab === 0 && (
        <Paper sx={{ p: 2 }}>
          <Box display="flex" justifyContent="space-between" mb={2}>
            <Typography variant="h6">Configured Devices ({devices.length})</Typography>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setDeviceForm({ 
                  name: '', can_id: '', extended: false, enabled: true, 
                  description: '', timeout_threshold: 30 
                });
                setSelectedDevice(null);
                setDeviceDialog(true);
              }}
            >
              Add Device
            </Button>
          </Box>

          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Status</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>CAN ID</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>RX Count</TableCell>
                  <TableCell>Last Seen</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {devices.map((device) => (
                  <TableRow key={device.id} hover>
                    <TableCell>
                      <Chip
                        icon={device.alive ? <CheckCircle /> : <ErrorIcon />}
                        label={device.alive ? 'Alive' : 'Timeout'}
                        size="small"
                        color={device.alive ? 'success' : 'default'}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" fontWeight="bold">
                        {device.name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip 
                        label={`0x${device.can_id.toString(16).toUpperCase()}`} 
                        size="small" 
                        color="primary"
                      />
                    </TableCell>
                    <TableCell>
                      {device.extended ? 'Extended' : 'Standard'}
                    </TableCell>
                    <TableCell>{device.rx_count || 0}</TableCell>
                    <TableCell>
                      {device.last_seen 
                        ? new Date(device.last_seen).toLocaleTimeString()
                        : 'Never'}
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={() => {
                          setDeviceForm({
                            name: device.name,
                            can_id: device.can_id,
                            extended: device.extended,
                            enabled: device.enabled,
                            description: device.description || '',
                            timeout_threshold: device.timeout_threshold || 30
                          });
                          setSelectedDevice(device);
                          setDeviceDialog(true);
                        }}
                      >
                        <Edit />
                      </IconButton>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleDeleteDevice(device.id)}
                      >
                        <Delete />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Tab 1: Message Sniffer - Same as before */}
      {activeTab === 1 && (
        <Paper sx={{ p: 2 }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">
              Message Sniffer ({messages.length} messages)
            </Typography>
            <Box display="flex" gap={1}>
              <ToggleButtonGroup
                value={displayFormat}
                exclusive
                onChange={(e, val) => val && setDisplayFormat(val)}
                size="small"
              >
                <ToggleButton value="HEX">HEX</ToggleButton>
                <ToggleButton value="DEC">DEC</ToggleButton>
                <ToggleButton value="ASCII">ASCII</ToggleButton>
              </ToggleButtonGroup>
              
              <Button
                variant={sniffing ? 'outlined' : 'contained'}
                color={sniffing ? 'error' : 'success'}
                startIcon={sniffing ? <Pause /> : <Visibility />}
                onClick={() => {
                  setSniffing(!sniffing);
                  if (!sniffing) loadMessages();
                }}
                disabled={!status?.connected}
              >
                {sniffing ? 'Pause' : 'Start'}
              </Button>
              
              <Button
                variant="outlined"
                startIcon={<GetApp />}
                onClick={exportMessages}
                disabled={messages.length === 0}
              >
                Export
              </Button>
              
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteSweep />}
                onClick={() => setMessages([])}
              >
                Clear
              </Button>
            </Box>
          </Box>

          {!status?.connected && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Connect CAN bus to start receiving messages
            </Alert>
          )}

          <Box display="flex" gap={2} mb={2}>
            <TextField
              size="small"
              label="Filter by CAN ID"
              placeholder="0x123 or 291"
              value={filterById}
              onChange={(e) => setFilterById(e.target.value)}
              sx={{ width: 200 }}
            />
            
            <FormControl size="small" sx={{ width: 150 }}>
              <InputLabel>Direction</InputLabel>
              <Select
                value={filterDirection}
                label="Direction"
                onChange={(e) => setFilterDirection(e.target.value)}
              >
                <MenuItem value="ALL">All</MenuItem>
                <MenuItem value="RX">RX Only</MenuItem>
                <MenuItem value="TX">TX Only</MenuItem>
              </Select>
            </FormControl>
            
            <Button
              size="small"
              variant="outlined"
              startIcon={<FilterList />}
              onClick={loadMessages}
            >
              Apply Filters
            </Button>
          </Box>

          <TableContainer sx={{ maxHeight: 500 }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Time</TableCell>
                  <TableCell>Dir</TableCell>
                  <TableCell>CAN ID</TableCell>
                  <TableCell>DLC</TableCell>
                  <TableCell>Data</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {messages.slice().reverse().map((msg, idx) => (
                  <TableRow 
                    key={idx}
                    sx={{
                      bgcolor: msg.direction === 'TX' ? 'warning.light' : 'success.light',
                      '&:hover': { bgcolor: msg.direction === 'TX' ? 'warning.main' : 'success.main' }
                    }}
                  >
                    <TableCell>
                      <Typography variant="caption">
                        {new Date(msg.timestamp).toLocaleTimeString()}.
                        {new Date(msg.timestamp).getMilliseconds()}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip 
                        label={msg.direction} 
                        size="small" 
                        color={msg.direction === 'TX' ? 'warning' : 'success'}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" fontFamily="monospace">
                        0x{msg.can_id.toString(16).toUpperCase().padStart(3, '0')}
                      </Typography>
                    </TableCell>
                    <TableCell>{msg.dlc}</TableCell>
                    <TableCell>
                      <Typography variant="body2" fontFamily="monospace">
                        {formatData(msg.data, displayFormat)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {messages.length === 0 && (
            <Box sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary">
                No messages captured
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {sniffing ? 'Waiting for CAN traffic...' : 'Click "Start" to begin sniffing'}
              </Typography>
            </Box>
          )}
        </Paper>
      )}

      {/* Tab 2: Send Message */}
      {activeTab === 2 && (
        <Paper sx={{ p: 3, maxWidth: 600 }}>
          <Typography variant="h6" gutterBottom>Send CAN Message</Typography>
          
          {!status?.connected && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Connect CAN bus to send messages
            </Alert>
          )}
          
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="CAN ID"
                placeholder="246 or 0x0F6"
                value={sendForm.can_id}
                onChange={(e) => setSendForm({ ...sendForm, can_id: e.target.value })}
                helperText="Decimal or hexadecimal (0x prefix)"
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Data Bytes (up to 8)"
                placeholder="0x8E 0x87 0x32 0xFA 0x26 0x8E 0xBE 0x86"
                value={sendForm.data}
                onChange={(e) => setSendForm({ ...sendForm, data: e.target.value })}
                helperText="Space or comma separated hex values"
              />
            </Grid>
            
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={sendForm.extended}
                    onChange={(e) => setSendForm({ ...sendForm, extended: e.target.checked })}
                  />
                }
                label="Extended Frame (29-bit ID)"
              />
            </Grid>
            
            <Grid item xs={12}>
              <Button
                fullWidth
                variant="contained"
                size="large"
                startIcon={<SendIcon />}
                onClick={handleSendMessage}
                disabled={!status?.connected || !sendForm.can_id || !sendForm.data}
              >
                Send Message
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* Tab 3: Statistics */}
      {activeTab === 3 && statistics && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>Bus Statistics</Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                <Box display="flex" justifyContent="space-between">
                  <Typography>Total RX:</Typography>
                  <Typography fontWeight="bold">{statistics.bus.rx_total}</Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography>Total TX:</Typography>
                  <Typography fontWeight="bold">{statistics.bus.tx_total}</Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography>Errors:</Typography>
                  <Typography fontWeight="bold" color="error.main">
                    {statistics.bus.errors}
                  </Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography>Device Timeouts:</Typography>
                  <Typography fontWeight="bold">{statistics.bus.device_timeouts || 0}</Typography>
                </Box>
                {statistics.bus.uptime && (
                  <Box display="flex" justifyContent="space-between">
                    <Typography>Uptime:</Typography>
                    <Typography fontWeight="bold">
                      {Math.floor(statistics.bus.uptime / 60)}m {Math.floor(statistics.bus.uptime % 60)}s
                    </Typography>
                  </Box>
                )}
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>Device Statistics</Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                <Box display="flex" justifyContent="space-between">
                  <Typography>Total Devices:</Typography>
                  <Typography fontWeight="bold">{statistics.devices.total}</Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography>Active Devices:</Typography>
                  <Typography fontWeight="bold" color="success.main">
                    {statistics.devices.active}
                  </Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography>Total Device RX:</Typography>
                  <Typography fontWeight="bold">{statistics.devices.total_rx}</Typography>
                </Box>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Device Dialog */}
      <Dialog open={deviceDialog} onClose={() => setDeviceDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {selectedDevice ? 'Edit Device' : 'Add New Device'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Device Name"
                value={deviceForm.name}
                onChange={(e) => setDeviceForm({ ...deviceForm, name: e.target.value })}
                placeholder="e.g., Engine ECU"
              />
            </Grid>
            
            <Grid item xs={8}>
              <TextField
                fullWidth
                label="CAN ID"
                value={deviceForm.can_id}
                onChange={(e) => setDeviceForm({ ...deviceForm, can_id: e.target.value })}
                placeholder="246 or 0x0F6"
                helperText="Decimal or hex (0x prefix)"
              />
            </Grid>
            
            <Grid item xs={4}>
              <FormControlLabel
                control={
                  <Switch
                    checked={deviceForm.extended}
                    onChange={(e) => setDeviceForm({ ...deviceForm, extended: e.target.checked })}
                  />
                }
                label="Extended"
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={2}
                label="Description (optional)"
                value={deviceForm.description}
                onChange={(e) => setDeviceForm({ ...deviceForm, description: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                type="number"
                label="Timeout Threshold (seconds)"
                value={deviceForm.timeout_threshold}
                onChange={(e) => setDeviceForm({ 
                  ...deviceForm, 
                  timeout_threshold: parseInt(e.target.value) || 30 
                })}
                inputProps={{ min: 5, max: 300 }}
                helperText="Device timeout detection threshold"
              />
            </Grid>
            
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={deviceForm.enabled}
                    onChange={(e) => setDeviceForm({ ...deviceForm, enabled: e.target.checked })}
                  />
                }
                label="Enabled"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeviceDialog(false)}>Cancel</Button>
          <Button
            onClick={handleSaveDevice}
            variant="contained"
            disabled={!deviceForm.name || !deviceForm.can_id}
          >
            {selectedDevice ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}