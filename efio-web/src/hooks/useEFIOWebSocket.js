// src/hooks/useEFIOWebSocket.js
// Fixed WebSocket hook with better error handling and fallback

import { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';

export default function useEFIOWebSocket() {
  const [connected, setConnected] = useState(false);
  const [ioData, setIoData] = useState({
    di: [0, 0, 0, 0],
    do: [0, 0, 0, 0]
  });
  const [systemData, setSystemData] = useState({
    cpu: 0,
    ram: 0,
    temp: 0,
    uptime: 0
  });
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [socket, setSocket] = useState(null);
  const reconnectAttempts = useRef(0);

  useEffect(() => {
    console.log('🔌 Initializing WebSocket connection to http://192.168.5.103:5000');
    
    // Create socket with better configuration
    const newSocket = io('http://192.168.5.103:5000', {
      // Try WebSocket first, then polling
      transports: ['polling', 'websocket'],
      
      // Connection options
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: Infinity,
      
      // Timeout options
      timeout: 20000,
      
      // Force new connection
      forceNew: true,
      
      // Additional options for better compatibility
      upgrade: true,
      rememberUpgrade: true,
      
      // Enable auto-connect
      autoConnect: true,
      
      // Query parameters for debugging
      query: {
        client: 'efio-web',
        timestamp: Date.now()
      }
    });

    // Connection event handlers
    newSocket.on('connect', () => {
      reconnectAttempts.current = 0;
      console.log('✅ WebSocket Connected successfully!');
      console.log('   Transport:', newSocket.io.engine.transport.name);
      console.log('   Socket ID:', newSocket.id);
      setConnected(true);
      
      // Request initial data
      console.log('📤 Requesting initial I/O state...');
      newSocket.emit('request_io');
      
      console.log('📤 Requesting initial system metrics...');
      newSocket.emit('request_system');
    });

    newSocket.on('connect_error', (error) => {
      reconnectAttempts.current += 1;
      console.error(`❌ Connection error (attempt ${reconnectAttempts.current}):`, error.message);
      console.error('   Make sure Flask backend is running on port 5000');
      console.error('   Check: python3 api/app.py is running');
      setConnected(false);
    });

    newSocket.on('disconnect', (reason) => {
      console.log('❌ WebSocket Disconnected:', reason);
      if (reason === 'io server disconnect') {
        console.log('   Server forced disconnect, reconnecting...');
        newSocket.connect();
      }
      setConnected(false);
    });

    newSocket.on('reconnect', (attemptNumber) => {
      console.log(`🔄 Reconnected after ${attemptNumber} attempts`);
      setConnected(true);
      newSocket.emit('request_io');
      newSocket.emit('request_system');
    });

    newSocket.on('reconnect_attempt', (attemptNumber) => {
      console.log(`🔄 Reconnection attempt ${attemptNumber}...`);
    });

    newSocket.on('reconnect_failed', () => {
      console.error('❌ Reconnection failed after all attempts');
    });

    // Data event handlers
    newSocket.on('io_update', (data) => {
      console.log('📥 I/O Update received:', data);
      if (data && data.di && data.do) {
        // Force new object reference to trigger React re-render
        setIoData({
          di: [...data.di],
          do: [...data.do]
        });
        setLastUpdate(new Date());
        console.log('✅ I/O state updated in React');
      } else {
        console.warn('⚠️ Received invalid I/O data:', data);
      }
    });

    newSocket.on('system_update', (data) => {
      console.log('📊 System Update received:', data);
      if (data) {
        // Force new object reference to trigger React re-render
        setSystemData({
          cpu: data.cpu?.percent || 0,
          ram: data.memory?.percent || 0,
          temp: data.temperature?.celsius || 0,
          uptime: data.uptime_seconds || 0
        });
        setLastUpdate(new Date());
        console.log('✅ System metrics updated in React');
      } else {
        console.warn('⚠️ Received invalid system data:', data);
      }
    });

    newSocket.on('error', (error) => {
      console.error('❌ WebSocket Error:', error);
    });

    // Debug: Log all events
    newSocket.onAny((eventName, ...args) => {
      console.log(`📨 Event '${eventName}':`, args);
    });

    setSocket(newSocket);

    // Cleanup on unmount
    return () => {
      console.log('🔌 Closing WebSocket connection');
      newSocket.close();
    };
  }, []);

  // Function to toggle digital output
  const toggleDO = (channel, state) => {
    if (!socket) {
      console.error('❌ Cannot toggle DO: Socket not initialized');
      return;
    }
    
    if (!connected) {
      console.error('❌ Cannot toggle DO: WebSocket not connected');
      alert('Not connected to controller. Please wait for connection.');
      return;
    }
    
    const value = state ? 1 : 0;
    console.log(`⚡ Setting DO${channel} to ${state ? 'ON' : 'OFF'} (value: ${value})`);
    
    socket.emit('set_do', { 
      channel: channel, 
      value: value 
    });
    
    // Also update via REST API as fallback
    fetch(`http://192.168.5.103:5000/api/io/do/${channel}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ state: state }),
    })
    .then(response => response.json())
    .then(data => {
      console.log('✅ REST API fallback confirmed:', data);
    })
    .catch(error => {
      console.error('❌ REST API fallback failed:', error);
    });
  };

  return {
    connected,
    ioData,
    systemData,
    toggleDO,
    lastUpdate,
    socket // Expose socket for debugging
  };
}