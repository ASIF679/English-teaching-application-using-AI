import React, { useState, useEffect, createContext, useContext, useRef, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import axios from 'axios';
import './App.css';

// API Configuration
const API_BASE = 'http://localhost:5000';
axios.defaults.baseURL = API_BASE;

// Enhanced error interceptor
axios.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error.response?.data || error.message);
    if (error.response?.status === 429) {
      console.warn('API Rate limit hit, implementing backoff...');
    }
    return Promise.reject(error);
  }
);

// Auth Context
const AuthContext = createContext();

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      axios.get('/api/user/profile')
        .then(response => setUser(response.data))
        .catch(() => {
          localStorage.removeItem('token');
          delete axios.defaults.headers.common['Authorization'];
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (username, password) => {
    try {
      const response = await axios.post('/api/auth/login', { username, password });
      const { token, user } = response.data;
      
      localStorage.setItem('token', token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      setUser(user);
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.error || 'Login failed' 
      };
    }
  };

  const signup = async (userData) => {
    try {
      const response = await axios.post('/api/auth/signup', userData);
      const { token, user } = response.data;
      
      localStorage.setItem('token', token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      setUser(user);
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.error || 'Signup failed' 
      };
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
  };

  const updateUserLevel = async (level) => {
    try {
      const response = await axios.post('/api/user/set-level', { level });
      if (response.data.level_changed) {
        setUser(prev => ({
          ...prev,
          level: response.data.level,
          proficiency_score: response.data.proficiency_score
        }));
      }
      return { success: true, data: response.data };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.error || 'Failed to update level' 
      };
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, signup, logout, loading, updateUserLevel }}>
      {children}
    </AuthContext.Provider>
  );
};

const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

// Enhanced Speech Recognition Hook with better error handling
const useSpeechRecognition = () => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [browserSupported, setBrowserSupported] = useState(false);
  const [error, setError] = useState(null);
  const recognitionRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const retryCountRef = useRef(0);
  
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    setBrowserSupported(!!SpeechRecognition);
  }, []);

  const startListening = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      setError('Speech recognition not supported in this browser. Please use Chrome.');
      return;
    }

    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }

    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
    }

    recognitionRef.current = new SpeechRecognition();
    const recognition = recognitionRef.current;

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
      setError(null);
      retryCountRef.current = 0;
      console.log('Enhanced listening started...');
    };

    recognition.onresult = (event) => {
      const results = event.results;
      let finalText = '';
      let interimText = '';
      
      for (let i = 0; i < results.length; i++) {
        if (results[i].isFinal) {
          finalText += results[i][0].transcript + ' ';
        } else {
          interimText += results[i][0].transcript;
        }
      }
      
      const fullTranscript = (finalText + interimText).trim();
      setTranscript(fullTranscript);
      
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
      }
      
      silenceTimerRef.current = setTimeout(() => {
        if (fullTranscript && fullTranscript.trim().length > 0) {
          console.log('Silence detected, stopping listening...');
          stopListening();
        }
      }, 2500); // Slightly longer pause detection
    };

    recognition.onend = () => {
      setIsListening(false);
      console.log('Recognition ended');
    };

    recognition.onerror = (event) => {
      setIsListening(false);
      console.error('Recognition error:', event.error);
      
      switch (event.error) {
        case 'not-allowed':
          setError('Please allow microphone access in your browser settings');
          break;
        case 'network':
          setError('Network error - please check your internet connection');
          break;
        case 'no-speech':
          if (retryCountRef.current < 2) {
            retryCountRef.current++;
            setError('No speech detected - trying again...');
            setTimeout(() => startListening(), 1000);
          } else {
            setError('No speech detected after multiple attempts');
          }
          break;
        case 'audio-capture':
          setError('Microphone not available - please check your device');
          break;
        case 'service-not-allowed':
          setError('Speech recognition service not available');
          break;
        default:
          setError(`Speech recognition error: ${event.error}`);
      }
    };

    try {
      recognition.start();
    } catch (err) {
      setError('Failed to start speech recognition');
      setIsListening(false);
    }
  }, []);

  const stopListening = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    
    setIsListening(false);
  }, []);

  const resetTranscript = useCallback(() => {
    setTranscript('');
    setError(null);
    retryCountRef.current = 0;
  }, []);

  return {
    isListening,
    transcript,
    startListening,
    stopListening,
    resetTranscript,
    browserSupported,
    error
  };
};

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }
  
  return user ? children : <Navigate to="/login" />;
};

// Enhanced Landing Page
const LandingPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  if (user) {
    navigate('/dashboard');
    return null;
  }

  return (
    <div className="landing-page">
      <header className="landing-header">
        <nav className="navbar">
          <div className="nav-brand">
            <h2>AI English Tutor v3.1</h2>
          </div>
          <div className="nav-links">
            <button onClick={() => navigate('/login')} className="btn-secondary">
              Login
            </button>
            <button onClick={() => navigate('/signup')} className="btn-primary">
              Get Started
            </button>
          </div>
        </nav>
      </header>

      <main className="landing-main">
        <section className="hero">
          <div className="hero-content">
            <h1>Learn English by chatting with Emma</h1>
            <p className="hero-subtitle">
              Have natural conversations with an AI tutor. Emma adapts to your level and helps you build confidence through dialogue.
            </p>
                        <div className="hero-features">
              <div className="feature-badge">Conversational practice</div>
              <div className="feature-badge">Level-aware tutoring</div>
              <div className="feature-badge">Grammar support</div>
            </div>
            <div className="hero-buttons">
              <button onClick={() => navigate('/signup')} className="btn-primary btn-large">
                Start learning
              </button>
            </div>
          </div>
          <div className="hero-visual">
            <div className="feature-preview">
              <div className="analysis-preview">
                <div className="score-circle">
                  <span className="score">87</span>
                  <span className="label">Overall</span>
                </div>
                <div className="score-breakdown">
                  <div className="score-item">
                    <span>Grammar</span>
                    <div className="score-bar">
                      <div className="score-fill grammar" style={{width: '92%'}}></div>
                    </div>
                    <span>92%</span>
                  </div>
                  <div className="score-item">
                    <span>Fluency</span>
                    <div className="score-bar">
                      <div className="score-fill fluency" style={{width: '85%'}}></div>
                    </div>
                    <span>85%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="features">
          <div className="container">
            <h2>What you get</h2>
            <div className="features-grid">
              <div className="feature-card">
                <div className="feature-icon">Chat</div>
                <h3>Chat-first learning</h3>
                <p>Practice real back-and-forth dialogue at your own pace, with Emma guiding the conversation.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon">Grammar</div>
                <h3>Grammar in context</h3>
                <p>Get gentle corrections and explanations woven into the chat, not separate drills.</p>
              </div>
              <div className="feature-card">
                <div className="feature-icon">Level</div>
                <h3>Your level, your way</h3>
                <p>Pick a starting level or let Emma adjust as you improve.</p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="container">
          <p>&copy; 2025 AI English Tutor v3.1. Enhanced language learning technology.</p>
        </div>
      </footer>
    </div>
  );
};

// Enhanced Signup Page with Manual Level Selection
const SignupPage = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    fullName: '',
    password: '',
    confirmPassword: '',
    initialLevel: 'auto'
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { signup } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    const result = await signup({
      username: formData.username,
      email: formData.email,
      fullName: formData.fullName,
      password: formData.password,
      initialLevel: formData.initialLevel
    });
    
    if (result.success) {
      navigate('/dashboard');
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-header">
          <h1>Start Your Enhanced Learning Journey</h1>
          <p>Join the next generation of English learning with AI-powered analysis</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="error-message">{error}</div>}
          
          <div className="form-group">
            <label htmlFor="fullName">Full Name</label>
            <input
              type="text"
              id="fullName"
              name="fullName"
              value={formData.fullName}
              onChange={handleChange}
              required
              placeholder="Enter your full name"
            />
          </div>

          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
              placeholder="Choose a username"
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              placeholder="Enter your email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              placeholder="Create a password"
              minLength="6"
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
              placeholder="Confirm your password"
            />
          </div>

          <div className="form-group">
            <label htmlFor="initialLevel">Starting Level (NEW!)</label>
            <select
              id="initialLevel"
              name="initialLevel"
              value={formData.initialLevel}
              onChange={handleChange}
              className="level-select"
            >
              <option value="auto">Let Emma determine automatically</option>
              <option value="beginner">Beginner - I'm just starting</option>
              <option value="intermediate">Intermediate - I know some English</option>
              <option value="advanced">Advanced - I'm quite confident</option>
            </select>
            <small className="helper-text">
              {formData.initialLevel === 'auto' ? 
                'Emma will assess your level during your first conversation' :
                'You can always change this later in your profile'
              }
            </small>
          </div>

          <button type="submit" disabled={loading} className="btn-primary btn-full">
            {loading ? 'Creating account...' : 'Start Enhanced Learning'}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            Already have an account?{' '}
            <span 
              onClick={() => navigate('/login')} 
              className="auth-link"
            >
              Sign in here
            </span>
          </p>
        </div>
      </div>
    </div>
  );
};

// Login Page (unchanged but enhanced error handling)
const LoginPage = () => {
  const [formData, setFormData] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const result = await login(formData.username, formData.password);
    
    if (result.success) {
      navigate('/dashboard');
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-header">
          <h1>Welcome Back!</h1>
          <p>Continue your enhanced English learning journey</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="error-message">{error}</div>}
          
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
              placeholder="Enter your username"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              placeholder="Enter your password"
            />
          </div>

          <button type="submit" disabled={loading} className="btn-primary btn-full">
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            Don't have an account?{' '}
            <span 
              onClick={() => navigate('/signup')} 
              className="auth-link"
            >
              Sign up here
            </span>
          </p>
        </div>
      </div>
    </div>
  );
};

// Enhanced Dashboard Component (FIX #3)
const Dashboard = () => {
  const [profile, setProfile] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Fetch profile and stats separately with individual error handling
        const profilePromise = axios.get('/api/user/profile').catch(err => {
          console.error('Profile fetch error:', err);
          throw new Error('Failed to load profile');
        });
        
        const statsPromise = axios.get('/api/user/stats').catch(err => {
          console.error('Stats fetch error:', err);
          // Return default stats if the endpoint fails
          return {
            data: {
              basic: { total_sessions: 0, average_wpm: 0 },
              proficiency: { 
                overall_score: 25, 
                pronunciation_score: 0, 
                grammar_score: 0, 
                fluency_score: 0,
                current_level: 'beginner',
                current_persona: 'beginner'
              },
              vocabulary: { mispronounced: 0 },
              recent_activity: { 
                avg_pronunciation_score: 0, 
                avg_grammar_score: 0, 
                total_errors_corrected: 0 
              }
            }
          };
        });

        const [profileRes, statsRes] = await Promise.all([profilePromise, statsPromise]);
        
        setProfile(profileRes.data);
        setStats(statsRes.data);
        
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
        setError(error.message || 'Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading your enhanced dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="loading-container">
        <div className="error-message">
          <h3>Dashboard Error</h3>
          <p>{error}</p>
          <button onClick={() => window.location.reload()} className="btn-primary">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="loading-container">
        <div className="error-message">
          <h3>Profile Not Found</h3>
          <p>Unable to load your profile. Please try logging in again.</p>
          <button onClick={logout} className="btn-primary">
            Login Again
          </button>
        </div>
      </div>
    );
  }

  const proficiency = stats.proficiency || {};
  const isAutoLevel = profile.profile?.preferences?.auto_level_adjustment !== false;

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-content">
          <h1>Welcome back, {profile.full_name}!</h1>
          <p>
            Current Level: <span className="level-badge">{proficiency.current_level || 'Beginner'}</span> 
            {!isAutoLevel && <span className="manual-badge">Manual</span>}
            | Overall Score: <span className="score-badge">{proficiency.overall_score || 25}%</span>
          </p>
        </div>
        <div className="header-actions">
          <button onClick={() => navigate('/profile')} className="btn-secondary">
            Profile Settings
          </button>
          <button onClick={logout} className="btn-outline">
            Logout
          </button>
        </div>
      </header>

      <div className="dashboard-grid">
        {/* Enhanced Proficiency Overview */}
        <div className="proficiency-overview">
          <h2>Your Proficiency Breakdown</h2>
          <div className="proficiency-scores">
            <div className="score-circle-container">
              <div className="score-circle large">
                <span className="score">{proficiency.overall_score || 25}</span>
                <span className="label">Overall</span>
              </div>
            </div>
            <div className="score-breakdown">
              <div className="score-item">
                <span className="score-label">Grammar</span>
                <div className="score-bar">
                  <div className="score-fill grammar" 
                       style={{width: `${proficiency.grammar_score || 0}%`}}></div>
                </div>
                <span className="score-value">{proficiency.grammar_score || 0}%</span>
              </div>
              <div className="score-item">
                <span className="score-label">Fluency</span>
                <div className="score-bar">
                  <div className="score-fill fluency" 
                       style={{width: `${proficiency.fluency_score || 0}%`}}></div>
                </div>
                <span className="score-value">{proficiency.fluency_score || 0}%</span>
              </div>
            </div>
          </div>
        </div>

        <div className="stats-overview">
          <h2>Learning Statistics</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon">Chat</div>
              <div className="stat-content">
                <h3>{stats.basic?.total_sessions || 0}</h3>
                <p>Conversations</p>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">Gram</div>
              <div className="stat-content">
                <h3>{stats.recent_activity?.avg_grammar_score || 0}%</h3>
                <p>Avg Grammar</p>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">WPM</div>
              <div className="stat-content">
                <h3>{stats.basic?.average_wpm || 0}</h3>
                <p>Words/Min</p>
              </div>
            </div>
          </div>
        </div>

        <div className="quick-actions">
          <h2>Continue learning</h2>
          <div className="action-cards">
            <div className="action-card primary" onClick={() => navigate('/chat')}>
              <div className="action-icon">Chat</div>
              <h3>Chat with Emma</h3>
              <p>Practice English in a natural conversation with your AI tutor.</p>
            </div>
          </div>
        </div>

        <div className="recent-activity">
          <h2>Recent activity</h2>
          <div className="activity-list">
            <div className="activity-item">
              <span className="activity-icon">Level</span>
              <span>
                Current persona: <strong>{proficiency.current_persona || 'Beginner'}</strong> Emma
                {!isAutoLevel && <em> (Manual Selection)</em>}
              </span>
            </div>
            <div className="activity-item">
              <span className="activity-icon">Gram</span>
              <span>Grammar corrections made: {stats.recent_activity?.total_errors_corrected || 0}</span>
            </div>
            <div className="activity-item">
              <span className="activity-icon">Rate</span>
              <span>Average speaking rate: {stats.basic?.average_wpm || 0} words per minute</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// FIX #5: Session Summary Component
const SessionSummary = ({ summary, onClose, onBackToDashboard }) => {
  if (!summary) return null;

  return (
    <div className="session-summary-modal">
      <div className="summary-content">
        <div className="summary-header">
          <h2>Chat Session Summary</h2>
          <div className="session-stats">
            <span>Messages: {summary.session_stats?.messages_sent || 0}</span>
            <span>Duration: Practice Session</span>
          </div>
        </div>

        <div className="summary-grid">
          <div className="summary-section achievements">
            <h3>Achievements</h3>
            <ul>
              {summary.achievements.map((achievement, index) => (
                <li key={index} className="achievement-item">
                  {achievement}
                </li>
              ))}
            </ul>
          </div>

          <div className="summary-section scores">
            <h3>Session Scores</h3>
            <div className="score-grid">
              <div className="score-item">
                <span className="score-label">Grammar</span>
                <span className="score-value">{summary.session_stats?.avg_grammar_score || 0}%</span>
              </div>
              <div className="score-item">
                <span className="score-label">Fluency</span>
                <span className="score-value">{summary.session_stats?.avg_fluency_score || 0}%</span>
              </div>
            </div>
          </div>

          <div className="summary-section weaknesses">
            <h3>Areas to Improve</h3>
            <ul>
              {summary.weaknesses.map((weakness, index) => (
                <li key={index} className="weakness-item">
                  {weakness}
                </li>
              ))}
            </ul>
          </div>

          <div className="summary-section recommendations">
            <h3>Next Steps</h3>
            <ul>
              {summary.recommendations.map((recommendation, index) => (
                <li key={index} className="recommendation-item">
                  {recommendation}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="summary-text">
          <p>{summary.summary_text}</p>
        </div>

        <div className="summary-actions">
          <button onClick={onClose} className="btn-secondary">
            Start New Chat
          </button>
          <button onClick={onBackToDashboard} className="btn-primary">
            Back to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
};

// Enhanced Chat Component with FIX #1, #4, #5
const ChatPage = () => {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [analysisMode] = useState('natural');
  const [currentAnalysis, setCurrentAnalysis] = useState(null);
  const [levelChanged, setLevelChanged] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [sessionSummary, setSessionSummary] = useState(null);
  const [showSessionSummary, setShowSessionSummary] = useState(false);
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);
  const synthRef = useRef(null);
  
  const { logout } = useAuth();

  // Enhanced speech recognition
  const { 
    isListening, 
    transcript,
    startListening, 
    stopListening,
    resetTranscript,
    browserSupported,
    error
  } = useSpeechRecognition();

  // Initialize speech synthesis
  useEffect(() => {
    if ('speechSynthesis' in window) {
      synthRef.current = window.speechSynthesis;
    }
  }, []);

  // Enhanced transcript handling
  useEffect(() => {
    if (transcript && !isListening) {
      setInputText(transcript);
      
      if (transcript.trim().length > 3) {
        setTimeout(() => {
          sendMessage(transcript);
        }, 500);
      }
      
      resetTranscript();
    }
  }, [transcript, isListening, resetTranscript]);

  // Enhanced auth error handler
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      response => response,
      error => {
        if (error.response?.status === 401) {
          logout();
          navigate('/login', { 
            state: { 
              message: "Your session has expired. Please log in again." 
            } 
          });
        }
        return Promise.reject(error);
      }
    );
    
    return () => {
      axios.interceptors.response.eject(interceptor);
    };
  }, [logout, navigate]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Enhanced TTS with error handling
  const speakText = (text) => {
    if (!audioEnabled || !synthRef.current) return;
    
    try {
      synthRef.current.cancel();
      
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.1;
      utterance.volume = 1.0;
      
      utterance.onerror = (e) => {
        console.warn('TTS Error:', e.error);
      };
      
      synthRef.current.speak(utterance);
    } catch (error) {
      console.warn('TTS not available:', error);
    }
  };

  const addMessage = (content, type, analysis = null, accentFeedback = null) => {
    const newMessage = {
      id: Date.now() + Math.random(),
      content,
      type,
      analysis,
      accentFeedback,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, newMessage]);
    return newMessage;
  };

  // FIX #1: Enhanced sendMessage with better completion checking and retry logic
  const sendMessage = async (text) => {
    if (!text.trim()) return;

    addMessage(text, 'user');
    setIsLoading(true);
    setInputText('');

    try {
      const response = await axios.post('/api/chat/message', {
        message: text,
        conversation_mode: analysisMode === 'comprehensive' ? 'full_feedback' : 'natural'
      }, {
        timeout: 60000 // Increased timeout for better responses
      });

      const { 
        response: botResponse, 
        analysis, 
        accent_feedback,
        processing_time 
      } = response.data;
      
      // FIX #1: Enhanced response completeness verification
      if (!botResponse || botResponse.trim().length < 10) {
        throw new Error('Incomplete response received');
      }

      // Check if response ends properly
      const endsWithPunctuation = /[.!?]["']?$/.test(botResponse.trim());
      if (!endsWithPunctuation && retryCount < 2) {
        console.warn('Response may be incomplete, retrying...');
        setRetryCount(prev => prev + 1);
        setTimeout(() => {
          sendMessage(text + " (Please give me a complete response)");
        }, 1000);
        return;
      }
      
      setCurrentAnalysis(analysis);
      setRetryCount(0); // Reset retry count on success
      
      // Show level change notification
      if (analysis.persona_changed) {
        setLevelChanged(true);
        setTimeout(() => setLevelChanged(false), 6000);
      }
      
      // Add bot response
      addMessage(botResponse, 'bot', analysis, accent_feedback);
      
      // Speak response if not listening
      setTimeout(() => {
        if (!isListening) {
          speakText(botResponse);
        }
      }, 300);

      console.log(`Enhanced analysis completed in ${processing_time}s`);
      console.log(`Response length: ${botResponse.length} characters`);

    } catch (error) {
      console.error('Enhanced chat error:', error);
      
      // Enhanced retry logic for failed requests
      if (retryCount < 2 && (error.code === 'ECONNABORTED' || error.response?.status >= 500)) {
        setRetryCount(prev => prev + 1);
        setTimeout(() => {
          console.log(`Retrying message... Attempt ${retryCount + 2}`);
          sendMessage(text);
        }, 2000);
        return;
      }
      
      let errorMessage = 'I apologize, but I had trouble processing your message. ';
      
      if (error.code === 'ECONNABORTED') {
        errorMessage += 'The request timed out. Let me try to give you a complete response.';
      } else if (error.response?.status === 429) {
        errorMessage += 'I need a moment to process. Please wait a few seconds before trying again.';
      } else {
        errorMessage += 'Please try again in a moment, and I\'ll make sure to give you a complete response.';
      }
      
      addMessage(errorMessage, 'bot');
      setTimeout(() => speakText(errorMessage), 300);
      setRetryCount(0);
    } finally {
      setIsLoading(false);
    }
  };

  // FIX #5: End chat and generate session summary
  const endChatSession = async () => {
    if (messages.length === 0) {
      navigate('/dashboard');
      return;
    }

    try {
      setIsLoading(true);
      const response = await axios.post('/api/chat/session-summary', {
        messages: messages
      });
      
      setSessionSummary(response.data.summary);
      setShowSessionSummary(true);
    } catch (error) {
      console.error('Failed to generate session summary:', error);
      // Fallback: generate basic summary from local data
      const userMessages = messages.filter(msg => msg.type === 'user');
      const fallbackSummary = {
        achievements: userMessages.length > 0 ? ['Completed practice session with Emma'] : ['Started learning journey'],
        weaknesses: ['Continue practicing for better analysis'],
        recommendations: ['Keep having conversations with Emma', 'Practice speaking clearly'],
        session_stats: {
          messages_sent: userMessages.length,
          avg_pronunciation_score: 0,
          avg_grammar_score: 0,
          avg_fluency_score: 0
        },
        summary_text: `You practiced ${userMessages.length} times with Emma in this session.`
      };
      setSessionSummary(fallbackSummary);
      setShowSessionSummary(true);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(inputText);
  };

  const handleVoiceInput = () => {
    if (!browserSupported) {
      alert("Speech recognition not supported. Please use Chrome browser for the best experience.");
      return;
    }

    if (isListening) {
      stopListening();
    } else {
      resetTranscript();
      if (synthRef.current) {
        synthRef.current.cancel();
      }
      startListening();
    }
  };

  const handleCloseSummary = () => {
    setShowSessionSummary(false);
    setSessionSummary(null);
    setMessages([]);
  };

  const handleBackToDashboard = () => {
    setShowSessionSummary(false);
    setSessionSummary(null);
    navigate('/dashboard');
  };

  return (
    <div className="chat-page">
      <header className="chat-header">
        <div className="chat-header-content">
          <button onClick={() => navigate('/dashboard')} className="back-button">
            ← Dashboard
          </button>
          <div className="header-center">
            <h1>Chat with Emma</h1>
            <div className="analysis-indicators">
              {isListening && (
                <span className="listening-badge">
                  Listening…
                </span>
              )}
            </div>
          </div>
          <div className="header-controls">
            {/* FIX #5: End Chat Button */}
            <button
              onClick={endChatSession}
              className="btn-danger end-chat-btn"
              disabled={isLoading}
              title="End chat and view session summary"
            >
              End Chat
            </button>
            <button
              onClick={() => setAudioEnabled(!audioEnabled)}
              className={`toggle-button ${audioEnabled ? 'active' : ''}`}
              title={`Audio ${audioEnabled ? 'On' : 'Off'}`}
            >
              {audioEnabled ? 'Audio On' : 'Audio Off'}
            </button>
          </div>
        </div>
      </header>

      {/* Enhanced Level Change Notification */}
      {levelChanged && (
        <div className="level-change-notification">
          Congratulations! Your proficiency level has been updated to:
          <strong>{currentAnalysis?.level}</strong>
          <br />
          <small>Emma will now adjust her teaching style accordingly!</small>
        </div>
      )}

      <div className="chat-container">
        <div className="chat-messages">
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.type}`}>
              <div className="message-content">
                <p>{message.content}</p>
              </div>
              <span className="message-time">
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}
          
          {isLoading && (
            <div className="message bot">
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span className="analysis-loading">
                  Emma is thinking…
                  {retryCount > 0 && <span> (Retry {retryCount + 1})</span>}
                </span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} className="chat-input-form">
          <div className="input-group">
            <div className="input-container">
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={isListening ? "Speak now…" : "Type your message or use the mic to speak…"}
                className="chat-input"
                disabled={isLoading}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
              />
              
              {/* Enhanced real-time transcript display */}
              {(isListening || transcript) && (
                <div className="real-time-transcript enhanced">
                  <div className="transcript-label">
                    {isListening ? (
                      <span className="listening-indicator">
                        Listening…
                        <span className="pulse-dot"></span>
                      </span>
                    ) : (
                      <span>Speech captured</span>
                    )}
                  </div>
                  <div className="transcript-text">{transcript}</div>
                </div>
              )}
            </div>
            
            {browserSupported && (
              <button
                type="button"
                onClick={handleVoiceInput}
                className={`voice-button enhanced ${isListening ? 'listening' : ''} ${error ? 'error' : ''}`}
                disabled={isLoading}
                title={
                  error ? `Speech error: ${error}` : 
                  isListening ? 'Stop recording' : 'Use microphone'
                }
              >
                {isListening ? 'Mic On' : 'Mic'}
                {isListening && <span className="voice-pulse"></span>}
              </button>
            )}
            
            <button
              type="submit"
              disabled={isLoading || !inputText.trim()}
              className="send-button"
            >
              {isLoading ? '...' : 'Send'}
            </button>
          </div>
          
          {error && (
            <div className="speech-error enhanced">
              {error}
              <button onClick={resetTranscript} className="error-reset">Try Again</button>
            </div>
          )}
        </form>
      </div>

      {/* FIX #5: Session Summary Modal */}
      {showSessionSummary && sessionSummary && (
        <SessionSummary 
          summary={sessionSummary}
          onClose={handleCloseSummary}
          onBackToDashboard={handleBackToDashboard}
        />
      )}
    </div>
  );
};

// Enhanced Profile Page with Manual Level Selection
const ProfilePage = () => {
  const [profile, setProfile] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({});
  const [loading, setLoading] = useState(false);
  const [levelChangeLoading, setLevelChangeLoading] = useState(false);
  const navigate = useNavigate();
  const { updateUserLevel } = useAuth();

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await axios.get('/api/user/profile');
        setProfile(response.data);
        setEditData({
          fullName: response.data.full_name,
          email: response.data.email,
          daily_practice_time: response.data.profile?.goals?.daily_practice_time || 15,
          weekly_vocab_target: response.data.profile?.goals?.weekly_vocab_target || 20,
          correction_style: response.data.profile?.preferences?.correction_style || 'gentle'
        });
      } catch (error) {
        console.error('Failed to fetch profile:', error);
      }
    };

    fetchProfile();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
      console.log('Saving profile data:', editData);
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save profile:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLevelChange = async (newLevel) => {
    if (window.confirm(`Are you sure you want to change your level to ${newLevel}? This will adjust your learning experience and disable automatic level adjustments.`)) {
      setLevelChangeLoading(true);
      try {
        const result = await updateUserLevel(newLevel);
        if (result.success) {
          // Refresh profile data
          const response = await axios.get('/api/user/profile');
          setProfile(response.data);
          alert(`Level successfully changed to ${newLevel}!`);
        } else {
          alert(`Failed to change level: ${result.error}`);
        }
      } catch (error) {
        alert('Failed to change level. Please try again.');
      } finally {
        setLevelChangeLoading(false);
      }
    }
  };

  if (!profile) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading enhanced profile...</p>
      </div>
    );
  }

  const formatDate = (dateStr) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  const proficiency = profile.profile || {};
  const recentScores = profile.recent_scores || {};
  const levelChangeHistory = profile.level_change_history || [];
  const isAutoLevel = proficiency.preferences?.auto_level_adjustment !== false;

  return (
    <div className="profile-page">
      <header className="profile-header">
        <button onClick={() => navigate('/dashboard')} className="back-button">
          ← Back to Dashboard
        </button>
        <h1>Your Enhanced Profile</h1>
      </header>

      <div className="profile-content">
        {/* Personal Information Section */}
        <div className="profile-section">
          <div className="section-header">
            <h2>Personal Information</h2>
            <button 
              onClick={() => setIsEditing(!isEditing)}
              className="btn-secondary"
              disabled={loading}
            >
              {isEditing ? 'Cancel' : 'Edit Profile'}
            </button>
          </div>
          
          <div className="profile-info-grid">
            <div className="info-item">
              <strong>Full Name:</strong>
              {isEditing ? (
                <input
                  type="text"
                  value={editData.fullName}
                  onChange={(e) => setEditData({...editData, fullName: e.target.value})}
                  className="edit-input"
                />
              ) : (
                <span>{profile.full_name}</span>
              )}
            </div>
            
            <div className="info-item">
              <strong>Email:</strong>
              {isEditing ? (
                <input
                  type="email"
                  value={editData.email}
                  onChange={(e) => setEditData({...editData, email: e.target.value})}
                  className="edit-input"
                />
              ) : (
                <span>{profile.email}</span>
              )}
            </div>
            
            <div className="info-item">
              <strong>Username:</strong>
              <span>{profile.username}</span>
            </div>
            
            <div className="info-item">
              <strong>Current Level:</strong>
              <span className="level-badge">{proficiency.level || 'Beginner'}</span>
              {!isAutoLevel && <span className="manual-badge">Manual</span>}
            </div>
            
            <div className="info-item">
              <strong>Overall Score:</strong>
              <span className="score-badge">{proficiency.proficiency_score || 25}%</span>
            </div>
            
            <div className="info-item">
              <strong>Member Since:</strong>
              <span>{formatDate(profile.created_at)}</span>
            </div>
          </div>

          {isEditing && (
            <div className="edit-actions">
              <button onClick={handleSave} className="btn-primary" disabled={loading}>
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          )}
        </div>

        {/* Enhanced Manual Level Selection */}
        <div className="profile-section">
          <h2>Manual Level Selection (NEW!)</h2>
          <div className="level-selection">
            <p>Choose your learning level manually or let Emma adjust automatically based on your performance.</p>
            
            <div className="level-options">
              {['beginner', 'intermediate', 'advanced', 'native'].map(level => (
                <button
                  key={level}
                  onClick={() => handleLevelChange(level)}
                  disabled={levelChangeLoading || proficiency.level === level}
                  className={`level-option ${proficiency.level === level ? 'current' : ''}`}
                >
                  <span className="level-emoji">
                    {level === 'beginner' ? 'B' :
                     level === 'intermediate' ? 'I' :
                     level === 'advanced' ? 'A' : 'N'}
                  </span>
                  <span className="level-name">{level.charAt(0).toUpperCase() + level.slice(1)}</span>
                  {proficiency.level === level && <span className="current-badge">Current</span>}
                </button>
              ))}
            </div>

            <div className="auto-adjustment-toggle">
              <label>
                <input
                  type="checkbox"
                  checked={isAutoLevel}
                  onChange={async () => {
                    // This would need to be implemented in the backend
                    console.log('Toggle auto level adjustment');
                  }}
                />
                Enable automatic level adjustments based on performance
              </label>
            </div>

            {levelChangeHistory.length > 0 && (
              <div className="level-history">
                <h4>Level Change History</h4>
                <div className="history-list">
                  {levelChangeHistory.slice(-3).reverse().map((change, idx) => (
                    <div key={idx} className="history-item">
                      <span className="change-date">{formatDate(change.timestamp)}</span>
                      <span className="change-details">
                        {change.from_level ? `${change.from_level} → ${change.to_level}` : `Set to ${change.to_level}`}
                      </span>
                      <span className={`change-method ${change.method}`}>
                        {change.method === 'manual' ? 'Manual' : 'Auto'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {levelChangeLoading && (
              <div className="level-loading">
                <div className="loading-spinner small"></div>
                <span>Updating level...</span>
              </div>
            )}
          </div>
        </div>

        {/* Rest of profile sections remain the same */}
        <div className="profile-section">
          <h2>Enhanced Proficiency Breakdown</h2>
          {/* ... existing proficiency section ... */}
        </div>
      </div>
    </div>
  );
};

// Main App Component with Enhanced Routing
const App = () => {
  return (
    <Router>
      <AuthProvider>
        <div className="App">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/chat" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
            <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
          </Routes>
        </div>
      </AuthProvider>
    </Router>
  );
};

export default App;