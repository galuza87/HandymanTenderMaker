import { useState, useRef, useEffect } from 'react'
import './App.css'

function App() {
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
    scrollToBottom();
  }, [messages]);

  // Fetch Categories & Contractors from SQL Server Backend
  useEffect(() => {
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
  }, []);

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

  // Icon selector based on category name
  const getCategoryIcon = (name) => {
    const lowerName = name.toLowerCase();
    if (lowerName.includes('plumb')) {
      return (
        <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
        </svg>
      );
    }
    if (lowerName.includes('electric')) {
      return (
        <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      );
    }
    if (lowerName.includes('construct')) {
      return (
        <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      );
    }
    if (lowerName.includes('carpen')) {
      return (
        <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.77 3.77z" />
        </svg>
      );
    }
    if (lowerName.includes('roof')) {
      return (
        <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
      );
    }
    if (lowerName.includes('fixing') || lowerName.includes('repair')) {
      return (
        <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      );
    }
    if (lowerName.includes('install')) {
      return (
        <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    }
    if (lowerName.includes('mov') || lowerName.includes('moov')) {
      return (
        <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
        </svg>
      );
    }
    return (
      <svg className="cat-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
      </svg>
    );
  };

  // Filter categories and contractors based on search term
  const filteredCategories = categories.filter(cat => 
    cat.name.toLowerCase().includes(categorySearch.toLowerCase()) || 
    cat.description.toLowerCase().includes(categorySearch.toLowerCase()) ||
    cat.subcategories.some(sub => 
      sub.name.toLowerCase().includes(categorySearch.toLowerCase()) ||
      (sub.brand && sub.brand.toLowerCase().includes(categorySearch.toLowerCase()))
    )
  );

  const filteredContractors = contractors.filter(con => {
    const matchesSearch = 
      con.first_name.toLowerCase().includes(contractorSearch.toLowerCase()) ||
      con.last_name.toLowerCase().includes(contractorSearch.toLowerCase()) ||
      con.description.toLowerCase().includes(contractorSearch.toLowerCase()) ||
      con.email.toLowerCase().includes(contractorSearch.toLowerCase());
      
    if (selectedCategoryFilter) {
      // Filter contractors by category name keyword in description
      return matchesSearch && con.description.toLowerCase().includes(selectedCategoryFilter.toLowerCase());
    }
    return matchesSearch;
  });

  return (
    <div className="app-container">
      <header className="header">
        <div className="logo-wrapper">
          <span className="logo-emoji">👷‍♂️</span>
          <div className="logo-text">
            <h2>HandyBid Pro</h2>
            <p>Smart Handyman Tenders & Matching</p>
          </div>
        </div>
        
        <nav className="nav-tabs">
          <button 
            className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`} 
            onClick={() => setActiveTab('chat')}
          >
            💬 AI Bid Wizard
          </button>
          <button 
            className={`nav-tab ${activeTab === 'directory' ? 'active' : ''}`} 
            onClick={() => setActiveTab('directory')}
          >
            🗂️ Categories & Contractors
          </button>
        </nav>
      </header>

      {activeTab === 'chat' ? (
        /* ==================== AI CHAT WIZARD TAB ==================== */
        <main className="chat-container">
          {messages.length === 1 && (
            <div className="welcome-screen">
              <h1>Build a Handyman Request</h1>
              <p>Describe your issue, and our AI Wizard will categorize it, draft the tender, and match you with active contractors instantly.</p>
            </div>
          )}

          <div className="messages-list">
            {messages.map((msg, index) => (
              <div key={index} className={`message-wrapper ${msg.role}`}>
                <div className="message-content">
                  <div className="avatar">
                    {msg.role === 'assistant' ? '✨' : '👤'}
                  </div>
                  <div className="text-bubble">
                    {msg.image && (
                      <div style={{ marginBottom: '12px' }}>
                        <img src={msg.image} alt="Upload" style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '8px' }} />
                      </div>
                    )}
                    {msg.content.split('\n').map((line, i) => {
                      // Check for bold markdown
                      let parsedLine = line;
                      const boldRegex = /\*\*(.*?)\*\*/g;
                      const parts = [];
                      let lastIndex = 0;
                      let match;
                      
                      while ((match = boldRegex.exec(line)) !== null) {
                        if (match.index > lastIndex) {
                          parts.push(line.substring(lastIndex, match.index));
                        }
                        parts.push(<strong key={match.index}>{match[1]}</strong>);
                        lastIndex = boldRegex.lastIndex;
                      }
                      
                      if (lastIndex < line.length) {
                        parts.push(line.substring(lastIndex));
                      }
                      
                      // Code block detection
                      if (line.startsWith('```')) {
                        return null; // Handle code blocks with pre tags if needed
                      }

                      return (
                        <span key={i}>
                          {parts.length > 0 ? parts : parsedLine}
                          <br />
                        </span>
                      );
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
                    <span className="dot"></span>
                    <span className="dot"></span>
                    <span className="dot"></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            {image && (
              <div style={{ padding: '8px', background: 'var(--bg-surface)', borderRadius: '12px', border: '1px solid var(--border-color)', marginBottom: '10px', display: 'flex', alignItems: 'flex-start', gap: '10px', position: 'relative' }}>
                <img src={image} alt="Preview" style={{ height: '60px', borderRadius: '6px' }} />
                <button onClick={() => setImage(null)} style={{ background: 'rgba(239, 68, 68, 0.2)', border: 'none', color: '#ef4444', borderRadius: '50%', width: '24px', height: '24px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'absolute', top: '4px', right: '4px' }}>✕</button>
              </div>
            )}
            <form onSubmit={handleSubmit} className="input-form">
              <input 
                type="file" 
                accept="image/*" 
                style={{ display: 'none' }} 
                ref={fileInputRef} 
                onChange={handleImageUpload} 
              />
              <button 
                type="button" 
                onClick={() => fileInputRef.current?.click()} 
                style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '0 8px', display: 'flex', alignItems: 'center' }}
                title="Upload Image"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                  <circle cx="8.5" cy="8.5" r="1.5"></circle>
                  <polyline points="21 15 16 10 5 21"></polyline>
                </svg>
              </button>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Describe your request (e.g. 'I need to repair my Bosch dishwasher')..."
                disabled={isLoading}
                autoFocus
              />
              <button type="submit" className="submit-btn" disabled={(!input.trim() && !image) || isLoading}>
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
              </button>
            </form>
            <div className="disclaimer">
              Powered by Microsoft SQL Server & BuildWizard AI. Live matchmaking ready.
            </div>
          </div>
        </main>
      ) : (
        /* ==================== DIRECTORY TAB ==================== */
        <main className="directory-container">
          <section className="directory-sidebar">
            <div className="search-box">
              <h3>🔍 Handyman Categories</h3>
              <p className="section-subtitle">Real-time categories in SQL database</p>
              <input 
                type="text" 
                placeholder="Search categories & subcategories..." 
                value={categorySearch} 
                onChange={(e) => setCategorySearch(e.target.value)}
                className="directory-search-input"
              />
            </div>

            {categoriesLoading ? (
              <div className="loader-box">Loading SQL categories...</div>
            ) : (
              <div className="categories-list-grid">
                {filteredCategories.map(cat => (
                  <div 
                    key={cat.id} 
                    className={`category-card ${selectedCategoryFilter === cat.name ? 'selected' : ''}`}
                    onClick={() => {
                      if (selectedCategoryFilter === cat.name) {
                        setSelectedCategoryFilter(null); // Deselect
                      } else {
                        setSelectedCategoryFilter(cat.name);
                      }
                    }}
                  >
                    <div className="cat-card-header">
                      {getCategoryIcon(cat.name)}
                      <h4>{cat.name}</h4>
                    </div>
                    <p className="cat-desc">{cat.description}</p>
                    <div className="sub-badge-container">
                      {cat.subcategories.slice(0, 4).map(sub => (
                        <span key={sub.id} className="sub-badge">
                          {sub.name} {sub.brand ? `(${sub.brand})` : ''}
                        </span>
                      ))}
                      {cat.subcategories.length > 4 && (
                        <span className="sub-badge more">+{cat.subcategories.length - 4} more</span>
                      )}
                    </div>
                  </div>
                ))}
                {filteredCategories.length === 0 && (
                  <div className="no-results">No categories found matching "{categorySearch}"</div>
                )}
              </div>
            )}
          </section>

          <section className="directory-content">
            <div className="search-box text-right">
              <div className="contractors-header-row">
                <div>
                  <h3>👷‍♂️ Registered Contractors</h3>
                  <p className="section-subtitle">
                    {selectedCategoryFilter 
                      ? `Showing experts in "${selectedCategoryFilter}"` 
                      : 'All available professional handymen'}
                  </p>
                </div>
                <div className="flex-row gap-10">
                  {selectedCategoryFilter && (
                    <button className="clear-filter-btn" onClick={() => setSelectedCategoryFilter(null)}>
                      Clear Category Filter ✕
                    </button>
                  )}
                  <input 
                    type="text" 
                    placeholder="Search by contractor name or skill..." 
                    value={contractorSearch} 
                    onChange={(e) => setContractorSearch(e.target.value)}
                    className="directory-search-input max-w-250"
                  />
                </div>
              </div>
            </div>

            {contractorsLoading ? (
              <div className="loader-box">Loading active contractors...</div>
            ) : (
              <div className="contractors-grid">
                {filteredContractors.map(con => (
                  <div key={con.id} className="contractor-card">
                    <div className="contractor-header">
                      <img 
                        src={con.photo || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&fit=crop"} 
                        alt={`${con.first_name} ${con.last_name}`}
                        className="contractor-avatar" 
                      />
                      <div className="contractor-meta">
                        <h4>{con.first_name} {con.last_name}</h4>
                        <span className="contractor-email">{con.email}</span>
                      </div>
                    </div>
                    
                    <div className="contractor-body">
                      <p className="contractor-desc">{con.description}</p>
                    </div>

                    <div className="contractor-footer">
                      <a href={`mailto:${con.email}`} className="btn-secondary">
                        📧 Contact
                      </a>
                      <button 
                        className="btn-primary" 
                        onClick={() => {
                          alert(`Request sent to ${con.first_name}! They will get in touch with you shortly.`);
                        }}
                      >
                        ⚡ Hire Me
                      </button>
                    </div>
                  </div>
                ))}
                {filteredContractors.length === 0 && (
                  <div className="no-results">
                    No contractors found. {selectedCategoryFilter && 'Try clearing the category filter.'}
                  </div>
                )}
              </div>
            )}
          </section>
        </main>
      )}
    </div>
  )
}

export default App
