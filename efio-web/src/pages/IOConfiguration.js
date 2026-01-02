// src/pages/IOConfiguration.js
// I/O channel configuration (naming, debounce, etc.)

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  Alert,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Slider
} from '@mui/material';
import { Save, Refresh } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import apiConfig from '../config/apiConfig';

export default function IOConfiguration() {
  const { getAuthHeader } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [config, setConfig] = useState({
    di: [
      { channel: 0, name: 'DI1', debounce_ms: 10, enabled: true },
      { channel: 1, name: 'DI2', debounce_ms: 10, enabled: true },
      { channel: 2, name: 'DI3', debounce_ms: 10, enabled: true },
      { channel: 3, name: 'DI4', debounce_ms: 10, enabled: true }
    ],
    do: [
      { channel: 0, name: 'DO1', enabled: true, inverted: false },
      { channel: 1, name: 'DO2', enabled: true, inverted: false },
      { channel: 2, name: 'DO3', enabled: true, inverted: false },
      { channel: 3, name: 'DO4', enabled: true, inverted: false }
    ]
  });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/config/io`, {
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
    setSaving(true);
    setMessage(null);

    try {
      const response = await fetch(`${apiConfig.baseUrl}/api/config/io`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader()
        },
        body: JSON.stringify(config)
      });

      const data = await response.json();

      if (response.ok) {
        setMessage({ type: 'success', text: 'I/O configuration saved successfully' });
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to save configuration' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    } finally {
      setSaving(false);
    }
  };

  const updateDI = (index, field, value) => {
    const newDI = [...config.di];
    newDI[index] = { ...newDI[index], [field]: value };
    setConfig({ ...config, di: newDI });
  };

  const updateDO = (index, field, value) => {
    const newDO = [...config.do];
    newDO[index] = { ...newDO[index], [field]: value };
    setConfig({ ...config, do: newDO });
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
        I/O Configuration
      </Typography>

      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Digital Inputs Configuration */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom color="primary">
              Digital Inputs
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 2 }}>
              Configure channel names and debounce settings
            </Typography>

            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Channel</TableCell>
                    <TableCell>Name</TableCell>
                    <TableCell>Debounce (ms)</TableCell>
                    <TableCell>Enabled</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {config.di.map((input, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <Typography variant="body1" fontWeight="bold">
                          DI{index + 1}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          value={input.name}
                          onChange={(e) => updateDI(index, 'name', e.target.value)}
                          placeholder={`Digital Input ${index + 1}`}
                          sx={{ minWidth: 200 }}
                        />
                      </TableCell>
                      <TableCell>
                        <Box sx={{ width: 200, display: 'flex', alignItems: 'center', gap: 2 }}>
                          <Slider
                            value={input.debounce_ms}
                            onChange={(e, val) => updateDI(index, 'debounce_ms', val)}
                            min={0}
                            max={100}
                            valueLabelDisplay="auto"
                            sx={{ flexGrow: 1 }}
                          />
                          <Typography variant="body2" sx={{ minWidth: 40 }}>
                            {input.debounce_ms} ms
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={input.enabled}
                          onChange={(e) => updateDI(index, 'enabled', e.target.checked)}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <Alert severity="info" sx={{ mt: 2 }}>
              <strong>Debounce:</strong> Time delay to filter mechanical switch noise. 
              Increase if switches trigger multiple times on single press.
            </Alert>
          </Paper>
        </Grid>

        {/* Digital Outputs Configuration */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom color="warning.main">
              Digital Outputs
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mb: 2 }}>
              Configure channel names and output behavior
            </Typography>

            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Channel</TableCell>
                    <TableCell>Name</TableCell>
                    <TableCell>Inverted</TableCell>
                    <TableCell>Enabled</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {config.do.map((output, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <Typography variant="body1" fontWeight="bold">
                          DO{index + 1}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          value={output.name}
                          onChange={(e) => updateDO(index, 'name', e.target.value)}
                          placeholder={`Digital Output ${index + 1}`}
                          sx={{ minWidth: 200 }}
                        />
                      </TableCell>
                      <TableCell>
                        <FormControlLabel
                          control={
                            <Switch
                              checked={output.inverted}
                              onChange={(e) => updateDO(index, 'inverted', e.target.checked)}
                            />
                          }
                          label={output.inverted ? 'ON=Open' : 'ON=Closed'}
                        />
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={output.enabled}
                          onChange={(e) => updateDO(index, 'enabled', e.target.checked)}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <Alert severity="info" sx={{ mt: 2 }}>
              <strong>Inverted:</strong> Reverses output logic. Use when controlling normally-closed relays or inverted logic devices.
            </Alert>
          </Paper>
        </Grid>

        {/* Actions */}
        <Grid item xs={12}>
          <Box display="flex" gap={2}>
            <Button
              variant="contained"
              startIcon={saving ? <CircularProgress size={20} /> : <Save />}
              onClick={handleSave}
              disabled={saving}
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
        </Grid>
      </Grid>
    </Box>
  );
}