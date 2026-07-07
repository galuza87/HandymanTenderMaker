import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { testingApi } from './services/testingApi';

export default function TestingDashboard() {
  const [history, setHistory] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [testCasesInput, setTestCasesInput] = useState(JSON.stringify([
    { input: "I need a plumber to fix a leak", expected: "single" },
    { input: "I need a plumber and an electrician", expected: "multiple" },
    { input: "hello", expected: "not able to identify" }
  ], null, 2));
  const [latestResults, setLatestResults] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const runs = await testingApi.getHistory();
      setHistory(runs.reverse()); // Oldest first for charts
    } catch (e) {
      console.error("Failed to fetch history", e);
    }
  };

  const handleRunTests = async () => {
    setIsRunning(true);
    setLatestResults(null);
    try {
      const cases = JSON.parse(testCasesInput);
      const result = await testingApi.runTests("contractor-intent", cases);
      setLatestResults(result);
      await fetchHistory();
    } catch (e) {
      alert("Error running tests: " + e.message);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <main className="directory-container" style={{ padding: '20px', overflowY: 'auto' }}>
      <div style={{ marginBottom: '20px' }}>
        <h3>🧪 Test Execution: Contractor Intent</h3>
        <p>Edit the JSON below to add or modify test cases. Expected values: <code>single</code>, <code>multiple</code>, <code>not able to identify</code>.</p>
        <textarea 
          style={{ width: '100%', height: '150px', fontFamily: 'monospace', padding: '10px', background: '#1a1f36', color: '#fff', border: '1px solid #333', borderRadius: '4px' }}
          value={testCasesInput}
          onChange={(e) => setTestCasesInput(e.target.value)}
        />
        <button 
          className="btn-primary" 
          style={{ marginTop: '10px' }}
          onClick={handleRunTests}
          disabled={isRunning}
        >
          {isRunning ? "Running Tests..." : "Run Tests"}
        </button>
      </div>

      {latestResults && (
        <div style={{ marginBottom: '30px', background: '#1a1f36', padding: '20px', borderRadius: '8px' }}>
          <h4>Latest Run Results (Accuracy: {latestResults.accuracy.toFixed(1)}%, Avg Time: {latestResults.avg_time_ms.toFixed(0)}ms)</h4>
          <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', marginTop: '10px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #333' }}>
                <th>Input</th>
                <th>Expected</th>
                <th>Actual</th>
                <th>Time (ms)</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {latestResults.results.map((res, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                  <td style={{ padding: '8px 0' }}>{res.input}</td>
                  <td>{res.expected}</td>
                  <td>{res.actual}</td>
                  <td>{res.exec_time.toFixed(0)}</td>
                  <td style={{ color: res.is_correct ? '#4caf50' : '#f44336' }}>
                    {res.is_correct ? "Pass" : "Fail"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {history.length > 0 && (
        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 400px', background: '#1a1f36', padding: '20px', borderRadius: '8px' }}>
            <h4>Accuracy Over Time (%)</h4>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="RunID" stroke="#888" />
                <YAxis domain={[0, 100]} stroke="#888" />
                <Tooltip contentStyle={{ background: '#1a1f36', border: '1px solid #333' }} />
                <Legend />
                <Line type="monotone" dataKey="OverallAccuracy" name="Accuracy" stroke="#8884d8" strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div style={{ flex: '1 1 400px', background: '#1a1f36', padding: '20px', borderRadius: '8px' }}>
            <h4>Average Execution Time (ms)</h4>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="RunID" stroke="#888" />
                <YAxis stroke="#888" />
                <Tooltip contentStyle={{ background: '#1a1f36', border: '1px solid #333' }} />
                <Legend />
                <Bar dataKey="AverageExecutionTime" name="Avg Time (ms)" fill="#82ca9d" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </main>
  );
}
