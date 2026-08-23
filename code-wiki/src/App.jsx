import { useState, useEffect, useCallback } from 'react';
import { ReactFlow, Controls, Background, applyNodeChanges, applyEdgeChanges } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Search, ChevronDown, ChevronRight } from 'lucide-react';
import './index.css';

export default function App() {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [atlas, setAtlas] = useState(null);
  const [wiki, setWiki] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedNode, setSelectedNode] = useState(null);
  const [expanded, setExpanded] = useState({ about: false, tools: false, stack: false });

  const toggleSection = (section) => {
    setExpanded(prev => ({ ...prev, [section]: !prev[section] }));
  };

  useEffect(() => {
    Promise.all([
      fetch('/code_atlas.json').then(res => res.json()),
      fetch('/workflows.json').then(res => res.json()).catch(() => []),
      fetch('/wiki_content.json').then(res => res.json()).catch(() => null)
    ]).then(([data, workflows, wikiContent]) => {
        setAtlas(data);
        setWiki(wikiContent);
        const newNodes = [];
        const newEdges = [];
        
        let yPos = 0;
        const endpointNodeMap = {}; // mapping label to id
        
        // Add Endpoints
        data.all_endpoints.forEach((ep, idx) => {
          const id = `ep-${idx}`;
          const label = `${ep.method} ${ep.path || ep.name}`;
          endpointNodeMap[label] = id;
          newNodes.push({
            id: id,
            position: { x: 100, y: yPos },
            data: { label: label, file: ep.file, line: ep.line_number },
            type: 'default',
            style: { background: '#4f46e5', color: '#fff', padding: 10, borderRadius: 5, width: 250 }
          });
          yPos += 60;
        });
        
        yPos = 0;
        // Add Models
        data.all_models.forEach((mod, idx) => {
          newNodes.push({
            id: `mod-${idx}`,
            position: { x: 500, y: yPos },
            data: { label: `Model: ${mod.name}`, file: mod.file, line: mod.line_number },
            type: 'default',
            style: { background: '#10b981', color: '#fff', padding: 10, borderRadius: 5, width: 250 }
          });
          yPos += 60;
        });
        
        // Add Modules
        let modYPos = 0;
        (data.all_modules || []).forEach((module, idx) => {
          newNodes.push({
            id: `module-${idx}`,
            position: { x: -100, y: modYPos },
            data: { label: `Module: ${module.name}`, file: module.file, type: 'module' },
            type: 'default',
            style: { background: '#f59e0b', color: '#fff', padding: 10, borderRadius: 5, width: 250 }
          });
          modYPos += 60;
        });
        
        // Add Workflows
        let wfYPos = 0;
        workflows.forEach((wf, wfIdx) => {
          newNodes.push({
            id: `wf-group-${wfIdx}`,
            position: { x: -300, y: wfYPos - 40 },
            data: { label: wf.name },
            type: 'default',
            style: { background: 'transparent', color: '#fbcfe8', border: 'none', fontWeight: 'bold', fontSize: '1.2rem', width: 250, textAlign: 'left', padding: 0 }
          });

          let prevStepId = null;
          wf.steps.forEach((step, stepIdx) => {
            const stepId = step.id;
            newNodes.push({
              id: stepId,
              position: { x: -300, y: wfYPos },
              data: { label: `Step ${stepIdx + 1}: ${step.name}` },
              type: 'default',
              style: { background: '#db2777', color: '#fff', padding: 10, borderRadius: 5, width: 250 }
            });
            
            if (prevStepId) {
              newEdges.push({
                id: `e-${prevStepId}-${stepId}`,
                source: prevStepId,
                target: stepId,
                animated: true,
                style: { stroke: '#f472b6', strokeWidth: 2 }
              });
            }
            
            // Connect to targets
            (step.targets || []).forEach(targetLabel => {
              const targetId = endpointNodeMap[targetLabel];
              if (targetId) {
                newEdges.push({
                  id: `e-${stepId}-${targetId}`,
                  source: stepId,
                  target: targetId,
                  animated: true,
                  style: { stroke: '#818cf8', strokeWidth: 2 }
                });
              }
            });
            
            prevStepId = stepId;
            wfYPos += 60;
          });
          wfYPos += 60; // spacing between workflows
        });

        setNodes(newNodes);
        setEdges(newEdges);
      });
  }, []);

  const onNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),
    [],
  );
  
  const onEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  );

  const onNodeClick = (e, node) => {
    setSelectedNode(node);
  };

  const handleJump = () => {
    if (!selectedNode?.data?.file) return;
    const pathInfo = `${selectedNode.data.file}:${selectedNode.data.line}`;
    navigator.clipboard.writeText(pathInfo);
    alert(`Copied reference to clipboard:\n${pathInfo}\n\nPaste this in your IDE search (Ctrl+P)!`);
  };

  const filteredNodes = nodes.filter(n => n.data.label.toLowerCase().includes(searchTerm.toLowerCase()));

  return (
    <div className="app-container">
      <header className="header">
        <h1>DynamicPromptWizard Code Atlas</h1>
        <div className="search-bar">
          <Search size={20} />
          <input 
            type="text" 
            placeholder="Search API, function, or model..." 
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>
      </header>
      
      <main className="main-content">
        {wiki && (
          <aside className="left-panel">
            <div className="nav-section">
              <h2 onClick={() => toggleSection('about')} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                {expanded.about ? <ChevronDown size={18} style={{marginRight: 8}} /> : <ChevronRight size={18} style={{marginRight: 8}} />} About
              </h2>
              {expanded.about && <p>{wiki.about}</p>}
            </div>
            <div className="nav-section">
              <h2 onClick={() => toggleSection('tools')} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                {expanded.tools ? <ChevronDown size={18} style={{marginRight: 8}} /> : <ChevronRight size={18} style={{marginRight: 8}} />} Tools
              </h2>
              {expanded.tools && wiki.tools.map((t, i) => (
                <div key={i} className="tool-item">
                  <h3>{t.name}</h3>
                  <p>{t.description}</p>
                </div>
              ))}
            </div>
            <div className="nav-section">
              <h2 onClick={() => toggleSection('stack')} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                {expanded.stack ? <ChevronDown size={18} style={{marginRight: 8}} /> : <ChevronRight size={18} style={{marginRight: 8}} />} Core Engine Stack
              </h2>
              {expanded.stack && (
                <div className="stack-trace">
                  {wiki.stackTrace.map((st, i) => (
                    <div key={i} className="stack-item" onClick={() => setSearchTerm(st.name)}>
                      <div className="stack-title">{st.name}</div>
                      <div className="stack-detail"><span className="stack-label">Input:</span>{st.input}</div>
                      <div className="stack-detail"><span className="stack-label">Output:</span>{st.output}</div>
                      <div className="stack-desc">{st.description}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </aside>
        )}
        <div className="flow-container">
          <ReactFlow 
            nodes={filteredNodes} 
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        
        <aside className="sidebar">
          {selectedNode ? (
            <div className="node-details">
              <h2>{selectedNode.data.label}</h2>
              {selectedNode.data.line && (
              <p><strong>Line:</strong> {selectedNode.data.line}</p>
            )}
            
            {/* ENDPOINT DETAILS */}
            {selectedNode.id.startsWith('ep-') && atlas.files[selectedNode.data.file] && (
              <div className="module-functions" style={{ marginTop: '1rem' }}>
                <h3 style={{ borderBottom: '1px solid #333', paddingBottom: '5px' }}>Endpoint Method</h3>
                {(() => {
                  const epFn = atlas.files[selectedNode.data.file].endpoints.find(e => e.line_number === selectedNode.data.line);
                  if (!epFn) return null;
                  return (
                    <div className="function-card" style={{ background: 'rgba(255,255,255,0.05)', padding: '10px', marginBottom: '10px', borderRadius: '5px' }}>
                      <h4 style={{ margin: '0 0 5px 0', color: '#60a5fa' }}>{epFn.name}()</h4>
                      {epFn.docstring && <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0 0 5px 0' }}>{epFn.docstring}</p>}
                      <p style={{ margin: '0', fontSize: '0.8rem' }}><strong style={{ color: '#a78bfa' }}>Input:</strong> {(epFn.args || []).join(', ') || 'None'}</p>
                      <p style={{ margin: '0', fontSize: '0.8rem' }}><strong style={{ color: '#a78bfa' }}>Output:</strong> {epFn.returns || 'Untyped'}</p>
                      {epFn.calls && epFn.calls.length > 0 && (
                        <div style={{ marginTop: '5px' }}>
                          <strong style={{ color: '#a78bfa', fontSize: '0.8rem' }}>Calls:</strong>
                          <ul style={{ margin: '0', paddingLeft: '20px', fontSize: '0.8rem', color: '#cbd5e1' }}>
                            {epFn.calls.map((call, cidx) => (
                              <li key={cidx}>
                                <a href="#" onClick={(e) => { e.preventDefault(); setSearchTerm(call); }} style={{ color: '#38bdf8', textDecoration: 'none' }}>{call}</a>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
            )}
            
            {/* MODEL DETAILS */}
            {selectedNode.id.startsWith('mod-') && atlas.files[selectedNode.data.file] && (
              <div className="module-functions" style={{ marginTop: '1rem' }}>
                <h3 style={{ borderBottom: '1px solid #333', paddingBottom: '5px' }}>Model Fields</h3>
                {(() => {
                  const cls = atlas.files[selectedNode.data.file].classes.find(c => c.line_number === selectedNode.data.line);
                  if (!cls) return null;
                  return (
                    <div className="function-card" style={{ background: 'rgba(255,255,255,0.05)', padding: '10px', marginBottom: '10px', borderRadius: '5px' }}>
                      <h4 style={{ margin: '0 0 5px 0', color: '#10b981' }}>{cls.name}</h4>
                      {cls.docstring && <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0 0 5px 0' }}>{cls.docstring}</p>}
                      <div style={{ marginTop: '5px' }}>
                        <strong style={{ color: '#10b981', fontSize: '0.8rem' }}>Fields:</strong>
                        <ul style={{ margin: '0', paddingLeft: '20px', fontSize: '0.8rem', color: '#cbd5e1' }}>
                          {(cls.fields || []).map((f, cidx) => <li key={cidx}>{f}</li>)}
                        </ul>
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}
            
            {selectedNode.data.type === 'module' && atlas.files[selectedNode.data.file] && (
              <div className="module-functions" style={{ marginTop: '1rem' }}>
                <h3 style={{ borderBottom: '1px solid #333', paddingBottom: '5px' }}>Functions</h3>
                {atlas.files[selectedNode.data.file].functions.map((fn, idx) => (
                  <div key={idx} className="function-card" style={{ background: 'rgba(255,255,255,0.05)', padding: '10px', marginBottom: '10px', borderRadius: '5px' }}>
                    <h4 style={{ margin: '0 0 5px 0', color: '#60a5fa' }}>{fn.name}()</h4>
                    {fn.docstring && <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0 0 5px 0' }}>{fn.docstring}</p>}
                    <p style={{ margin: '0', fontSize: '0.8rem' }}><strong style={{ color: '#a78bfa' }}>Input:</strong> {fn.args.join(', ') || 'None'}</p>
                    <p style={{ margin: '0', fontSize: '0.8rem' }}><strong style={{ color: '#a78bfa' }}>Output:</strong> {fn.returns || 'Untyped'}</p>
                    {fn.calls && fn.calls.length > 0 && (
                      <div style={{ marginTop: '5px' }}>
                        <strong style={{ color: '#a78bfa', fontSize: '0.8rem' }}>Calls:</strong>
                        <ul style={{ margin: '0', paddingLeft: '20px', fontSize: '0.8rem', color: '#cbd5e1' }}>
                          {fn.calls.map((call, cidx) => (
                            <li key={cidx}>
                              <a href="#" onClick={(e) => { e.preventDefault(); setSearchTerm(call); }} style={{ color: '#38bdf8', textDecoration: 'none' }}>{call}</a>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            
            {selectedNode.data.file && selectedNode.data.line && (
                <div style={{ margin: '1rem 0', padding: '0.75rem', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', fontSize: '0.9rem', wordBreak: 'break-all', border: '1px solid rgba(255,255,255,0.1)' }}>
                  <code style={{ color: '#a78bfa' }}>{selectedNode.data.file}</code>
                  <br/>
                  <span style={{ color: '#94a3b8' }}>Line: {selectedNode.data.line}</span>
                </div>
              )}
              <button className="link-btn" onClick={handleJump}>Copy Code Reference</button>
            </div>
          ) : (
            <div className="empty-state">
              <p>Select a node on the map to see details and links.</p>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}
