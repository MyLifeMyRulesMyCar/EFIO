import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Switch,
  FormControlLabel,
  Alert,
  Chip,
  Grid,
  Card,
  CardContent,
  Tooltip,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Divider,
  CircularProgress
} from '@mui/material';
import apiConfig from '../config/apiConfig';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  BarChart as StatsIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon
} from '@mui/icons-material';

const CANMQTTBridge = () => {
  // State
  const [mappings, setMappings] = useState([]);
  const [status, setStatus] = useState({
    running: false,
    mqtt_connected: false,
    can_connected: false,
    mappings_count: 0,
    statistics: {},
    mapping_details: [] // ✅ ADDED: Initialize mapping_details
  });
  const [openDialog, setOpenDialog] = useState(false);
  const [editMapping, setEditMapping] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    can_id: '',
    topic: '',
    enabled: true,
    publish_on_change: true,
    min_interval_ms: 100,
    qos: 1
  });

  // Load data on mount
  useEffect(() => {
    loadMappings();
    loadStatus();
    
    // Refresh status every 5 seconds
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // ✅ ADDED: Debug logging to see what status contains
  useEffect(() => {
    if (status) {
      console.log('CAN-MQTT Bridge Status:', {
        running: status.running,
        statistics: status.statistics,
        mapping_details: status.mapping_details,
        mapping_details_count: status.mapping_details?.length || 0
      });
    }
  }, [status]);

  // ================================
  // API Helpers
  // ================================

  const getAuthHeaders = () => {
    const token = localStorage.getItem('access_token');
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    };
  };

  const apiRequest = async (url, options = {}) => {
    try {
      const fullUrl = url.startsWith('http') ? url : `${apiConfig.baseUrl}${url}`;
      const response = await fetch(fullUrl, {
        ...options,
        headers: {
          ...getAuthHeaders(),
          ...options.headers
        }
      });

      // Check if response is actually JSON
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        // Got HTML instead of JSON (probably 404 or server error)
        const text = await response.text();
        console.error('Non-JSON response:', text.substring(0, 200));
        throw new Error('API endpoint not found or server error');
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }

      return data;
    } catch (err) {
      console.error('API request failed:', err);
      throw err;
    }
  };

  // ================================
  // API Calls
  // ================================

  const loadMappings = async () => {
    try {
      const data = await apiRequest('/api/can-mqtt/mappings');
      setMappings(data.mappings || []);
    } catch (err) {
      console.error('Failed to load mappings:', err);
      setError('Failed to load mappings');
    }
  };

  const loadStatus = async () => {
    try {
      const data = await apiRequest('/api/can-mqtt/status');
      console.log('Status loaded:', data); // ✅ ADDED: Debug log
      setStatus(data);
    } catch (err) {
      console.error('Failed to load status:', err);
    }
  };

  // ✅ MODIFIED: Enhanced error handling
  const startBridge = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiRequest('/api/can-mqtt/start', { method: 'POST' });
      setSuccess('Bridge started successfully');
      await loadStatus();
    } catch (err) {
      // Enhanced error messages
      let errorMessage = err.message || 'Failed to start bridge';
      
      if (errorMessage.includes('MQTT')) {
        setError(
          <Box>
            <Typography variant="body2" fontWeight="bold">
              MQTT Configuration Issue
            </Typography>
            <Typography variant="caption" display="block">
              {errorMessage}
            </Typography>
            <Typography variant="caption" display="block" sx={{ mt: 1 }}>
              Go to Settings → MQTT Settings and enable MQTT publishing
            </Typography>
          </Box>
        );
      } else if (errorMessage.includes('CAN')) {
        setError(
          <Box>
            <Typography variant="body2" fontWeight="bold">
              CAN Connection Issue
            </Typography>
            <Typography variant="caption" display="block">
              {errorMessage}
            </Typography>
            <Typography variant="caption" display="block" sx={{ mt: 1 }}>
              Bridge may start but won't forward messages until CAN device is connected
            </Typography>
          </Box>
        );
      } else {
        setError(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  const stopBridge = async () => {
    setLoading(true);
    setError(null);
    try {
      await apiRequest('/api/can-mqtt/stop', { method: 'POST' });
      setSuccess('Bridge stopped');
      await loadStatus();
    } catch (err) {
      setError(err.message || 'Failed to stop bridge');
    } finally {
      setLoading(false);
    }
  };

  const saveMapping = async () => {
    setLoading(true);
    setError(null);

    try {
      // Validate CAN ID (hex or decimal)
      let canId;
      if (formData.can_id.startsWith('0x') || formData.can_id.startsWith('0X')) {
        canId = parseInt(formData.can_id, 16);
      } else {
        canId = parseInt(formData.can_id, 10);
      }

      if (isNaN(canId) || canId < 0 || canId > 0x1FFFFFFF) {
        setError('Invalid CAN ID (range: 0x000 - 0x1FFFFFFF)');
        setLoading(false);
        return;
      }

      const payload = {
        ...formData,
        can_id: canId,
        min_interval_ms: parseInt(formData.min_interval_ms) || 100,
        qos: parseInt(formData.qos) || 1
      };

      if (editMapping) {
        // Update existing mapping
        await apiRequest(`/api/can-mqtt/mappings/${editMapping.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });
        setSuccess('Mapping updated successfully');
      } else {
        // Create new mapping
        await apiRequest('/api/can-mqtt/mappings', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        setSuccess('Mapping added successfully');
      }

      await loadMappings();
      handleCloseDialog();
    } catch (err) {
      setError(err.message || 'Failed to save mapping');
    } finally {
      setLoading(false);
    }
  };

  const deleteMapping = async (mappingId) => {
    if (!window.confirm('Are you sure you want to delete this mapping?')) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await apiRequest(`/api/can-mqtt/mappings/${mappingId}`, {
        method: 'DELETE'
      });
      setSuccess('Mapping deleted');
      await loadMappings();
    } catch (err) {
      setError(err.message || 'Failed to delete mapping');
    } finally {
      setLoading(false);
    }
  };

  // ================================
  // Dialog Handlers
  // ================================

  const handleOpenDialog = (mapping = null) => {
    if (mapping) {
      // Edit mode
      setEditMapping(mapping);
      setFormData({
        name: mapping.name,
        can_id: `0x${mapping.can_id.toString(16).toUpperCase().padStart(3, '0')}`,
        topic: mapping.topic,
        enabled: mapping.enabled,
        publish_on_change: mapping.publish_on_change ?? true,
        min_interval_ms: mapping.min_interval_ms || 100,
        qos: mapping.qos || 1
      });
    } else {
      // Add mode
      setEditMapping(null);
      setFormData({
        name: '',
        can_id: '',
        topic: '',
        enabled: true,
        publish_on_change: true,
        min_interval_ms: 100,
        qos: 1
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditMapping(null);
    setError(null);
  };

  const handleFormChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // ================================
  // Helper Functions
  // ================================

  const formatCANId = (canId) => {
    return `0x${canId.toString(16).toUpperCase().padStart(3, '0')}`;
  };

  const getStatusColor = (connected) => {
    return connected ? 'success' : 'error';
  };

  const getStatusIcon = (connected) => {
    return connected ? <CheckCircleIcon /> : <ErrorIcon />;
  };

  // ✅ ADDED: Helper function to get mapping statistics
  const getMappingStats = (mappingId) => {
    // First try to find in mapping_details array
    const detail = status.mapping_details?.find(d => d.id === mappingId);
    if (detail) {
      return {
        messages_received: detail.messages_received || detail.message_count || 0,
        messages_published: detail.messages_published || detail.message_count || 0,
        last_seen: detail.last_seen,
        last_publish: detail.last_publish
      };
    }
    
    // Fallback to old statistics object (backwards compatibility)
    const stats = status.statistics?.[mappingId] || {};
    return {
      messages_received: stats.messages_received || 0,
      messages_published: stats.messages_published || 0,
      last_seen: stats.last_seen,
      last_publish: stats.last_publish
    };
  };

  // ✅ ADDED: Helper to format last publish time
  const formatLastPublish = (lastPublish) => {
    if (!lastPublish) return null;
    
    // Check if it's a Unix timestamp (number) or ISO string
    const timestamp = typeof lastPublish === 'number' 
      ? lastPublish * 1000  // Convert seconds to milliseconds
      : lastPublish;
    
    const date = new Date(timestamp);
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);
    
    if (diffSec < 60) {
      return `${diffSec}s ago`;
    } else if (diffSec < 3600) {
      return `${Math.floor(diffSec / 60)}m ago`;
    } else {
      return date.toLocaleTimeString();
    }
  };

  // ================================
  // Render
  // ================================

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          CAN-MQTT Bridge
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Map CAN bus messages to MQTT topics for cloud integration and monitoring
        </Typography>
      </Box>

      {/* Alerts */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      {/* ✅ ADDED: Info alert when bridge running but no statistics */}
      {status.running && mappings.length > 0 && (
        !status.mapping_details || status.mapping_details.length === 0
      ) && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Bridge is running but no messages received yet. Ensure CAN bus has active traffic and mapping CAN IDs match actual messages.
        </Alert>
      )}

      {/* Status Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  Bridge Status
                </Typography>
                {getStatusIcon(status.running)}
              </Box>
              <Typography variant="h6" sx={{ mt: 1 }}>
                {status.running ? 'Running' : 'Stopped'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  MQTT Connection
                </Typography>
                {getStatusIcon(status.mqtt_connected)}
              </Box>
              <Typography variant="h6" sx={{ mt: 1 }}>
                {status.mqtt_connected ? 'Connected' : 'Disconnected'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  CAN Connection
                </Typography>
                {getStatusIcon(status.can_connected)}
              </Box>
              <Typography variant="h6" sx={{ mt: 1 }}>
                {status.can_connected ? 'Connected' : 'Disconnected'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  Active Mappings
                </Typography>
                <StatsIcon />
              </Box>
              <Typography variant="h6" sx={{ mt: 1 }}>
                {mappings.filter(m => m.enabled).length} / {mappings.length}
              </Typography>
              {/* ✅ ADDED: Show total published messages */}
              <Typography variant="caption" color="text.secondary">
                Published: {status.statistics?.messages_published || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Controls */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            color={status.running ? 'error' : 'success'}
            startIcon={status.running ? <StopIcon /> : <PlayIcon />}
            onClick={status.running ? stopBridge : startBridge}
            disabled={loading}
          >
            {status.running ? 'Stop Bridge' : 'Start Bridge'}
          </Button>

          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={() => handleOpenDialog()}
          >
            Add Mapping
          </Button>

          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadMappings}
          >
            Refresh
          </Button>

          {!status.can_connected && !status.running && (
            <Alert severity="info" sx={{ flexGrow: 1 }}>
              CAN device not detected. Bridge will still start but may not receive messages until device is connected.
            </Alert>
          )}

          {!status.mqtt_connected && status.running && (
            <Alert severity="warning" sx={{ flexGrow: 1 }}>
              MQTT not connected. Check MQTT settings.
            </Alert>
          )}
        </Box>
      </Paper>

      {/* Mappings Table */}
      <Paper>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Status</TableCell>
                <TableCell>Name</TableCell>
                <TableCell>CAN ID</TableCell>
                <TableCell>MQTT Topic</TableCell>
                <TableCell>Settings</TableCell>
                <TableCell>Statistics</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {mappings.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    <Box sx={{ py: 4 }}>
                      <Typography variant="body2" color="text.secondary">
                        No mappings configured. Click "Add Mapping" to create one.
                      </Typography>
                    </Box>
                  </TableCell>
                </TableRow>
              ) : (
                mappings.map((mapping) => {
                  // ✅ MODIFIED: Use new helper function instead of direct access
                  const stats = getMappingStats(mapping.id);
                  
                  return (
                    <TableRow key={mapping.id}>
                      <TableCell>
                        <Chip
                          label={mapping.enabled ? 'Enabled' : 'Disabled'}
                          color={mapping.enabled ? 'success' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {mapping.name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {formatCANId(mapping.can_id)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          (Dec: {mapping.can_id})
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {mapping.topic}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                          <Typography variant="caption">
                            Change: {mapping.publish_on_change ? 'Yes' : 'No'}
                          </Typography>
                          <Typography variant="caption">
                            Interval: {mapping.min_interval_ms}ms
                          </Typography>
                          <Typography variant="caption">
                            QoS: {mapping.qos}
                          </Typography>
                        </Box>
                      </TableCell>
                      {/* ✅ MODIFIED: Statistics cell with better handling */}
                      <TableCell>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                          {stats.messages_published > 0 ? (
                            <>
                              <Typography variant="caption">
                                Messages: {stats.messages_published}
                              </Typography>
                              {stats.last_publish && (
                                <Typography variant="caption" color="text.secondary">
                                  Last: {formatLastPublish(stats.last_publish)}
                                </Typography>
                              )}
                            </>
                          ) : (
                            <Typography variant="caption" color="text.secondary">
                              No activity
                            </Typography>
                          )}
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title="Edit">
                          <IconButton
                            size="small"
                            onClick={() => handleOpenDialog(mapping)}
                          >
                            <EditIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton
                            size="small"
                            onClick={() => deleteMapping(mapping.id)}
                            color="error"
                          >
                            <DeleteIcon />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Add/Edit Dialog */}
      <Dialog
        open={openDialog}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editMapping ? 'Edit Mapping' : 'Add New Mapping'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
            {/* Name */}
            <TextField
              label="Mapping Name"
              value={formData.name}
              onChange={(e) => handleFormChange('name', e.target.value)}
              placeholder="e.g., Engine ECU, Battery Monitor"
              required
              fullWidth
            />

            {/* CAN ID */}
            <TextField
              label="CAN ID"
              value={formData.can_id}
              onChange={(e) => handleFormChange('can_id', e.target.value)}
              placeholder="e.g., 0x0F6 or 246"
              helperText="Enter in hex (0x0F6) or decimal (246) format"
              required
              fullWidth
            />

            {/* MQTT Topic */}
            <TextField
              label="MQTT Topic"
              value={formData.topic}
              onChange={(e) => handleFormChange('topic', e.target.value)}
              placeholder="e.g., vehicle/engine/data"
              helperText="Topic where CAN data will be published"
              required
              fullWidth
            />

            <Divider />

            {/* Settings */}
            <Typography variant="subtitle2" color="text.secondary">
              Publishing Settings
            </Typography>

            <FormControlLabel
              control={
                <Switch
                  checked={formData.enabled}
                  onChange={(e) => handleFormChange('enabled', e.target.checked)}
                />
              }
              label="Enabled"
            />

            <FormControlLabel
              control={
                <Switch
                  checked={formData.publish_on_change}
                  onChange={(e) => handleFormChange('publish_on_change', e.target.checked)}
                />
              }
              label="Publish on Change Only"
            />

            <TextField
              label="Minimum Interval (ms)"
              type="number"
              value={formData.min_interval_ms}
              onChange={(e) => handleFormChange('min_interval_ms', e.target.value)}
              helperText="Minimum time between publishes (rate limiting)"
              fullWidth
            />

            <FormControl fullWidth>
              <InputLabel>MQTT QoS</InputLabel>
              <Select
                value={formData.qos}
                onChange={(e) => handleFormChange('qos', e.target.value)}
                label="MQTT QoS"
              >
                <MenuItem value={0}>0 - At most once</MenuItem>
                <MenuItem value={1}>1 - At least once</MenuItem>
                <MenuItem value={2}>2 - Exactly once</MenuItem>
              </Select>
            </FormControl>

            {/* Info Box */}
            <Alert severity="info">
              <Typography variant="caption">
                <strong>How it works:</strong><br />
                • CAN messages with ID {formData.can_id || '[CAN_ID]'} will be captured<br />
                • Data will be published to topic: {formData.topic || '[TOPIC]'}<br />
                • Message format: JSON with can_id, data (hex), dlc, timestamp
              </Typography>
            </Alert>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button
            onClick={saveMapping}
            variant="contained"
            disabled={loading || !formData.name || !formData.can_id || !formData.topic}
          >
            {loading ? <CircularProgress size={24} /> : (editMapping ? 'Update' : 'Add')}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default CANMQTTBridge;