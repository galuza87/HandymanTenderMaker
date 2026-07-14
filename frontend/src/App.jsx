import { useState, useRef, useEffect } from 'react'
import './App.css'
import TestingDashboard from './TestingDashboard'

function App() {
  // Auth States
  const [loggedInClient, setLoggedInClient] = useState(null);
  const [isRegistering, setIsRegistering] = useState(false);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [editData, setEditData] = useState({});
  const [loginPhone, setLoginPhone] = useState('');
  const [regData, setRegData] = useState({ name: '', last_name: '', phone: '', additional_phone: '', email: '', address: '' });
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [clientProjects, setClientProjects] = useState([]);

  // App States
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' or 'directory'
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '👋 **Welcome to the Handyman & Contractor Bid Wizard!** 🛠️\n\nI can help you draft professional quote prompts, handyman service requests, and subcontractor tenders.\n\nWould you like to build a **Handyman Service Request**, a **Construction Quote**, or a **Subcontractor Tender**? Tell me what you need done!'
    }
  ]);
  const [input, setInput] = useState('');
  const [sessionId] = useState(() => Math.random().toString(36).substring(7));
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const [isLoading, setIsLoading] = useState(false);
  const [image, setImage] = useState(null);

  // DB States
  const [categories, setCategories] = useState([]);
  const [contractors, setContractors] = useState([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [contractorsLoading, setContractorsLoading] = useState(true);

  // Search States
  const [categorySearch, setCategorySearch] = useState('');
  const [contractorSearch, setContractorSearch] = useState('');
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (loggedInClient) {
      scrollToBottom();
    }
  }, [messages, loggedInClient]);

  // Fetch Categories & Contractors
  useEffect(() => {
    if (!loggedInClient) return;
    const fetchCategories = async () => {
      try {
        const response = await fetch('/api/categories');
        if (response.ok) {
          const data = await response.json();
          setCategories(data);
        }
      } catch (error) {
        console.error('Error fetching categories:', error);
      } finally {
        setCategoriesLoading(false);
      }
    };

    const fetchContractors = async () => {
      try {
        const response = await fetch('/api/contractors');
        if (response.ok) {
          const data = await response.json();
          setContractors(data);
        }
      } catch (error) {
        console.error('Error fetching contractors:', error);
      } finally {
        setContractorsLoading(false);
      }
    };

    fetchCategories();
    fetchContractors();
  }, [loggedInClient]);

  // Fetch Projects when logged in
  useEffect(() => {
    if (loggedInClient) {
      const fetchProjects = async () => {
        try {
          const res = await fetch(`/api/client/${loggedInClient.id}/projects`);
          if (res.ok) {
            const data = await res.json();
            setClientProjects(data);
          }
        } catch (e) {
          console.error(e);
        }
      };
      fetchProjects();
    }
  }, [loggedInClient]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: loginPhone })
      });
      if (res.ok) {
        const data = await res.json();
        setLoggedInClient(data.client);
      } else if (res.status === 404) {
        setRegData(prev => ({ ...prev, phone: loginPhone }));
        setIsRegistering(true);
      } else {
        setAuthError('Login failed. Please try again.');
      }
    } catch (e) {
      setAuthError('Network error connecting to server.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);
    try {
      const res = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(regData)
      });
      if (res.ok) {
        const data = await res.json();
        setLoggedInClient(data.client);
        setIsRegistering(false);
      } else {
        const err = await res.json();
        setAuthError(err.detail || 'Registration failed.');
      }
    } catch (e) {
      setAuthError('Network error connecting to server.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    try {
      const res = await fetch(`/api/client/${loggedInClient.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editData.name,
          last_name: editData.last_name,
          email: editData.email,
          address: editData.address,
          additional_phone: editData.additional_phone
        })
      });
      if (res.ok) {
        setLoggedInClient({ ...loggedInClient, ...editData });
        setIsEditingProfile(false);
      } else {
        alert('Failed to update profile');
      }
    } catch (e) {
      alert('Network error connecting to server.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImage(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if ((!input.trim() && !image) || isLoading) return;

    const userMessage = input.trim();
    const currentImage = image;

    setMessages(prev => [...prev, { role: 'user', content: userMessage, image: currentImage }]);
    setInput('');
    setImage(null);
    setIsLoading(true);

    try {
      const response = await fetch('/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId,
          user_id: loggedInClient ? loggedInClient.id : null,
          image: currentImage
        }),
      });

      if (!response.ok) throw new Error('Network error');
      const data = await response.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: '❌ **Error**: Could not connect to the wizard backend server. Please verify the backend is running.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const getCategoryIcon = (name) => {
    const lowerName = name.toLowerCase();
    if (lowerName.includes('plumb')) return <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>;
    if (lowerName.includes('electric')) return <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>;
    if (lowerName.includes('construct')) return <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>;
    return <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>;
  };

  const filteredCategories = categories.filter(cat =>
    cat.name.toLowerCase().includes(categorySearch.toLowerCase()) ||
    cat.description.toLowerCase().includes(categorySearch.toLowerCase()) ||
    cat.subcategories.some(sub => sub.name.toLowerCase().includes(categorySearch.toLowerCase()))
  );

  const filteredContractors = contractors.filter(con => {
    const matchesSearch = con.first_name.toLowerCase().includes(contractorSearch.toLowerCase()) || con.description.toLowerCase().includes(contractorSearch.toLowerCase());
    if (selectedCategoryFilter) return matchesSearch && con.description.toLowerCase().includes(selectedCategoryFilter.toLowerCase());
    return matchesSearch;
  });

  // --- Auth Screens ---
  if (!loggedInClient) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-header">
            <span className="logo-emoji">👷‍♂️</span>
            <h2>HandyBid Pro</h2>
            <p>{isRegistering ? 'Create your profile to continue' : 'Enter your phone number to sign in'}</p>
          </div>

          {authError && <div className="auth-error">{authError}</div>}

          {!isRegistering ? (
            <form onSubmit={handleLogin} className="auth-form">
              <div className="input-group">
                <label>Phone Number</label>
                <input
                  type="tel"
                  placeholder="e.g., +1 234 567 8900"
                  value={loginPhone}
                  onChange={(e) => setLoginPhone(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <button type="submit" className="btn-primary auth-btn" disabled={authLoading}>
                {authLoading ? 'Verifying...' : 'Sign In'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="auth-form register-form">
              <div className="input-row">
                <div className="input-group">
                  <label>First Name *</label>
                  <input type="text" value={regData.name} onChange={e => setRegData({ ...regData, name: e.target.value })} required autoFocus />
                </div>
                <div className="input-group">
                  <label>Last Name *</label>
                  <input type="text" value={regData.last_name} onChange={e => setRegData({ ...regData, last_name: e.target.value })} required />
                </div>
              </div>
              <div className="input-row">
                <div className="input-group">
                  <label>Phone *</label>
                  <input type="tel" value={regData.phone} onChange={e => setRegData({ ...regData, phone: e.target.value })} required />
                </div>
                <div className="input-group">
                  <label>Alt Phone</label>
                  <input type="tel" value={regData.additional_phone} onChange={e => setRegData({ ...regData, additional_phone: e.target.value })} />
                </div>
              </div>
              <div className="input-group">
                <label>Email *</label>
                <input type="email" value={regData.email} onChange={e => setRegData({ ...regData, email: e.target.value })} required />
              </div>
              <div className="input-group">
                <label>Address *</label>
                <input type="text" value={regData.address} onChange={e => setRegData({ ...regData, address: e.target.value })} required />
              </div>

              <div className="auth-actions">
                <button type="button" className="btn-secondary auth-btn" onClick={() => setIsRegistering(false)}>Back</button>
                <button type="submit" className="btn-primary auth-btn" disabled={authLoading}>
                  {authLoading ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    );
  }

  // --- Main App ---
  return (
    <div className="app-container with-sidebar">
      {/* Gemini-style Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="user-profile" onClick={() => { setIsEditingProfile(true); setEditData({ ...loggedInClient }); }} style={{ cursor: 'pointer' }}>
            <div className="avatar small">{loggedInClient.name[0]}</div>
            <div className="user-info">
              <span className="user-name">{loggedInClient.name} {loggedInClient.last_name}</span>
            </div>
          </div>
          <button className="logout-btn" onClick={() => setLoggedInClient(null)} title="Sign out">
            <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
          </button>
        </div>

        <div className="sidebar-content">
          <h3 className="sidebar-title">Recent Projects</h3>
          {clientProjects.length === 0 ? (
            <div className="no-projects">No recent projects. Start a new request!</div>
          ) : (
            <div className="project-list">
              {clientProjects.map(p => (
                <div key={p.id} className="project-item">
                  <div className="project-icon">📝</div>
                  <div className="project-details">
                    <div className="project-desc">{p.description || 'New Project Request'}</div>
                    <div className="project-date">{new Date(p.created_date).toLocaleDateString()}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      <div className="main-content">
        <header className="header">
          <div className="logo-wrapper">
            <span className="logo-emoji">👷‍♂️</span>
            <div className="logo-text">
              <h2>HandyBid Pro</h2>
              <p>Smart Handyman Tenders & Matching</p>
            </div>
          </div>

          <nav className="nav-tabs">
            <button className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>💬 AI Bid Wizard</button>
            <button className={`nav-tab ${activeTab === 'directory' ? 'active' : ''}`} onClick={() => setActiveTab('directory')}>🗂️ Categories</button>
            <button className={`nav-tab ${activeTab === 'testing' ? 'active' : ''}`} onClick={() => setActiveTab('testing')}>🧪 Testing</button>
          </nav>
        </header>

        {activeTab === 'chat' && (
          <main className="chat-container">
            {messages.length === 1 && (
              <div className="welcome-screen">
                <h1>Hello, {loggedInClient.name}!</h1>
                <p>Describe your issue, and our AI Wizard will categorize it, draft the tender, and match you with active contractors instantly.</p>
              </div>
            )}

            <div className="messages-list">
              {messages.map((msg, index) => (
                <div key={index} className={`message-wrapper ${msg.role}`}>
                  <div className="message-content">
                    <div className="avatar">
                      {msg.role === 'assistant' ? '✨' : loggedInClient.name[0]}
                    </div>
                    <div className="text-bubble">
                      {msg.image && (
                        <div style={{ marginBottom: '12px' }}>
                          <img src={msg.image} alt="Upload" style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '8px' }} />
                        </div>
                      )}
                      {msg.content.split('\n').map((line, i) => {
                        let parsedLine = line;
                        const boldRegex = /\*\*(.*?)\*\*/g;
                        const parts = [];
                        let lastIndex = 0;
                        let match;

                        while ((match = boldRegex.exec(line)) !== null) {
                          if (match.index > lastIndex) parts.push(line.substring(lastIndex, match.index));
                          parts.push(<strong key={match.index}>{match[1]}</strong>);
                          lastIndex = boldRegex.lastIndex;
                        }
                        if (lastIndex < line.length) parts.push(line.substring(lastIndex));
                        return <span key={i}>{parts.length > 0 ? parts : parsedLine}<br /></span>;
                      })}
                    </div>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="message-wrapper assistant">
                  <div className="message-content">
                    <div className="avatar">✨</div>
                    <div className="text-bubble typing">
                      <span className="dot"></span><span className="dot"></span><span className="dot"></span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="input-area">
              <form onSubmit={handleSubmit} className="input-form">
                <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Describe your request..." disabled={isLoading} autoFocus />
                <button type="submit" className="submit-btn" disabled={!input.trim() || isLoading}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
              </form>
            </div>
          </main>
        )}
        
        {activeTab === 'directory' && (
          <main className="directory-container">
            <section className="directory-sidebar">
              <div className="search-box">
                <h3>🔍 Categories</h3>
                <input type="text" placeholder="Search..." value={categorySearch} onChange={(e) => setCategorySearch(e.target.value)} className="directory-search-input" />
              </div>
              {categoriesLoading ? <div className="loader-box">Loading...</div> : (
                <div className="categories-list-grid">
                  {filteredCategories.map(cat => (
                    <div key={cat.id} className={`category-card ${selectedCategoryFilter === cat.name ? 'selected' : ''}`} onClick={() => setSelectedCategoryFilter(selectedCategoryFilter === cat.name ? null : cat.name)}>
                      <div className="cat-card-header">{getCategoryIcon(cat.name)}<h4>{cat.name}</h4></div>
                      <p className="cat-desc">{cat.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>
            <section className="directory-content">
              <div className="search-box text-right">
                <div className="contractors-header-row">
                  <h3>👷‍♂️ Contractors</h3>
                  <input type="text" placeholder="Search contractors..." value={contractorSearch} onChange={(e) => setContractorSearch(e.target.value)} className="directory-search-input max-w-250" />
                </div>
              </div>
              {contractorsLoading ? <div className="loader-box">Loading...</div> : (
                <div className="contractors-grid">
                  {filteredContractors.map(con => (
                    <div key={con.id} className="contractor-card">
                      <div className="contractor-header">
                        <div className="contractor-meta">
                          <h4>{con.first_name} {con.last_name}</h4>
                        </div>
                      </div>
                      <div className="contractor-body"><p className="contractor-desc">{con.description}</p></div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </main>
        )}

        {activeTab === 'testing' && (
          <TestingDashboard />
        )}
      </div>

      {isEditingProfile && (
        <div className="auth-container" style={{ position: 'fixed', top: 0, left: 0, zIndex: 1000, background: 'rgba(7, 10, 19, 0.8)' }}>
          <div className="auth-card">
            <div className="auth-header">
              <h2>Edit Profile</h2>
            </div>
            <form onSubmit={handleUpdateProfile} className="auth-form register-form">
              <div className="input-row">
                <div className="input-group">
                  <label>First Name *</label>
                  <input type="text" value={editData.name} onChange={e => setEditData({ ...editData, name: e.target.value })} required autoFocus />
                </div>
                <div className="input-group">
                  <label>Last Name *</label>
                  <input type="text" value={editData.last_name} onChange={e => setEditData({ ...editData, last_name: e.target.value })} required />
                </div>
              </div>
              <div className="input-group">
                <label>Alt Phone</label>
                <input type="tel" value={editData.additional_phone || ''} onChange={e => setEditData({ ...editData, additional_phone: e.target.value })} />
              </div>
              <div className="input-group">
                <label>Email *</label>
                <input type="email" value={editData.email} onChange={e => setEditData({ ...editData, email: e.target.value })} required />
              </div>
              <div className="input-group">
                <label>Address *</label>
                <input type="text" value={editData.address} onChange={e => setEditData({ ...editData, address: e.target.value })} required />
              </div>

              <div className="auth-actions">
                <button type="button" className="btn-secondary auth-btn" onClick={() => setIsEditingProfile(false)}>Cancel</button>
                <button type="submit" className="btn-primary auth-btn" disabled={authLoading}>
                  {authLoading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
