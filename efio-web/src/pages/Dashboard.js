// src/pages/Dashboard.js
// Main dashboard page with overview cards

import React from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Paper,
  Alert
} from '@mui/material';
import {
  Memory,
  Storage,
  Thermostat,
  Speed,
  Circle
} from '@mui/icons-material';
import useEFIOWebSocket from '../hooks/useEFIOWebSocket';

export default function Dashboard() {
  const { connected, ioData, systemData } = useEFIOWebSocket();

  const formatUptime = (seconds) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${minutes}m`;
  };

  const MetricCard = ({ icon, title, value, unit, percent, color = 'primary' }) => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" gap={1} mb={2}>
          {icon}
          <Typography variant="h6">{title}</Typography>
        </Box>
        <Typography variant="h3" sx={{ mb: 1 }}>
          {value}{unit}
        </Typography>
        {percent !== undefined && (
          <LinearProgress
            variant="determinate"
            value={percent}
            color={color}
            sx={{ height: 8, borderRadius: 1 }}
          />
        )}
      </CardContent>
    </Card>
  );

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom fontWeight="bold">
        Dashboard Overview
      </Typography>
      
      {!connected && (
        <Alert severity="error" sx={{ mb: 3 }}>
          ⚠️ Disconnected from EFIO controller. Attempting to reconnect...
        </Alert>
      )}

      {/* System Metrics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <MetricCard
            icon={<Memory sx={{ color: 'primary.main' }} />}
            title="CPU Usage"
            value={systemData.cpu.toFixed(1)}
            unit="%"
            percent={systemData.cpu}
            color="primary"
          />
        </Grid>

        <Grid item xs={12} md={3}>
          <MetricCard
            icon={<Storage sx={{ color: 'secondary.main' }} />}
            title="Memory"
            value={systemData.ram.toFixed(1)}
            unit="%"
            percent={systemData.ram}
            color="secondary"
          />
        </Grid>

        <Grid item xs={12} md={3}>
          <MetricCard
            icon={<Thermostat sx={{ color: 'error.main' }} />}
            title="Temperature"
            value={systemData.temp.toFixed(1)}
            unit="°C"
            color="error"
          />
        </Grid>

        <Grid item xs={12} md={3}>
          <MetricCard
            icon={<Speed sx={{ color: 'success.main' }} />}
            title="Uptime"
            value={formatUptime(systemData.uptime)}
            unit=""
            color="success"
          />
        </Grid>
      </Grid>

      {/* I/O Status Overview */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Digital Inputs Status
            </Typography>
            <Box display="flex" gap={2} flexWrap="wrap" mt={2}>
              {ioData.di.map((value, idx) => (
                <Box
                  key={idx}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    p: 2,
                    border: 1,
                    borderColor: value ? 'success.main' : 'grey.300',
                    borderRadius: 2,
                    backgroundColor: value ? 'success.light' : 'grey.50',
                    minWidth: 100
                  }}
                >
                  <Circle
                    sx={{
                      fontSize: 20,
                      color: value ? 'success.main' : 'grey.400'
                    }}
                  />
                  <Box>
                    <Typography variant="body2" fontWeight="bold">
                      DI{idx + 1}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {value ? 'Active' : 'Inactive'}
                    </Typography>
                  </Box>
                </Box>
              ))}
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Digital Outputs Status
            </Typography>
            <Box display="flex" gap={2} flexWrap="wrap" mt={2}>
              {ioData.do.map((value, idx) => (
                <Box
                  key={idx}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    p: 2,
                    border: 1,
                    borderColor: value ? 'warning.main' : 'grey.300',
                    borderRadius: 2,
                    backgroundColor: value ? 'warning.light' : 'grey.50',
                    minWidth: 100
                  }}
                >
                  <Circle
                    sx={{
                      fontSize: 20,
                      color: value ? 'warning.main' : 'grey.400'
                    }}
                  />
                  <Box>
                    <Typography variant="body2" fontWeight="bold">
                      DO{idx + 1}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {value ? 'ON' : 'OFF'}
                    </Typography>
                  </Box>
                </Box>
              ))}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}