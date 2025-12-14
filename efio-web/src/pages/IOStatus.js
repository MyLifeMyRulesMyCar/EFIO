// src/pages/IOStatus.js
// I/O Control and Status Page

import React from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Alert
} from '@mui/material';
import useEFIOWebSocket from '../hooks/useEFIOWebSocket';
import IOCard from '../components/IOCard';

export default function IOStatus() {
  const { connected, ioData, toggleDO } = useEFIOWebSocket();

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom fontWeight="bold">
        I/O Control & Status
      </Typography>

      {!connected && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          ⚠️ WebSocket disconnected. I/O control disabled.
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Digital Inputs */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h5" gutterBottom color="primary">
              Digital Inputs (Read-Only)
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              24VDC inputs with 2,500V isolation
            </Typography>
            
            <Grid container spacing={2}>
              {ioData.di.map((value, idx) => (
                <Grid item xs={12} sm={6} key={idx}>
                  <IOCard
                    channel={idx}
                    value={value}
                    type="DI"
                  />
                </Grid>
              ))}
            </Grid>
          </Paper>
        </Grid>

        {/* Digital Outputs */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h5" gutterBottom color="warning.main">
              Digital Outputs (Control)
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              5A @ 250VAC relay outputs with 4,000V isolation
            </Typography>
            
            <Grid container spacing={2}>
              {ioData.do.map((value, idx) => (
                <Grid item xs={12} sm={6} key={idx}>
                  <IOCard
                    channel={idx}
                    value={value}
                    type="DO"
                    onToggle={toggleDO}
                  />
                </Grid>
              ))}
            </Grid>
          </Paper>
        </Grid>
      </Grid>

      {/* Additional Info */}
      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="h6" gutterBottom>
          I/O Specifications
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" color="primary">
              Digital Inputs (DI)
            </Typography>
            <Typography variant="body2" color="text.secondary">
              • Voltage Range: 15-30VDC (24V nominal)
            </Typography>
            <Typography variant="body2" color="text.secondary">
              • Input Impedance: 6kΩ (4mA @ 24V)
            </Typography>
            <Typography variant="body2" color="text.secondary">
              • Response Time: &lt;3ms
            </Typography>
            <Typography variant="body2" color="text.secondary">
              • Protection: Reverse polarity, overvoltage (TVS)
            </Typography>
          </Grid>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" color="warning.main">
              Digital Outputs (DO)
            </Typography>
            <Typography variant="body2" color="text.secondary">
              • Contact Rating: 5A @ 250VAC / 30VDC
            </Typography>
            <Typography variant="body2" color="text.secondary">
              • Response Time: ~10ms (relay actuation)
            </Typography>
            <Typography variant="body2" color="text.secondary">
              • Mechanical Life: 10 million operations
            </Typography>
            <Typography variant="body2" color="text.secondary">
              • Electrical Life: 100,000 ops @ rated load
            </Typography>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
}