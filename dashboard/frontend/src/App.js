import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const API_BASE = 'http://localhost:8000';

// ─────────────────────────────────────────
// MAIN APP
// ─────────────────────────────────────────

function App() {
  const [topology, setTopology] = useState({ devices: [], links: [] });
  const [anomalies, setAnomalies] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [chatMessages, setChatMessages] = useState([
    { role: 'assistant', text: '👋 Hi! I am your AIOps Network Assistant. Ask me anything about the network.' }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isRunningRCA, setIsRunningRCA] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [wsStatus, setWsStatus] = useState('connecting');
  const wsRef = useRef(null);

  // Load initial data
  useEffect(() => {
    fetchTopology();
    fetchAnomalies();
    connectWebSocket();
    const interval = setInterval(fetchAnomalies, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchTopology = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/topology`);
      const data = await res.json();
      setTopology(data);
    } catch (e) {
      console.error('Failed to fetch topology', e);
    }
  };

  const fetchAnomalies = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/anomalies`);
      const data = await res.json();
      setAnomalies(data.anomalies || []);
    } catch (e) {
      console.error('Failed to fetch anomalies', e);
    }
  };

  const connectWebSocket = () => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    wsRef.current = ws;

    ws.onopen = () => setWsStatus('connected');
    ws.onclose = () => {
      setWsStatus('disconnected');
      setTimeout(connectWebSocket, 3000);
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'telemetry_update') {
        setAnomalies(data.faulty_devices || []);
      }
    };
  };

  const simulateFault = async (scenarioId) => {
    await fetch(`${API_BASE}/api/simulate/${scenarioId}`, { method: 'POST' });
    setTimeout(fetchAnomalies, 1000);
  };

  const clearFaults = async () => {
    await fetch(`${API_BASE}/api/simulate/clear`, { method: 'POST' });
    setTimeout(fetchAnomalies, 1000);
  };

  const runRCA = async () => {
    setIsRunningRCA(true);
    try {
      const res = await fetch(`${API_BASE}/api/agent/rca`, { method: 'POST' });
      const data = await res.json();
      setIncidents(data.incidents || []);
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        text: `🔍 RCA Complete! Processed ${data.incidents_processed} incidents. ${data.incidents?.map(i => `\n• ${i.device_id}: ${i.fault_type} (${i.risk_level} risk)`).join('')}`
      }]);
    } catch (e) {
      console.error('RCA failed', e);
    }
    setIsRunningRCA(false);
  };

  const sendChat = async () => {
    if (!chatInput.trim()) return;
    const question = chatInput;
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: question }]);

    try {
      const res = await fetch(`${API_BASE}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question })
      });
      const data = await res.json();
      setChatMessages(prev => [...prev, { role: 'assistant', text: data.response }]);
    } catch (e) {
      setChatMessages(prev => [...prev, { role: 'assistant', text: '❌ Error connecting to AI agent.' }]);
    }
  };

  // Get anomalous device IDs for highlighting
  const anomalousIds = new Set(anomalies.map(a => a.device_id || a.fault_type));

  return (
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <div className="header-left">
          <span className="logo">⚡ AIOps Network Intelligence</span>
          <span className={`ws-status ${wsStatus}`}>
            {wsStatus === 'connected' ? '🟢 Live' : '🔴 Offline'}
          </span>
        </div>
        <div className="header-right">
          <span className="stat">Devices: {topology.devices?.length || 0}</span>
          <span className="stat anomaly">Anomalies: {anomalies.length}</span>
        </div>
      </header>

      <div className="main">
        {/* LEFT PANEL — Network Graph */}
        <div className="left-panel">
          <div className="panel-header">
            <h2>Network Topology</h2>
            <div className="controls">
              <button onClick={() => simulateFault('scenario_1')} className="btn btn-danger">
                💥 Simulate Fault
              </button>
              <button onClick={clearFaults} className="btn btn-success">
                ✅ Clear Faults
              </button>
              <button onClick={runRCA} className="btn btn-primary" disabled={isRunningRCA}>
                {isRunningRCA ? '🔄 Running RCA...' : '🤖 Run AI RCA'}
              </button>
            </div>
          </div>

          {/* Network Grid Visualization */}
          <div className="network-grid">
            {topology.devices?.map(device => {
              const isAnomalous = anomalies.some(a => a.device_id === device.id);
              const anomaly = anomalies.find(a => a.device_id === device.id);
              return (
                <div
                  key={device.id}
                  className={`device-node ${device.type} ${isAnomalous ? 'anomalous' : ''}`}
                  onClick={() => setSelectedDevice(isAnomalous ? anomaly : device)}
                  title={device.name}
                >
                  <span className="device-icon">{getDeviceIcon(device.type)}</span>
                  <span className="device-name">{device.name.split('-').pop()}</span>
                  {isAnomalous && <span className="alert-dot">!</span>}
                </div>
              );
            })}
          </div>

          {/* Device Detail Panel */}
          {selectedDevice && (
            <div className="device-detail">
              <h3>
                {selectedDevice.device_id || selectedDevice.id}
                <button onClick={() => setSelectedDevice(null)} className="close-btn">✕</button>
              </h3>
              {selectedDevice.fault_type && (
                <>
                  <p><strong>Fault:</strong> {selectedDevice.fault_type}</p>
                  <p><strong>Risk:</strong> <span className={`risk ${selectedDevice.risk_level?.toLowerCase()}`}>{selectedDevice.risk_level}</span></p>
                  <p><strong>Summary:</strong> {selectedDevice.summary}</p>
                </>
              )}
              {selectedDevice.type && (
                <>
                  <p><strong>Type:</strong> {selectedDevice.type}</p>
                  <p><strong>Location:</strong> {selectedDevice.location}</p>
                  <p><strong>Vendor:</strong> {selectedDevice.vendor}</p>
                  <p><strong>IP:</strong> {selectedDevice.ip_address}</p>
                </>
              )}
            </div>
          )}
        </div>

        {/* RIGHT PANEL — Chat + Incidents */}
        <div className="right-panel">
          {/* AI Chat */}
          <div className="chat-panel">
            <h2>🤖 NOC AI Assistant</h2>
            <div className="chat-messages">
              {chatMessages.map((msg, i) => (
                <div key={i} className={`message ${msg.role}`}>
                  <span className="message-role">{msg.role === 'user' ? '👤' : '🤖'}</span>
                  <span className="message-text">{msg.text}</span>
                </div>
              ))}
            </div>
            <div className="chat-input">
              <input
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyPress={e => e.key === 'Enter' && sendChat()}
                placeholder="Ask about network status..."
              />
              <button onClick={sendChat} className="btn btn-primary">Send</button>
            </div>
          </div>

          {/* Incidents */}
          <div className="incidents-panel">
            <h2>📋 Recent Incidents</h2>
            {incidents.length === 0 ? (
              <p className="no-incidents">No incidents yet. Run AI RCA to detect issues.</p>
            ) : (
              incidents.map((incident, i) => (
                <div key={i} className={`incident-card ${incident.risk_level?.toLowerCase()}`}>
                  <div className="incident-header">
                    <strong>{incident.device_id}</strong>
                    <span className={`risk-badge ${incident.risk_level?.toLowerCase()}`}>
                      {incident.risk_level}
                    </span>
                  </div>
                  <p><strong>Fault:</strong> {incident.fault_type}</p>
                  <p><strong>Impact:</strong> {incident.blast_radius} devices affected</p>
                  <p><strong>Status:</strong> {incident.remediation_status}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function getDeviceIcon(type) {
  const icons = {
    router: '🌐',
    switch: '🔀',
    firewall: '🛡️',
    server: '🖥️',
    load_balancer: '⚖️'
  };
  return icons[type] || '📦';
}

export default App;