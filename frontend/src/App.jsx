import { useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  // ==================================================
  // AUTHENTICATION
  // ==================================================

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState(localStorage.getItem("token"));

  // ==================================================
  // TICKETS
  // ==================================================

  const [tickets, setTickets] = useState([]);
  const [analyses, setAnalyses] = useState({});

  // ==================================================
  // LOADING / ERRORS
  // ==================================================

  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(null);
  const [updatingStatus, setUpdatingStatus] = useState(null);
  const [error, setError] = useState("");

  // ==================================================
  // CREATE TICKET
  // ==================================================

  const [ticketTitle, setTicketTitle] = useState("");
  const [ticketDescription, setTicketDescription] = useState("");
  const [ticketPriority, setTicketPriority] = useState("medium");
  const [creatingTicket, setCreatingTicket] = useState(false);

  // ==================================================
  // LOAD TICKETS AFTER LOGIN
  // ==================================================

  useEffect(() => {
    if (token) {
      loadTickets();
    }
  }, [token]);

  // ==================================================
  // LOGIN
  // ==================================================

  async function login(e) {
    e.preventDefault();

    setError("");
    setLoading(true);

    try {
      const formData = new URLSearchParams();

      formData.append("username", username);
      formData.append("password", password);

      const response = await fetch(`${API_URL}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Login failed");
      }

      localStorage.setItem("token", data.access_token);
      setToken(data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // ==================================================
  // LOAD TICKETS
  // ==================================================

  async function loadTickets() {
    setError("");

    try {
      const response = await fetch(`${API_URL}/tickets`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to load tickets");
      }

      setTickets(data);
    } catch (err) {
      setError(err.message);
    }
  }

  // ==================================================
  // CREATE TICKET
  // ==================================================

  async function createTicket(e) {
    e.preventDefault();

    setError("");
    setCreatingTicket(true);

    try {
      const response = await fetch(`${API_URL}/tickets`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: ticketTitle,
          description: ticketDescription,
          priority: ticketPriority,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to create ticket");
      }

      setTicketTitle("");
      setTicketDescription("");
      setTicketPriority("medium");

      await loadTickets();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreatingTicket(false);
    }
  }

  // ==================================================
  // AI ANALYSIS
  // ==================================================

  async function analyzeTicket(ticketId) {
    setAnalyzing(ticketId);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/tickets/${ticketId}/analyze`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "AI analysis failed");
      }

      setAnalyses((previous) => ({
        ...previous,
        [ticketId]: data,
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(null);
    }
  }

  // ==================================================
  // UPDATE TICKET STATUS
  // ==================================================

  async function updateTicketStatus(ticketId, status) {
    setError("");
    setUpdatingStatus(ticketId);

    try {
      const response = await fetch(
        `${API_URL}/tickets/${ticketId}/status`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            status: status,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to update ticket status"
        );
      }

      await loadTickets();
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingStatus(null);
    }
  }

  // ==================================================
  // LOGOUT
  // ==================================================

  function logout() {
    localStorage.removeItem("token");

    setToken(null);
    setTickets([]);
    setAnalyses({});

    setUsername("");
    setPassword("");
  }

  // ==================================================
  // FORMAT AI RESPONSE
  // ==================================================

  function formatAIText(text) {
    if (!text) return null;

    const lines = text.split("\n");

    return lines.map((line, index) => {
      const content = line.trim();

      if (!content) {
        return (
          <div
            key={index}
            style={{ height: "12px" }}
          />
        );
      }

      const headingMatch = content.match(
        /^\*{0,2}(\d+\.\s+[^:*]+):\*{0,2}$/
      );

      if (headingMatch) {
        return (
          <h3
            key={index}
            className="analysis-heading"
          >
            {headingMatch[1]}
          </h3>
        );
      }

      const boldMatch = content.match(
        /^\*{0,2}([^*]+):\*{0,2}$/
      );

      if (boldMatch) {
        return (
          <h3
            key={index}
            className="analysis-heading"
          >
            {boldMatch[1]}
          </h3>
        );
      }

      if (/^\d+\.\s/.test(content)) {
        return (
          <div
            key={index}
            className="analysis-list-item"
          >
            {content}
          </div>
        );
      }

      if (/^-\s/.test(content)) {
        return (
          <div
            key={index}
            className="analysis-bullet"
          >
            • {content.substring(2)}
          </div>
        );
      }

      return (
        <p
          key={index}
          className="analysis-paragraph"
        >
          {content.replace(/\*\*/g, "")}
        </p>
      );
    });
  }

  // ==================================================
  // LOGIN PAGE
  // ==================================================

  if (!token) {
    return (
      <div className="login-page">
        <div className="login-card">

          <div className="ai-logo">
            AI
          </div>

          <h1>AI IT Operations</h1>

          <p className="subtitle">
            Intelligent Incident Management Platform
          </p>

          <form onSubmit={login}>

            <label>Username</label>

            <input
              type="text"
              placeholder="Enter username"
              value={username}
              onChange={(e) =>
                setUsername(e.target.value)
              }
              required
            />

            <label>Password</label>

            <input
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={(e) =>
                setPassword(e.target.value)
              }
              required
            />

            {error && (
              <div className="error">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
            >
              {loading
                ? "Signing In..."
                : "Sign In"}
            </button>

          </form>
        </div>
      </div>
    );
  }

  // ==================================================
  // DASHBOARD STATISTICS
  // ==================================================

  const totalTickets = tickets.length;

  const openTickets = tickets.filter(
    (ticket) =>
      ticket.status === "open"
  ).length;

  const highPriority = tickets.filter(
    (ticket) =>
      ticket.priority === "high"
  ).length;

  const resolvedTickets = tickets.filter(
    (ticket) =>
      ticket.status === "resolved"
  ).length;

  // ==================================================
  // DASHBOARD
  // ==================================================

  return (
    <div className="dashboard">

      {/* ============================================
          TOP BAR
      ============================================ */}

      <header className="topbar">

        <div>

          <div className="brand">

            <span className="brand-logo">
              AI
            </span>

            <span>
              AI IT Operations
            </span>

          </div>

          <div className="brand-subtitle">
            Intelligent Incident Management Platform
          </div>

        </div>

        <div className="topbar-right">

          <span className="ai-status">

            <span className="status-dot"></span>

            AI Powered

          </span>

          <button
            className="logout-button"
            onClick={logout}
          >
            Logout
          </button>

        </div>

      </header>

      {/* ============================================
          MAIN CONTENT
      ============================================ */}

      <main className="container">

        {error && (
          <div className="error dashboard-error">
            {error}
          </div>
        )}

        {/* ==========================================
            STATISTICS
        ========================================== */}

        <section className="stats-grid">

          <div className="stat-card">

            <span className="stat-label">
              Total Tickets
            </span>

            <strong>
              {totalTickets}
            </strong>

          </div>

          <div className="stat-card">

            <span className="stat-label">
              Open Tickets
            </span>

            <strong>
              {openTickets}
            </strong>

          </div>

          <div className="stat-card">

            <span className="stat-label">
              High Priority
            </span>

            <strong>
              {highPriority}
            </strong>

          </div>

          <div className="stat-card">

            <span className="stat-label">
              Resolved
            </span>

            <strong>
              {resolvedTickets}
            </strong>

          </div>

        </section>

        {/* ==========================================
            CREATE TICKET
        ========================================== */}

        <section className="create-ticket-section">

          <div className="section-header">

            <div>

              <h2>
                Create New Ticket
              </h2>

              <p>
                Create an IT incident for AI-powered analysis.
              </p>

            </div>

          </div>

          <form
            className="ticket-form"
            onSubmit={createTicket}
          >

            <div className="form-group">

              <label>
                Incident Title
              </label>

              <input
                type="text"
                placeholder="e.g. Application server is slow"
                value={ticketTitle}
                onChange={(e) =>
                  setTicketTitle(e.target.value)
                }
                required
              />

            </div>

            <div className="form-group">

              <label>
                Description
              </label>

              <textarea
                placeholder="Describe the incident in detail..."
                value={ticketDescription}
                onChange={(e) =>
                  setTicketDescription(e.target.value)
                }
                rows="4"
                required
              />

            </div>

            <div className="form-group">

              <label>
                Priority
              </label>

              <select
                value={ticketPriority}
                onChange={(e) =>
                  setTicketPriority(e.target.value)
                }
              >

                <option value="low">
                  Low
                </option>

                <option value="medium">
                  Medium
                </option>

                <option value="high">
                  High
                </option>

              </select>

            </div>

            <button
              type="submit"
              className="create-ticket-button"
              disabled={creatingTicket}
            >
              {creatingTicket
                ? "Creating Ticket..."
                : "Create Ticket"}
            </button>

          </form>

        </section>

        {/* ==========================================
            INCIDENT TICKETS
        ========================================== */}

        <section className="tickets-section">

          <div className="section-header">

            <div>

              <h2>
                Incident Tickets
              </h2>

              <p>
                Monitor and analyze IT incidents.
              </p>

            </div>

            <button
              className="refresh-button"
              onClick={loadTickets}
            >
              Refresh
            </button>

          </div>

          <div className="tickets-table">

            <div className="table-header">

              <span>
                ID
              </span>

              <span>
                Incident
              </span>

              <span>
                Priority
              </span>

              <span>
                Status
              </span>

              <span>
                AI Analysis
              </span>

            </div>

            {tickets.length === 0 && (
              <div className="empty-tickets">
                No incident tickets found.
              </div>
            )}

            {tickets.map((ticket) => (

              <div
                className="ticket-row"
                key={ticket.id}
              >

                <span>
                  #{ticket.id}
                </span>

                <div>

                  <strong>
                    {ticket.title}
                  </strong>

                  <p>
                    {ticket.description}
                  </p>

                </div>

                <span
                  className={`priority ${ticket.priority}`}
                >
                  {ticket.priority.toUpperCase()}
                </span>

                {/* STATUS CONTROL */}
                <select
                  className={`status ${ticket.status}`}
                  value={ticket.status}
                  onChange={(e) =>
                    updateTicketStatus(
                      ticket.id,
                      e.target.value
                    )
                  }
                  disabled={
                    updatingStatus === ticket.id
                  }
                >
                  <option value="open">
                    Open
                  </option>

                  <option value="in_progress">
                    In Progress
                  </option>

                  <option value="resolved">
                    Resolved
                  </option>

                  <option value="closed">
                    Closed
                  </option>
                </select>

                <button
                  className="analyze-button"
                  onClick={() =>
                    analyzeTicket(ticket.id)
                  }
                  disabled={
                    analyzing === ticket.id
                  }
                >
                  {analyzing === ticket.id
                    ? "Analyzing..."
                    : "Analyze with AI"}
                </button>

              </div>

            ))}

          </div>

        </section>

        {/* ==========================================
            AI ANALYSIS
        ========================================== */}

        <section className="analysis-section">

          <div className="section-header">

            <div>

              <h2>
                AI Incident Analysis
              </h2>

              <p>
                RAG-powered troubleshooting recommendations.
              </p>

            </div>

          </div>

          {Object.values(analyses).length === 0 && (

            <div className="empty-analysis">

              Select an incident and click{" "}

              <strong>
                Analyze with AI
              </strong>{" "}

              to generate troubleshooting
              recommendations.

            </div>

          )}

          {tickets.map((ticket) => {

            const analysis =
              analyses[ticket.id];

            if (!analysis) {
              return null;
            }

            return (

              <div
                className="analysis-card"
                key={ticket.id}
              >

                <div className="analysis-top">

                  <div>

                    <span className="ticket-number">
                      Ticket #{ticket.id}
                    </span>

                    <h2>
                      {ticket.title}
                    </h2>

                  </div>

                  <span
                    className={`priority ${ticket.priority}`}
                  >
                    {ticket.priority.toUpperCase()}
                  </span>

                </div>

                <div className="analysis-content">

                  {formatAIText(
                    analysis.analysis
                  )}

                </div>

                <div className="knowledge-sources">

                  <h3>
                    Knowledge Sources
                  </h3>

                  {analysis.knowledge_sources &&
                  analysis.knowledge_sources.length > 0 ? (

                    analysis.knowledge_sources.map(
                      (source) => (

                        <div
                          className="knowledge-source"
                          key={source}
                        >
                          📄 {source}
                        </div>

                      )
                    )

                  ) : (

                    <div className="no-knowledge-source">
                      No relevant internal knowledge
                      base source found.
                    </div>

                  )}

                </div>

              </div>

            );

          })}

        </section>

      </main>

    </div>
  );
}

export default App;