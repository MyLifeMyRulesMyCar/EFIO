// src/components/Header.js
// Top app bar with connection status

import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Chip,
  Box
} from '@mui/material';
import {
  CheckCircle,
  Cancel,
  WifiOff
} from '@mui/icons-material';

const drawerWidth = 240;

export default function Header({ connected, title, lastUpdate }) {
  const formatTime = (date) => {
    if (!date) return '';
    return date.toLocaleTimeString();
  };

  return (
    <AppBar
      position="fixed"
      sx={{
        width: `calc(100% - ${drawerWidth}px)`,
        ml: `${drawerWidth}px`,
        backgroundColor: 'white',
        color: 'text.primary',
        boxShadow: 1
      }}
    >
      <Toolbar>
        <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
          {title}
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          {lastUpdate && (
            <Typography variant="caption" color="text.secondary">
              Last update: {formatTime(lastUpdate)}
            </Typography>
          )}
          <Chip
            icon={connected ? <CheckCircle /> : <WifiOff />}
            label={connected ? 'Connected' : 'Disconnected'}
            color={connected ? 'success' : 'error'}
            size="small"
            variant="outlined"
          />
          <Typography variant="body2" color="text.secondary">
            192.168.5.103:5000
          </Typography>
        </Box>
      </Toolbar>
    </AppBar>
  );
}