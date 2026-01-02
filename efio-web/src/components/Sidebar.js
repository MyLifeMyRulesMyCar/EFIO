// src/components/Sidebar.js
// Sidebar navigation component with Material-UI

import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Divider,
  Box,
  Button
  
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  PowerSettingsNew,
  Assessment,
  Settings,
  BugReport,
  NetworkCheck,
  Tune,
  Logout,
  Backup,
  Wifi,
  Transform
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { SettingsInputComponent } from '@mui/icons-material'; 
const drawerWidth = 240;

// Add to menuItems array
const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'I/O Status', icon: <PowerSettingsNew />, path: '/io' },
  { text: 'System Metrics', icon: <Assessment />, path: '/metrics' },
  { text: 'Diagnostic', icon: <BugReport />, path: '/diagnostic' },
  { text: 'divider' },
  { text: 'Modbus Manager', icon: <SettingsInputComponent />, path: '/modbus' },
  { text: 'Modbus-MQTT Bridge', icon: <Transform />, path: '/modbus-mqtt-bridge' },
  { text: 'Backup & Restore', icon: <Backup />, path: '/backup', adminOnly: true },
  { text: 'divider' },  // ADD THIS DIVIDER
  { text: 'Network Config', icon: <NetworkCheck />, path: '/config/network', adminOnly: true },
  { text: 'I/O Config', icon: <Tune />, path: '/config/io' },
  { text: 'MQTT Settings', icon: <Wifi />, path: '/config/mqtt', adminOnly: true },  // ← ADD THIS
  { text: 'Settings', icon: <Settings />, path: '/settings' }
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: drawerWidth,
          boxSizing: 'border-box',
        },
      }}
    >
      <Toolbar>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 32,
              height: 32,
              borderRadius: 1,
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontWeight: 'bold',
              fontSize: 16
            }}
          >
            EF
          </Box>
          <Typography variant="h6" noWrap component="div">
            EdgeForce
          </Typography>
        </Box>
      </Toolbar>
      <Divider />
      <List>
        {menuItems.map((item, index) => {
          if (item.text === 'divider') {
            return <Divider key={`div-${index}`} sx={{ my: 1 }} />;
          }

          return (
            <ListItem key={item.text} disablePadding>
              <ListItemButton
                component={Link}
                to={item.path}
                selected={location.pathname === item.path}
                sx={{
                  '&.Mui-selected': {
                    backgroundColor: 'primary.light',
                    '&:hover': {
                      backgroundColor: 'primary.light',
                    },
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    color: location.pathname === item.path ? 'primary.main' : 'inherit',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText primary={item.text} />
              </ListItemButton>
            </ListItem>
          );
        })}
      </List>
      <Divider />
      <Box sx={{ p: 2, mt: 'auto' }}>
        <Typography variant="caption" color="text.secondary">
          EdgeForce-1000 v1.0.0
        </Typography>
        <br />
        <Typography variant="caption" color="text.secondary">
          192.168.5.103
        </Typography>
      </Box>
    </Drawer>
  );
}