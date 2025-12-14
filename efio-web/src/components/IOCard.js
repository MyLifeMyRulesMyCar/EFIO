// src/components/IOCard.js
// Reusable card component for displaying I/O status

import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Switch,
  Chip
} from '@mui/material';
import { Circle, PowerSettingsNew } from '@mui/icons-material';

export default function IOCard({ 
  channel, 
  value, 
  type = 'DI', // 'DI' or 'DO'
  onToggle 
}) {
  const isInput = type === 'DI';
  const isActive = value === 1;

  return (
    <Card
      variant="outlined"
      sx={{
        backgroundColor: isActive 
          ? (isInput ? 'success.light' : 'warning.light') 
          : 'grey.50',
        transition: 'all 0.3s ease',
        border: isActive ? 2 : 1,
        borderColor: isActive 
          ? (isInput ? 'success.main' : 'warning.main') 
          : 'grey.300',
        '&:hover': {
          boxShadow: 2
        }
      }}
    >
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
          <Typography variant="h5" fontWeight="bold">
            {type}{channel + 1}
          </Typography>
          
          {isInput ? (
            <Circle
              sx={{
                fontSize: 40,
                color: isActive ? 'success.main' : 'grey.400',
                transition: 'color 0.3s'
              }}
            />
          ) : (
            <PowerSettingsNew
              sx={{
                fontSize: 40,
                color: isActive ? 'warning.main' : 'grey.400',
                transition: 'color 0.3s'
              }}
            />
          )}
        </Box>

        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Chip
            label={isActive ? (isInput ? 'ACTIVE' : 'ON') : (isInput ? 'INACTIVE' : 'OFF')}
            color={isActive ? (isInput ? 'success' : 'warning') : 'default'}
            size="small"
          />
          
          {!isInput && (
            <Switch
              checked={isActive}
              onChange={() => onToggle && onToggle(channel, !isActive)}
              color="warning"
            />
          )}
        </Box>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          {isInput 
            ? (isActive ? '24V Detected' : '0V (Ground)') 
            : (isActive ? 'Relay Closed' : 'Relay Open')}
        </Typography>
      </CardContent>
    </Card>
  );
}