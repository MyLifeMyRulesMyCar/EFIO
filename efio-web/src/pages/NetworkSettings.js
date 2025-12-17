// src/pages/NetworkSettings.js
// Network configuration page

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
  Radio,
  RadioGroup,
  Alert,
  CircularProgress,
  Divider
} from '@mui/material';
import { Save, Refresh, CheckCircle } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

export default function NetworkSettings() {
  const { getAuthHeader, hasRole } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [singleEthernet, setSingleEthernet] = useState(true); // Default to single ethernet
  const [config, setConfig] = useState({
    wan: {
      interface: 'eth0',
      mode: 'dhcp',
      ip: '192.168.5.103',
      netmask: '255.255.255.0',
      gateway: '192.168.5.1',
      dns1: '8.8.8.8',
      dns2: '8.8.4.4'
    },
    lan: {
      interface: 'eth1',
      mode: 'static',
      ip: '192.168.100.1',
      netmask: '255.255.255.0',
      dhcp_enabled: true,
      dhcp_start: '192.168.100.100',
      dhcp_end: '192.168.100.200',
      enabled: false // Disabled by default for single ethernet
    },
    hostname: 'edgeforce-1000'
  });

  useEffect(() => {
    loadConfig();
    checkEthernetPorts();
  }, []);

  const checkEthernetPorts = async () => {
    try {
      const response = await fetch('http://192.168.5.103:5000/api/config/system', {
        headers: getAuthHeader()
      });
      
      if (response.ok) {
        const data = await response.json();
        // Check if eth1 exists
        const hasEth1 = data.interfaces && 'eth1' in data.interfaces;
        setSingleEthernet(!hasEth1);
        
        if (!hasEth1) {
          setMessage({ 
            type: 'info', 
            text: 'Single Ethernet mode detected. Only WAN/Primary interface available.' 
          });
        }
      }
    } catch (error) {
      console.error('Error checking interfaces:', error);
    }
  };

  const loadConfig = async () => {
    try {
      const response = await fetch('http://192.168.5.103:5000/api/config/network', {
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
      const response = await fetch('http://192.168.5.103:5000/api/config/network', {
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
          text: 'Configuration saved successfully. Restart required for changes to take effect.' 
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
        Network Settings
      </Typography>

      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      {singleEthernet && (
        <Alert severity="info" sx={{ mb: 3 }}>
          <strong>Single Ethernet Mode:</strong> Your CM4 carrier board has one Ethernet port (eth0). 
          For dual ethernet features, use a board with both eth0 and eth1 interfaces.
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* WAN Configuration */}
        <Grid item xs={12} md={singleEthernet ? 12 : 6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom color="primary">
              {singleEthernet ? 'Primary Network (eth0)' : 'WAN Interface (eth0)'}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {singleEthernet 
                ? 'Main network connection' 
                : 'Connection to factory network / internet'}
            </Typography>

            {config.wan.current_ip && (
              <Alert severity="info" sx={{ my: 2 }}>
                Current IP: {config.wan.current_ip}
              </Alert>
            )}

            <RadioGroup
              value={config.wan.mode}
              onChange={(e) => setConfig({
                ...config,
                wan: { ...config.wan, mode: e.target.value }
              })}
              sx={{ mb: 2 }}
            >
              <FormControlLabel value="dhcp" control={<Radio />} label="DHCP (Automatic)" />
              <FormControlLabel value="static" control={<Radio />} label="Static IP" />
            </RadioGroup>

            {config.wan.mode === 'static' && (
              <>
                <TextField
                  fullWidth
                  label="IP Address"
                  value={config.wan.ip}
                  onChange={(e) => setConfig({
                    ...config,
                    wan: { ...config.wan, ip: e.target.value }
                  })}
                  margin="normal"
                />
                <TextField
                  fullWidth
                  label="Netmask"
                  value={config.wan.netmask}
                  onChange={(e) => setConfig({
                    ...config,
                    wan: { ...config.wan, netmask: e.target.value }
                  })}
                  margin="normal"
                />
                <TextField
                  fullWidth
                  label="Gateway"
                  value={config.wan.gateway}
                  onChange={(e) => setConfig({
                    ...config,
                    wan: { ...config.wan, gateway: e.target.value }
                  })}
                  margin="normal"
                />
              </>
            )}

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" gutterBottom>
              DNS Servers
            </Typography>
            <TextField
              fullWidth
              label="Primary DNS"
              value={config.wan.dns1}
              onChange={(e) => setConfig({
                ...config,
                wan: { ...config.wan, dns1: e.target.value }
              })}
              margin="normal"
            />
            <TextField
              fullWidth
              label="Secondary DNS"
              value={config.wan.dns2}
              onChange={(e) => setConfig({
                ...config,
                wan: { ...config.wan, dns2: e.target.value }
              })}
              margin="normal"
            />
          </Paper>
        </Grid>

        {/* LAN Configuration - Only show if dual ethernet */}
        {!singleEthernet && (
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom color="secondary">
                LAN Interface (eth1)
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Direct connection to HMI / configuration PC
              </Typography>

              {config.lan.current_ip && (
                <Alert severity="info" sx={{ my: 2 }}>
                  Current IP: {config.lan.current_ip}
                </Alert>
              )}

              <TextField
                fullWidth
                label="IP Address"
                value={config.lan.ip}
                onChange={(e) => setConfig({
                  ...config,
                  lan: { ...config.lan, ip: e.target.value }
                })}
                margin="normal"
              />
              <TextField
                fullWidth
                label="Netmask"
                value={config.lan.netmask}
                onChange={(e) => setConfig({
                  ...config,
                  lan: { ...config.lan, netmask: e.target.value }
                })}
                margin="normal"
              />

              <Divider sx={{ my: 2 }} />

              <FormControlLabel
                control={
                  <Switch
                    checked={config.lan.dhcp_enabled}
                    onChange={(e) => setConfig({
                      ...config,
                      lan: { ...config.lan, dhcp_enabled: e.target.checked }
                    })}
                  />
                }
                label="Enable DHCP Server"
              />

              {config.lan.dhcp_enabled && (
                <>
                  <TextField
                    fullWidth
                    label="DHCP Start"
                    value={config.lan.dhcp_start}
                    onChange={(e) => setConfig({
                      ...config,
                      lan: { ...config.lan, dhcp_start: e.target.value }
                    })}
                    margin="normal"
                  />
                  <TextField
                    fullWidth
                    label="DHCP End"
                    value={config.lan.dhcp_end}
                    onChange={(e) => setConfig({
                      ...config,
                      lan: { ...config.lan, dhcp_end: e.target.value }
                    })}
                    margin="normal"
                  />
                </>
              )}
            </Paper>
          </Grid>
        )}

        {/* Hostname */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Device Settings
            </Typography>
            <TextField
              label="Hostname"
              value={config.hostname}
              onChange={(e) => setConfig({ ...config, hostname: e.target.value })}
              sx={{ maxWidth: 400 }}
            />
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
              Admin access required to modify network settings
            </Alert>
          )}
        </Grid>
      </Grid>
    </Box>
  );
}