import { Component, useEffect, useRef, useState, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { Scene } from "./scene/Scene";
import { api } from "./lib/api";
import { listen, speak, silence } from "./lib/voice";
import "./style.css";
type Message = {
  id?: number;
  role: string;
  message: string;
  provider?: string;
};
type Status = {
  provider: string;
  model: string;
  facts: { fact_key: string; fact_value: string }[];
  conversations: Message[];
  actions: boolean;
  stt: boolean;
  tts: boolean;
};
type Approval = { id: string; name: string; input: unknown; expires: number };
class OrbBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="fallback-orb">A</div>
    ) : (
      this.props.children
    );
  }
}
function App() {
  const [status, setStatus] = useState<Status | null>(null),
    [code, setCode] = useState(""),
    [error, setError] = useState(""),
    [messages, setMessages] = useState<Message[]>([]),
    [text, setText] = useState(""),
    [busy, setBusy] = useState(false),
    [mic, setMic] = useState(false),
    [level, setLevel] = useState(0),
    [voice, setVoice] = useState(false),
    [theme, setTheme] = useState(localStorage.getItem("aura-theme") || "calm"),
    [tab, setTab] = useState("conversation"),
    [approvals, setApprovals] = useState<Approval[]>([]),
    [task, setTask] = useState<{ state: string; response: string } | null>(
      null,
    ),
    [taskInput, setTaskInput] = useState("");
  const stopListen = useRef<(() => void) | null>(null),
    bottom = useRef<HTMLDivElement>(null),
    micStarting = useRef(false);
  async function refresh() {
    const data = await api<Status>("status");
    setStatus(data);
    setMessages(data.conversations);
  }
  useEffect(() => {
    refresh().catch(() => {});
    return () => {
      stopListen.current?.();
      silence();
    };
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);
  useEffect(() => {
    localStorage.setItem("aura-theme", theme);
  }, [theme]);
  useEffect(() => {
    if (!status?.actions) return;
    const timer = setInterval(() => {
      api<{ task: typeof task; approvals: Approval[] }>("task")
        .then((data) => {
          setTask(data.task);
          setApprovals(data.approvals);
        })
        .catch(() => {});
    }, 700);
    return () => clearInterval(timer);
  }, [status?.actions]);
  async function login(event: React.FormEvent) {
    event.preventDefault();
    try {
      await api("login", { token: code });
      setCode("");
      await refresh();
      setError("");
    } catch (e) {
      setError(String(e));
    }
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim() || busy) return;
    const message = text.trim();
    setText("");
    setBusy(true);
    setError("");
    setMessages((items) => [...items, { role: "user", message }]);
    try {
      const result = await api<{
        response: string;
        id: number;
        provider: string;
      }>("chat", { message });
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          message: result.response,
          id: result.id,
          provider: result.provider,
        },
      ]);
      const data = await api<Status>("status");
      setStatus(data);
      if (voice) void speak(result.response, status?.tts || false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function toggleMic() {
    if (micStarting.current) return;
    if (mic) {
      stopListen.current?.();
      stopListen.current = null;
      setMic(false);
      return;
    }
    micStarting.current = true;
    try {
      stopListen.current = await listen(
        status?.stt || false,
        (value) => {
          setText(value);
          setError("Transcript ready — edit it, then send.");
        },
        setLevel,
        setError,
      );
      setMic(true);
      setError("Say “Hey AURA”, then your message.");
    } catch (e) {
      setError(String(e));
    } finally {
      micStarting.current = false;
    }
  }
  async function feedback(id: number, rating: string) {
    try {
      await api("feedback", { response_id: id, rating });
      setError("Feedback saved to your companion’s memory.");
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <div className={"app " + theme}>
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brand-mark">✳</span>
          <span>
            AURA<small>YOUR COMPANION</small>
          </span>
        </a>
        <div className="nav-title">YOUR SPACE</div>
        <nav>
          {[
            ["conversation", "Conversation", "01"],
            ["memory", "Memory", "02"],
            ["actions", "Actions", "03"],
          ].map(([id, label, n]) => (
            <button
              key={id}
              className={tab === id ? "selected" : ""}
              onClick={() => setTab(id)}
            >
              <span>{label}</span>
              <small>{n}</small>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="dot" /> LOCAL MEMORY
          <small>
            Your conversations stay in your SQLite library. Cloud replies use
            your configured provider.
          </small>
          <div className="version">AURA COMPANION / 0.2.0</div>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <span className="eyebrow">A LITTLE SPACE TO BE YOURSELF</span>
            <h1>
              {tab === "memory"
                ? "What stays with us"
                : tab === "actions"
                  ? "A helping hand"
                  : "Good to have you here."}
            </h1>
          </div>
          <span className="privacy">
            {status ? "● Connected locally" : "○ Connect to begin"}
          </span>
        </header>
        <div className="workspace">
          <section className="presence">
            <div className="orb">
              <OrbBoundary>
                <Scene active={busy || mic} level={level} theme={theme} />
              </OrbBoundary>
              <div className="orb-label">A U R A</div>
            </div>
            <span className="eyebrow">
              {busy
                ? "THINKING WITH YOU"
                : mic
                  ? "LISTENING FOR “HEY AURA”"
                  : "HERE, WHEN YOU NEED ME"}
            </span>
            <h2>
              A familiar presence.
              <br />A fresh perspective.
            </h2>
            <p>
              Talk through your day, make a little room for your thoughts, or
              find your next step.
            </p>
            <div className="theme-switch">
              <button
                aria-pressed={theme === "calm"}
                onClick={() => setTheme("calm")}
              >
                Calm glow
              </button>
              <button
                aria-pressed={theme === "hologram"}
                onClick={() => setTheme("hologram")}
              >
                Holographic
              </button>
            </div>
            <div className="connection">
              <span className="dot" />
              {status?.provider === "claude"
                ? "Claude · " + (status.model || "model not set")
                : status?.provider || "Local companion"}
              <small>
                External actions{" "}
                {status?.actions ? "require your approval" : "disabled"}
              </small>
            </div>
          </section>
          <section className="panel">
            {!status ? (
              <div className="login">
                <span className="eyebrow">YOUR PRIVATE SPACE</span>
                <h2>Welcome to AURA.</h2>
                <p>
                  Enter the session code printed by the AURA launcher. Your
                  provider keys stay on the server.
                </p>
                <form onSubmit={login}>
                  <label htmlFor="code">Session code</label>
                  <input
                    id="code"
                    type="password"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    autoComplete="off"
                    required
                  />
                  <button className="primary">Connect to AURA →</button>
                </form>
              </div>
            ) : tab === "conversation" ? (
              <>
                <div className="panel-heading">
                  <h3>Our conversation</h3>
                  <span>JUST YOU & AURA</span>
                </div>
                <div className="messages" role="log" aria-live="polite">
                  {messages.length === 0 ? (
                    <div className="welcome">
                      <h2>What’s on your mind?</h2>
                      <p>There’s no perfect place to start.</p>
                      {[
                        "I’m feeling a little overwhelmed",
                        "Help me think through my day",
                        "I have something good to share",
                      ].map((s) => (
                        <button key={s} onClick={() => setText(s)}>
                          {s}
                          <span>↗</span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    messages
                      .filter((m) => m.role !== "system")
                      .map((m, i) => (
                        <article
                          key={m.id || i}
                          className={"message " + m.role}
                        >
                          <small>
                            {m.role === "user" ? "YOU" : "AURA"}
                            {m.provider === "local" ? " · LOCAL RESPONSE" : ""}
                          </small>
                          <p>{m.message}</p>
                          {m.role === "assistant" && m.id && (
                            <div className="feedback">
                              <button
                                aria-label="Helpful response"
                                onClick={() => void feedback(m.id!, "good")}
                              >
                                Helpful
                              </button>
                              <button
                                aria-label="Unhelpful response"
                                onClick={() => void feedback(m.id!, "bad")}
                              >
                                Not quite
                              </button>
                            </div>
                          )}
                        </article>
                      ))
                  )}
                  {busy && <p className="thinking">AURA is thinking…</p>}
                  <div ref={bottom} />
                </div>
                <form className="composer" onSubmit={send}>
                  <label className="sr-only" htmlFor="message">
                    Your message
                  </label>
                  <textarea
                    id="message"
                    placeholder="Tell me what’s on your mind…"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    maxLength={8000}
                  />
                  <div>
                    <button
                      type="button"
                      aria-pressed={mic}
                      onClick={() => void toggleMic()}
                    >
                      {mic ? "■ Stop microphone" : "◉ Enable microphone"}
                    </button>
                    <button className="primary" disabled={busy || !text.trim()}>
                      Send ↗
                    </button>
                  </div>
                  <label className="voice">
                    <input
                      type="checkbox"
                      checked={voice}
                      onChange={(e) => {
                        setVoice(e.target.checked);
                        if (!e.target.checked) silence();
                      }}
                    />{" "}
                    Speak replies
                  </label>
                  <button
                    className="stop-voice"
                    type="button"
                    onClick={silence}
                  >
                    Stop speaking
                  </button>
                  <small>
                    Voice transcripts are yours to review before sending.
                  </small>
                </form>
              </>
            ) : tab === "memory" ? (
              <div className="details">
                <span className="eyebrow">CONTINUITY, NOT A FRESH START</span>
                <h2>Your companion remembers.</h2>
                <p>
                  These are the facts in your existing AURA memory.
                  Conversations and feedback continue in the same database.
                </p>
                {status.facts.length === 0 ? (
                  <p>No facts yet. Start a conversation.</p>
                ) : (
                  status.facts.map((f) => (
                    <article className="fact" key={f.fact_key}>
                      <small>{f.fact_key.replaceAll("_", " ")}</small>
                      <p>{f.fact_value}</p>
                    </article>
                  ))
                )}
              </div>
            ) : (
              <div className="details">
                <span className="eyebrow">YOU STAY IN CONTROL</span>
                <h2>
                  {status.actions
                    ? "Review every action."
                    : "Actions are switched off."}
                </h2>
                <p>
                  External tools need server-side opt-in and an exact allowlist.
                  Each invocation needs a fresh approval here. Unanswered
                  requests expire after one minute.
                </p>
                {status.actions && (
                  <>
                    <form
                      onSubmit={async (e) => {
                        e.preventDefault();
                        try {
                          await api("task", { message: taskInput });
                          setTask({ state: "running", response: "" });
                          setTaskInput("");
                        } catch (err) {
                          setError(String(err));
                        }
                      }}
                    >
                      <label htmlFor="task">
                        Task for your configured tools
                      </label>
                      <textarea
                        id="task"
                        value={taskInput}
                        onChange={(e) => setTaskInput(e.target.value)}
                        maxLength={8000}
                      />
                      <button
                        className="primary"
                        disabled={
                          !taskInput.trim() || task?.state === "running"
                        }
                      >
                        Start task
                      </button>
                    </form>
                    {task && (
                      <article>
                        <h3>{task.state}</h3>
                        <p>{task.response}</p>
                        {task.state === "running" && (
                          <button onClick={() => void api("cancel", {})}>
                            Cancel task
                          </button>
                        )}
                      </article>
                    )}
                    {approvals.map((a) => (
                      <article className="approval" key={a.id}>
                        <h3>{a.name}</h3>
                        <pre>{JSON.stringify(a.input, null, 2)}</pre>
                        <button
                          onClick={() =>
                            void api("approve", { id: a.id, approved: false })
                          }
                        >
                          Deny
                        </button>
                        <button
                          className="primary"
                          onClick={() =>
                            void api("approve", { id: a.id, approved: true })
                          }
                        >
                          Approve this action
                        </button>
                      </article>
                    ))}
                  </>
                )}
              </div>
            )}
          </section>
        </div>
        {error && (
          <div className="notice" role="status">
            {error}
            <button aria-label="Dismiss" onClick={() => setError("")}>
              ×
            </button>
          </div>
        )}
        <footer>
          <span>Built around your memory. Designed for your pace.</span>
          <span>
            Voice uses browser services or your configured ElevenLabs account.
          </span>
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
