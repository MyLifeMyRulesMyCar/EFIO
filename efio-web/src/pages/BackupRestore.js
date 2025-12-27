// efio-web/src/pages/BackupRestore.js
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Button, Alert, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Paper, IconButton,
  Dialog, DialogTitle, DialogContent, DialogActions, CircularProgress
} from '@mui/material';
import { Backup, Restore, Download } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

export default function BackupRestore() {
  const { getAuthHeader } = useAuth();
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [creating, setCreating] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, backup: null });

  const loadBackups = useCallback(async () => {
    try {
      const response = await fetch('http://192.168.5.103:5000/api/backup/list', {
        headers: getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        setBackups(data.backups || []);
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  }, [getAuthHeader]);

  useEffect(() => {
    loadBackups();
  }, [loadBackups]);

  const handleCreate = async () => {
    setCreating(true);
    setMessage(null);
    try {
      const response = await fetch('http://192.168.5.103:5000/api/backup/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify({ include_logs: true })
      });
      const data = await response.json();
      if (response.ok) {
        setMessage({ type: 'success', text: 'Backup created: ' + data.filename });
        loadBackups();
      } else {
        setMessage({ type: 'error', text: data.error || 'Backup failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error: ' + error.message });
    } finally {
      setCreating(false);
    }
  };

  const handleRestore = async (backup) => {
    try {
      const response = await fetch('http://192.168.5.103:5000/api/backup/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify({ filename: backup.filename })
      });
      const data = await response.json();
      if (response.ok) {
        setMessage({ type: 'success', text: 'Restored! System will restart in 10 seconds...' });
        setTimeout(() => window.location.reload(), 10000);
      } else {
        setMessage({ type: 'error', text: data.error || 'Restore failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Restore error: ' + error.message });
    } finally {
      setConfirmDialog({ open: false, backup: null });
    }
  };

  const handleDownload = async (backup) => {
    try {
      const response = await fetch(
        `http://192.168.5.103:5000/api/backup/download?filename=${backup.filename}`,
        {
          headers: getAuthHeader()
        }
      );
      
      if (!response.ok) {
        setMessage({ type: 'error', text: 'Download failed' });
        return;
      }
      
      // Get the blob
      const blob = await response.blob();
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = backup.filename;
      document.body.appendChild(a);
      a.click();
      
      // Cleanup
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      setMessage({ type: 'success', text: 'Download started' });
      
    } catch (error) {
      setMessage({ type: 'error', text: 'Download error: ' + error.message });
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
      <Box display="flex" justifyContent="space-between" mb={3}>
        <Typography variant="h4" fontWeight="bold">Backup & Restore</Typography>
        <Button 
          variant="contained" 
          startIcon={creating ? <CircularProgress size={20} /> : <Backup />} 
          onClick={handleCreate} 
          disabled={creating}
        >
          {creating ? 'Creating...' : 'Create Backup'}
        </Button>
      </Box>

      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>Available Backups ({backups.length})</Typography>
        
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Filename</TableCell>
                <TableCell>Date</TableCell>
                <TableCell>Size</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {backups.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} align="center">
                    <Box py={3}>
                      <Typography color="text.secondary">No backups found</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Create your first backup using the button above
                      </Typography>
                    </Box>
                  </TableCell>
                </TableRow>
              ) : (
                backups.map((b, i) => (
                  <TableRow key={i} hover>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        <Backup fontSize="small" color="primary" />
                        {b.filename}
                      </Box>
                    </TableCell>
                    <TableCell>{new Date(b.created).toLocaleString()}</TableCell>
                    <TableCell>{(b.size / 1024).toFixed(1)} KB</TableCell>
                    <TableCell align="right">
                      <IconButton 
                        size="small" 
                        color="primary"
                        onClick={() => handleDownload(b)} 
                        title="Download"
                      >
                        <Download />
                      </IconButton>
                      <IconButton 
                        size="small" 
                        color="success" 
                        onClick={() => setConfirmDialog({ open: true, backup: b })} 
                        title="Restore"
                      >
                        <Restore />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Dialog 
        open={confirmDialog.open} 
        onClose={() => setConfirmDialog({ open: false, backup: null })}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Confirm Restore</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This will overwrite current configuration!
          </Alert>
          <Typography variant="body2" gutterBottom>
            Are you sure you want to restore from:
          </Typography>
          <Typography variant="body1" fontWeight="bold" sx={{ mt: 1 }}>
            {confirmDialog.backup?.filename}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Created: {confirmDialog.backup && new Date(confirmDialog.backup.created).toLocaleString()}
          </Typography>
          <Typography variant="body2" sx={{ mt: 2 }} color="text.secondary">
            The system will restart after restore.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialog({ open: false, backup: null })}>
            Cancel
          </Button>
          <Button 
            variant="contained" 
            color="warning" 
            onClick={() => handleRestore(confirmDialog.backup)}
          >
            Restore
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}