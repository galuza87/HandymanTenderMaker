import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { testingApi } from './services/testingApi';

export default function TestingDashboard() {
  const [history, setHistory] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [testCasesInput, setTestCasesInput] = useState(JSON.stringify([
    { id: 1, input: "I need a plumber to fix a leak", expected: "single" },
    { id: 2, input: "I need a plumber and an electrician", expected: "multiple" },
    { id: 3, input: "hello", expected: "unknown" },
    { id: 4, input: "I'm looking for a tiler to replace the flooring in my half-bathroom. Right now it's old linoleum, and I want to put down ceramic tile. The catch is that there's a hot water radiator heating pipe that runs right under the floorboards, and the floor dips exactly where the pipe runs. I need the floor leveled out over that pipe dip and the new tiles laid down. I already bought the tiles and the thinset.", expected: "unknown" },
    { id: 5, input: "I am looking for a handyman to fix the wall right behind my bathroom sink. The backsplash tiles are starting to bulge out a bit in the middle, and the drywall on the other side of that exact wall (in the hallway) has a weird yellow water stain near the baseboard. I just want the bulging tiles taken off and put back on flat, and maybe some fresh caulking around the sink base to make it look nice again.", expected: "unknown" },
    { id: 6, input: "Hey, need a tile guy to help with my shower floor. A few of the mosaic tiles right around the metal drain grate are coming loose and the grout is cracking. The metal drain thing is also sitting a bit crooked now. When I step on the tiles next to it, water kinda squishes up from underneath. Can he come re-stick the loose tiles, put new grout down, and just straighten out the drain cover so it's flush again?", expected: "unknown" },
    { id: 7, input: "I need some help fixing my house", expected: "unknown" }
  ], null, 2));
  const [selectedResults, setSelectedResults] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const runs = await testingApi.getHistory();
      const formattedRuns = runs.reverse().map(run => ({
        ...run,
        AverageExecutionTime: run.AverageExecutionTime / 1000
      }));
      setHistory(formattedRuns); // Oldest first for charts
    } catch (e) {
      console.error("Failed to fetch history", e);
    }
  };

  const handleRunTests = async () => {
    setIsRunning(true);
    setSelectedResults(null);
    try {
      const cases = JSON.parse(testCasesInput);
      const result = await testingApi.runTests("contractor-intent", cases);
      setSelectedResults({ ...result, isHistorical: false });
      await fetchHistory();
    } catch (e) {
      alert("Error running tests: " + e.message);
    } finally {
      setIsRunning(false);
    }
  };

  const handleChartClick = async (data) => {
    let runData = null;
    if (data && data.activePayload && data.activePayload.length > 0) {
      runData = data.activePayload[0].payload;
    } else if (data && data.activeLabel) {
      runData = history.find(h => h.RunID === data.activeLabel);
    } else if (data && data.RunID !== undefined) {
      runData = data;
    } else if (data && data.payload && data.payload.RunID !== undefined) {
      runData = data.payload;
    }

    if (!runData || !runData.RunID) return;

    try {
      const results = await testingApi.getRunDetails(runData.RunID);
      setSelectedResults({
        isHistorical: true,
        run_id: runData.RunID,
        accuracy: runData.OverallAccuracy,
        avg_time_ms: runData.AverageExecutionTime * 1000,
        results: results.map((r, idx) => ({
          id: idx + 1,
          input: r.InputText,
          expected: r.ExpectedOutcome,
          actual: r.ActualOutcome,
          exec_time: r.ExecutionTimeMs,
          is_correct: r.IsCorrect
        }))
      });
    } catch (e) {
      alert("Error fetching run details: " + e.message);
    }
  };

  return (
    <main className="directory-container" style={{ padding: '20px', overflowY: 'auto' }}>
      <div style={{ marginBottom: '20px' }}>
        <h3>🧪 Test Execution: Contractor Intent</h3>
        <p>Edit the JSON below to add or modify test cases. Expected values: <code>single</code>, <code>multiple</code>, <code>unknown</code> (for vague requests caught by the Data Validator).</p>
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

      {selectedResults && (
        <div style={{ marginBottom: '30px', background: '#1a1f36', padding: '20px', borderRadius: '8px' }}>
          <h4>{selectedResults.isHistorical ? `Latest Run Results - Run #${selectedResults.run_id} Results` : 'Latest Run Results'} (Accuracy: {selectedResults.accuracy.toFixed(1)}%, Avg Time: {(selectedResults.avg_time_ms / 1000).toFixed(3)}s)</h4>
          <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', marginTop: '10px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #333' }}>
                <th>Test ID</th>
                <th>Expected</th>
                <th>Actual</th>
                <th>Time (s)</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {selectedResults.results.map((res, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                  <td style={{ padding: '8px 0', cursor: 'help' }} title={res.input}>#{res.id || (i + 1)}</td>
                  <td>{res.expected}</td>
                  <td>{res.actual}</td>
                  <td>{(res.exec_time / 1000).toFixed(3)}</td>
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
              <LineChart data={history} onClick={handleChartClick} style={{ cursor: 'pointer' }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="RunID" stroke="#888" />
                <YAxis domain={[0, 100]} stroke="#888" />
                <Tooltip contentStyle={{ background: '#1a1f36', border: '1px solid #333' }} />
                <Legend />
                <Line type="monotone" dataKey="OverallAccuracy" name="Accuracy" stroke="#8884d8" strokeWidth={3} activeDot={{ onClick: (e, payload) => handleChartClick(payload) }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div style={{ flex: '1 1 400px', background: '#1a1f36', padding: '20px', borderRadius: '8px' }}>
            <h4>Average Execution Time (s)</h4>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={history} onClick={handleChartClick} style={{ cursor: 'pointer' }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="RunID" stroke="#888" />
                <YAxis stroke="#888" />
                <Tooltip contentStyle={{ background: '#1a1f36', border: '1px solid #333' }} />
                <Legend />
                <Bar dataKey="AverageExecutionTime" name="Avg Time (s)" fill="#82ca9d" onClick={handleChartClick} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </main>
  );
}
