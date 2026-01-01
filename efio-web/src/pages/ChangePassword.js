// efio-web/src/pages/ChangePassword.js
// NEW: Force password change page

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Card, CardContent, TextField, Button, Typography,
  Alert, LinearProgress, InputAdornment, IconButton
} from '@mui/material';
import { Visibility, VisibilityOff, Lock } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

export default function ChangePassword({ forced = false }) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
    confirm: false
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { getAuthHeader, logout } = useAuth();
  const navigate = useNavigate();

  // Password strength calculation
  const getPasswordStrength = (password) => {
    let strength = 0;
    if (password.length >= 8) strength += 25;
    if (password.length >= 12) strength += 25;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength += 25;
    if (/\d/.test(password)) strength += 15;
    if (/[^A-Za-z0-9]/.test(password)) strength += 10;
    return Math.min(strength, 100);
  };

  const strength = getPasswordStrength(newPassword);
  const strengthColor = strength < 40 ? 'error' : strength < 70 ? 'warning' : 'success';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Validation
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match');
      return;
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    if (!forced && !currentPassword) {
      setError('Current password required');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch('http://192.168.5.103:5000/api/auth/change-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader()
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      });

      const data = await response.json();

      if (response.ok) {
        // Clear session and force user to re-login with new password
        logout();

        // Redirect to login page
        navigate('/login');
      } else {
        setError(data.error || 'Failed to change password');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: forced 
          ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
          : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        padding: 3
      }}
    >
      <Card sx={{ maxWidth: 500, width: '100%' }}>
        <CardContent sx={{ p: 4 }}>
          {/* Header */}
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <Box
              sx={{
                width: 64, height: 64, borderRadius: 2,
                background: forced ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'white', margin: '0 auto 16px'
              }}
            >
              <Lock sx={{ fontSize: 32 }} />
            </Box>
            <Typography variant="h5" fontWeight="bold" gutterBottom>
              {forced ? 'Password Change Required' : 'Change Password'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {forced 
                ? 'For security, you must change the default password'
                : 'Update your password to keep your account secure'}
            </Typography>
          </Box>

          {/* Alert for forced change */}
          {forced && (
            <Alert severity="error" sx={{ mb: 3 }}>
              <strong>Security Warning:</strong> Default passwords are not secure. 
              Please create a strong, unique password before continuing.
            </Alert>
          )}

          {/* Error Alert */}
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit}>
            {!forced && (
              <TextField
                fullWidth
                label="Current Password"
                type={showPasswords.current ? 'text' : 'password'}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                margin="normal"
                required
                disabled={loading}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowPasswords({...showPasswords, current: !showPasswords.current})}
                        edge="end"
                      >
                        {showPasswords.current ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
            )}

            <TextField
              fullWidth
              label="New Password"
              type={showPasswords.new ? 'text' : 'password'}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              margin="normal"
              required
              disabled={loading}
              helperText="Minimum 8 characters, use letters, numbers, and symbols"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPasswords({...showPasswords, new: !showPasswords.new})}
                      edge="end"
                    >
                      {showPasswords.new ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            {/* Password Strength Indicator */}
            {newPassword && (
              <Box sx={{ mt: 1 }}>
                <Box display="flex" justifyContent="space-between" mb={0.5}>
                  <Typography variant="caption" color="text.secondary">
                    Password Strength:
                  </Typography>
                  <Typography variant="caption" color={`${strengthColor}.main`}>
                    {strength < 40 ? 'Weak' : strength < 70 ? 'Medium' : 'Strong'}
                  </Typography>
                </Box>
                <LinearProgress 
                  variant="determinate" 
                  value={strength} 
                  color={strengthColor}
                  sx={{ height: 6, borderRadius: 3 }}
                />
              </Box>
            )}

            <TextField
              fullWidth
              label="Confirm New Password"
              type={showPasswords.confirm ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              margin="normal"
              required
              disabled={loading}
              error={confirmPassword && newPassword !== confirmPassword}
              helperText={confirmPassword && newPassword !== confirmPassword ? 'Passwords do not match' : ''}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPasswords({...showPasswords, confirm: !showPasswords.confirm})}
                      edge="end"
                    >
                      {showPasswords.confirm ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={loading || !newPassword || newPassword !== confirmPassword}
              sx={{ mt: 3, mb: 2 }}
            >
              {loading ? 'Changing Password...' : 'Change Password'}
            </Button>

            {!forced && (
              <Button
                fullWidth
                variant="text"
                onClick={() => navigate(-1)}
                disabled={loading}
              >
                Cancel
              </Button>
            )}
          </form>

          {/* Logout button for forced change */}
          {forced && (
            <Box sx={{ mt: 2, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                Need to logout?{' '}
                <Button
                  size="small"
                  onClick={() => {
                    logout();
                    navigate('/login');
                  }}
                >
                  Logout
                </Button>
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}