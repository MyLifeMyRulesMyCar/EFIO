// src/pages/Metrics.js
// System Metrics and Health Monitoring Page

import React from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  LinearProgress,
  Paper,
  Chip,
  Alert
} from '@mui/material';
import {
  Memory,
  Storage,
  Thermostat,
  Speed,
  Computer,
  CheckCircle,
  Warning
} from '@mui/icons-material';
import useEFIOWebSocket from '../hooks/useEFIOWebSocket';

export default function Metrics() {
  const { connected, systemData } = useEFIOWebSocket();

  const formatUptime = (seconds) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${days}d ${hours}h ${minutes}m ${secs}s`;
  };

  const getHealthStatus = () => {
    if (systemData.cpu > 80 || systemData.ram > 85 || systemData.temp > 75) {
      return { severity: 'warning', label: 'Warning', icon: <Warning /> };
    }
    return { severity: 'success', label: 'Healthy', icon: <CheckCircle /> };
  };

  const health = getHealthStatus();

  const MetricDetailCard = ({ icon, title, value, percent, color, details }) => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" gap={1} mb={2}>
          {React.cloneElement(icon, { sx: { color: `${color}.main`, fontSize: 32 } })}
          <Box flexGrow={1}>
            <Typography variant="h6">{title}</Typography>
            <Typography variant="body2" color="text.secondary">
              {details}
            </Typography>
          </Box>
        </Box>

        <Typography variant="h3" sx={{ mb: 1 }}>
          {value}
        </Typography>

        {percent !== undefined && (
          <>
            <LinearProgress
              variant="determinate"
              value={percent}
              color={color}
              sx={{ height: 12, borderRadius: 2, mb: 1 }}
            />
            <Box display="flex" justifyContent="space-between">
              <Typography variant="caption" color="text.secondary">
                Usage: {percent.toFixed(1)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {percent > 80 ? '⚠️ High' : percent > 60 ? '📊 Moderate' : '✅ Normal'}
              </Typography>
            </Box>
          </>
        )}
      </CardContent>
    </Card>
  );

  return (
    <Box sx={{ p: 3 }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
        <Typography variant="h4" fontWeight="bold">
          System Metrics
        </Typography>
        <Chip
          icon={health.icon}
          label={`System ${health.label}`}
          color={health.severity}
          sx={{ fontSize: 16, py: 2, px: 1 }}
        />
      </Box>

      {!connected && (
        <Alert severity="error" sx={{ mb: 3 }}>
          ⚠️ No live data. WebSocket disconnected.
        </Alert>
      )}

      {/* Main Metrics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <MetricDetailCard
            icon={<Memory />}
            title="CPU Usage"
            value={`${systemData.cpu.toFixed(1)}%`}
            percent={systemData.cpu}
            color="primary"
            details="Rockchip RK3588 (8-core)"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <MetricDetailCard
            icon={<Storage />}
            title="Memory Usage"
            value={`${systemData.ram.toFixed(1)}%`}
            percent={systemData.ram}
            color="secondary"
            details="LPDDR4x 8GB RAM"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <MetricDetailCard
            icon={<Thermostat />}
            title="Temperature"
            value={`${systemData.temp.toFixed(1)}°C`}
            percent={(systemData.temp / 85) * 100}
            color={systemData.temp > 70 ? 'error' : 'success'}
            details="RK3588 Junction Temp"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <Speed sx={{ color: 'success.main', fontSize: 32 }} />
                <Box>
                  <Typography variant="h6">System Uptime</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Time since last boot
                  </Typography>
                </Box>
              </Box>
              <Typography variant="h4" sx={{ mb: 1 }}>
                {formatUptime(systemData.uptime)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* System Information */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom display="flex" alignItems="center" gap={1}>
          <Computer />
          System Information
        </Typography>
        
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Device Model
            </Typography>
            <Typography variant="body1" fontWeight="bold">
              EdgeForce-1000
            </Typography>
          </Grid>
          
          <Grid item xs={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Firmware Version
            </Typography>
            <Typography variant="body1" fontWeight="bold">
              v1.0.0
            </Typography>
          </Grid>
          
          <Grid item xs={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Operating System
            </Typography>
            <Typography variant="body1" fontWeight="bold">
              Ubuntu 22.04 LTS
            </Typography>
          </Grid>
          
          <Grid item xs={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              IP Address
            </Typography>
            <Typography variant="body1" fontWeight="bold">
              192.168.5.103
            </Typography>
          </Grid>

          <Grid item xs={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Processor
            </Typography>
            <Typography variant="body1" fontWeight="bold">
              RK3588 (8-core)
            </Typography>
          </Grid>
          
          <Grid item xs={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              RAM
            </Typography>
            <Typography variant="body1" fontWeight="bold">
              8GB LPDDR4x
            </Typography>
          </Grid>
          
          <Grid item xs={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              Storage
            </Typography>
            <Typography variant="body1" fontWeight="bold">
              64GB eMMC
            </Typography>
          </Grid>
          
          <Grid item xs={6} md={3}>
            <Typography variant="body2" color="text.secondary">
              I/O Channels
            </Typography>
            <Typography variant="body1" fontWeight="bold">
              4 DI / 4 DO
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Health Alerts */}
      <Box sx={{ mt: 3 }}>
        {systemData.temp > 75 && (
          <Alert severity="error" sx={{ mb: 2 }}>
            🔥 High temperature detected! Current: {systemData.temp.toFixed(1)}°C (Limit: 85°C)
          </Alert>
        )}
        {systemData.cpu > 80 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            ⚡ High CPU usage: {systemData.cpu.toFixed(1)}% - Consider reducing workload
          </Alert>
        )}
        {systemData.ram > 85 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            💾 High memory usage: {systemData.ram.toFixed(1)}% - System may slow down
          </Alert>
        )}
      </Box>
    </Box>
  );
}