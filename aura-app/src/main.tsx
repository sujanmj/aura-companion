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
  facts: { id: number; fact_key: string; fact_value: string }[];
  routines: {
    id: number;
    routine_key: string;
    routine_value: string;
    last_seen_at: string;
  }[];
  observations: {
    id: number;
    event_type: string;
    event_summary: string;
    source: string;
    created_at: string;
  }[];
  preferences: CheckinPreferences;
  conversations: Message[];
  actions: boolean;
  stt: boolean;
  tts: boolean;
};
type CheckinPreferences = {
  checkins_enabled: boolean;
  quiet_start: string;
  quiet_end: string;
  checkin_interval_hours: number;
  last_checkin_at: string | null;
};
type Readiness = {
  brain: { provider: string; state: string; model: string; missing: string[] };
  memory: string;
  voice: { stt: string; tts: string };
  actions: { state: string };
  hardware: string;
};
type ProviderTest = { provider: string; state: string; verified: boolean };
type Approval = { id: string; name: string; input: unknown; expires: number };
const acceptanceSteps = [
  {
    id: "conversation",
    title: "Check a real conversation",
    detail:
      "Send a direct, non-greeting question. Confirm the reply is useful and its provider label matches the brain you configured; a LOCAL RESPONSE means the fallback answered.",
    tab: "conversation",
  },
  {
    id: "voice-input",
    title: "Review a voice draft",
    detail:
      "Opt in to the microphone, say Hey AURA and a short request, then edit the transcript before sending it. Turn the microphone off afterward.",
    tab: "conversation",
  },
  {
    id: "voice-output",
    title: "Test spoken replies and Stop",
    detail:
      "Enable Speak replies, confirm you can hear a response, then use Stop speaking to interrupt one. Browser speech availability varies by device.",
    tab: "conversation",
  },
  {
    id: "memory",
    title: "Confirm memory continuity",
    detail:
      "Share a low-sensitivity preference, open Memory, and confirm the saved fact appears for your account. Correct or forget it if you do not want to keep it.",
    tab: "memory",
  },
  {
    id: "ambient",
    title: "Accept the Mac ambient session",
    detail:
      "On a Mac, pair the native helper and explicitly start ambient mode. Check its live mic/camera indicators, Pause, restart, and sleep/wake. Permission denial recovery and acoustic feedback need a real-device check.",
    tab: "setup",
  },
  {
    id: "actions",
    title: "Review optional tool approvals",
    detail:
      "Only if you configured a trusted MCP server: test a harmless tool, deny one call, and approve a separate call. Every call should show its exact name and arguments first.",
    tab: "actions",
  },
] as const;
const acceptanceStorageKey = "aura-first-device-acceptance-v1";
function loadAcceptanceChecks(): Record<string, boolean> {
  try {
    const value = localStorage.getItem(acceptanceStorageKey);
    if (!value) return {};
    const parsed: unknown = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
      return {};
    return Object.fromEntries(
      acceptanceSteps.map(({ id }) => [
        id,
        (parsed as Record<string, unknown>)[id] === true,
      ]),
    );
  } catch {
    return {};
  }
}
type SpeechPreferences = { voiceURI: string; rate: number };
const speechPreferencesKey = "aura-browser-speech-preferences-v1";
function loadSpeechPreferences(): SpeechPreferences {
  try {
    const value = localStorage.getItem(speechPreferencesKey);
    if (!value) return { voiceURI: "", rate: 0.97 };
    const parsed: unknown = JSON.parse(value);
    if (!parsed || typeof parsed !== "object")
      return { voiceURI: "", rate: 0.97 };
    const preferences = parsed as Partial<SpeechPreferences>;
    return {
      voiceURI:
        typeof preferences.voiceURI === "string" ? preferences.voiceURI : "",
      rate:
        typeof preferences.rate === "number" &&
        Number.isFinite(preferences.rate)
          ? Math.min(1.2, Math.max(0.8, preferences.rate))
          : 0.97,
    };
  } catch {
    return { voiceURI: "", rate: 0.97 };
  }
}
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
  const kioskRequested =
    new URLSearchParams(window.location.search).get("kiosk") === "1";
  const [status, setStatus] = useState<Status | null>(null),
    [code, setCode] = useState(""),
    [error, setError] = useState(""),
    [messages, setMessages] = useState<Message[]>([]),
    [text, setText] = useState(""),
    [busy, setBusy] = useState(false),
    [mic, setMic] = useState(false),
    [speaking, setSpeaking] = useState(false),
    [level, setLevel] = useState(0),
    [voice, setVoice] = useState(false),
    [autoSend, setAutoSend] = useState(false),
    [theme, setTheme] = useState(localStorage.getItem("aura-theme") || "calm"),
    [tab, setTab] = useState("conversation"),
    [approvals, setApprovals] = useState<Approval[]>([]),
    [task, setTask] = useState<{ state: string; response: string } | null>(
      null,
    ),
    [taskInput, setTaskInput] = useState(""),
    [readiness, setReadiness] = useState<Readiness | null>(null),
    [providerTest, setProviderTest] = useState<ProviderTest | null>(null),
    [providerTesting, setProviderTesting] = useState(false),
    [acceptanceChecks, setAcceptanceChecks] = useState(loadAcceptanceChecks),
    [speechPreferences, setSpeechPreferences] = useState<SpeechPreferences>(
      loadSpeechPreferences,
    ),
    [browserVoices, setBrowserVoices] = useState<SpeechSynthesisVoice[]>([]),
    [checkinPreferences, setCheckinPreferences] =
      useState<CheckinPreferences | null>(null),
    [editingFact, setEditingFact] = useState<number | null>(null),
    [factDraft, setFactDraft] = useState(""),
    [editingRoutine, setEditingRoutine] = useState<number | null>(null),
    [routineDraft, setRoutineDraft] = useState("");
  const stopListen = useRef<(() => void) | null>(null),
    bottom = useRef<HTMLDivElement>(null),
    micStarting = useRef(false),
    sending = useRef(false),
    onTranscript = useRef<(value: string) => void>(() => {});
  onTranscript.current = (value) => {
    if (kioskRequested && autoSend) {
      void sendMessage(value);
    } else {
      setText(value);
      setError("Transcript ready — edit it, then send.");
    }
  };
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
    if (!status?.preferences.checkins_enabled || tab !== "conversation") return;
    let pending = false;
    const checkIn = async () => {
      if (pending || document.visibilityState !== "visible") return;
      pending = true;
      try {
        const result = await api<{ due: boolean; response?: string }>(
          "checkin",
          {},
        );
        if (result.due) {
          await refresh();
          setError("AURA checked in. Reply whenever you feel like it.");
        }
      } catch {
        // Check-ins are optional; transient errors do not interrupt conversation.
      } finally {
        pending = false;
      }
    };
    void checkIn();
    const timer = window.setInterval(() => void checkIn(), 5 * 60 * 1000);
    document.addEventListener("visibilitychange", checkIn);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", checkIn);
    };
  }, [status?.preferences.checkins_enabled, tab]);
  useEffect(() => {
    if (!status || tab !== "setup") return;
    api<CheckinPreferences>("preferences")
      .then(setCheckinPreferences)
      .catch((e) => setError(String(e)));
  }, [!!status, tab]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);
  useEffect(() => {
    localStorage.setItem("aura-theme", theme);
  }, [theme]);
  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const updateVoices = () =>
      setBrowserVoices(window.speechSynthesis.getVoices());
    updateVoices();
    window.speechSynthesis.addEventListener("voiceschanged", updateVoices);
    return () =>
      window.speechSynthesis.removeEventListener("voiceschanged", updateVoices);
  }, []);
  function updateSpeechPreferences(next: SpeechPreferences) {
    setSpeechPreferences(next);
    try {
      localStorage.setItem(speechPreferencesKey, JSON.stringify(next));
    } catch {
      setError("Could not save voice preferences in this browser.");
    }
  }
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
  async function checkReadiness() {
    setReadiness(null);
    setProviderTest(null);
    try {
      setReadiness(await api<Readiness>("readiness"));
    } catch (e) {
      setError(String(e));
    }
  }
  async function testProvider() {
    setProviderTesting(true);
    setProviderTest(null);
    try {
      setProviderTest(await api<ProviderTest>("readiness/provider-test", {}));
    } catch (e) {
      setError(String(e));
    } finally {
      setProviderTesting(false);
    }
  }
  useEffect(() => {
    if (status && tab === "setup") void checkReadiness();
  }, [!!status, tab]);
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
  async function sendMessage(message: string) {
    if (!message.trim() || sending.current) return;
    sending.current = true;
    message = message.trim();
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
      if (voice) {
        setSpeaking(true);
        void speak(
          result.response,
          status?.tts || false,
          speechPreferences.voiceURI,
          speechPreferences.rate,
        ).finally(() => setSpeaking(false));
      }
    } catch (e) {
      setError(String(e));
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }
  function send(event: React.FormEvent) {
    event.preventDefault();
    void sendMessage(text);
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
        (value) => onTranscript.current(value),
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
    <div
      className={"app " + theme + (kioskRequested && status ? " kiosk" : "")}
    >
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
            ["setup", "Setup", "04"],
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
          <div className="version">AURA COMPANION / 0.3.0</div>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <span className="eyebrow">A LITTLE SPACE TO BE YOURSELF</span>
            <h1>
              {tab === "setup"
                ? "Ready for our next conversation?"
                : tab === "memory"
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
          <section className="presence" aria-busy={busy}>
            <div className="orb">
              <OrbBoundary>
                <Scene
                  active={busy || mic || speaking}
                  level={level}
                  theme={theme}
                />
              </OrbBoundary>
              <div className="orb-label">A U R A</div>
            </div>
            <span className="eyebrow">
              {speaking
                ? "AURA IS SPEAKING"
                : busy
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
            {kioskRequested && status && (
              <div className="kiosk-controls">
                <button
                  type="button"
                  className={mic ? "kiosk-mic active" : "kiosk-mic"}
                  aria-pressed={mic}
                  onClick={() => void toggleMic()}
                >
                  {mic ? "Pause listening" : "Start listening"}
                </button>
                <label>
                  <input
                    type="checkbox"
                    checked={autoSend}
                    onChange={(e) => setAutoSend(e.target.checked)}
                  />
                  Send recognized speech automatically (saves it to memory and
                  uses your configured brain)
                </label>
                {!autoSend && (
                  <form onSubmit={send}>
                    <label htmlFor="kiosk-message">Review your message</label>
                    <textarea
                      id="kiosk-message"
                      value={text}
                      maxLength={8000}
                      onChange={(e) => setText(e.target.value)}
                    />
                    <button disabled={busy || !text.trim()}>
                      Send message
                    </button>
                  </form>
                )}
                <label>
                  <input
                    type="checkbox"
                    checked={voice}
                    onChange={(e) => {
                      setVoice(e.target.checked);
                      if (!e.target.checked) silence();
                    }}
                  />
                  Speak replies
                </label>
              </div>
            )}
            {kioskRequested && status && (
              <p className="kiosk-reply" role="status">
                {messages.filter((m) => m.role === "assistant").at(-1)?.message}
              </p>
            )}
            {kioskRequested && error && (
              <div className="kiosk-status">{error}</div>
            )}
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
                    onClick={() => {
                      silence();
                      setSpeaking(false);
                    }}
                  >
                    Stop speaking
                  </button>
                  <small>
                    Voice transcripts are yours to review before sending.
                  </small>
                </form>
              </>
            ) : tab === "setup" ? (
              <div className="details">
                <span className="eyebrow">SETUP & READINESS</span>
                <h2>Know what is ready.</h2>
                <p>
                  Refreshing readiness reads configuration only. It does not
                  contact providers, start tools, or turn on your microphone
                  or camera. The separate provider test below runs only when
                  you choose it.
                </p>
                <button onClick={() => void checkReadiness()}>
                  Refresh readiness
                </button>
                {readiness && (
                  <>
                    <article className="fact">
                      <h3>Memory</h3>
                      <p>Available in this local session.</p>
                    </article>
                    <article className="fact">
                      <h3>Conversation brain</h3>
                      <p>
                        {readiness.brain.provider}
                        {readiness.brain.model
                          ? " · " + readiness.brain.model
                          : ""}
                      </p>
                      <p>
                        {readiness.brain.state === "local_only"
                          ? "Local rule-based replies. A cloud or local language model is not selected."
                          : readiness.brain.state === "configured_unverified"
                            ? "Configured. A successful live conversation still needs to be verified."
                            : readiness.brain.state === "missing_configuration"
                              ? "Configuration is incomplete; AURA will use its local fallback."
                              : "This provider is not implemented. AURA will use its local fallback."}
                      </p>
                      {readiness.brain.missing.length > 0 && (
                        <p>
                          Set {readiness.brain.missing.join(" and ")} in your
                          private config/keys.env, then restart AURA.
                        </p>
                      )}
                      <p>
                        A provider test sends only “Reply with exactly: AURA
                        connection confirmed.” to the selected provider. It
                        includes no conversation, memory, or personal details,
                        and AURA does not save the reply.
                      </p>
                      <button
                        type="button"
                        disabled={
                          providerTesting ||
                          readiness.brain.state !== "configured_unverified"
                        }
                        onClick={() => void testProvider()}
                      >
                        {providerTesting
                          ? "Testing provider…"
                          : "Test configured provider"}
                      </button>
                      {providerTest && (
                        <p role="status">
                          {providerTest.state === "live_verified"
                            ? `${providerTest.provider} replied to the test request.`
                            : providerTest.state === "test_failed"
                              ? `${providerTest.provider} did not complete the test request.`
                              : `Provider test unavailable: ${providerTest.state.replaceAll("_", " ")}.`}
                        </p>
                      )}
                    </article>
                    <article className="fact">
                      <h3>Voice</h3>
                      <p>
                        {readiness.voice.stt === "browser"
                          ? "Speech input uses browser recognition when supported."
                          : "Cloud transcription is configured but has not been tested live."}
                      </p>
                      <p>
                        {readiness.voice.tts === "browser"
                          ? "Replies use browser speech."
                          : "Cloud speech is configured but has not been tested live."}
                      </p>
                      <p>
                        Microphone, speakers, camera and native on-device
                        recognition still require a real-device check. Browser
                        recognition may use the browser vendor’s cloud service.
                      </p>
                      <label htmlFor="browser-voice">
                        Installed browser voice
                      </label>
                      <select
                        id="browser-voice"
                        value={speechPreferences.voiceURI}
                        onChange={(event) =>
                          updateSpeechPreferences({
                            ...speechPreferences,
                            voiceURI: event.target.value,
                          })
                        }
                      >
                        <option value="">System default</option>
                        {browserVoices.map((browserVoice) => (
                          <option
                            key={browserVoice.voiceURI}
                            value={browserVoice.voiceURI}
                          >
                            {browserVoice.name} ({browserVoice.lang})
                          </option>
                        ))}
                      </select>
                      <label htmlFor="browser-voice-rate">
                        Browser speaking pace (
                        {speechPreferences.rate.toFixed(2)}×)
                      </label>
                      <input
                        id="browser-voice-rate"
                        type="range"
                        min="0.8"
                        max="1.2"
                        step="0.05"
                        value={speechPreferences.rate}
                        onChange={(event) =>
                          updateSpeechPreferences({
                            ...speechPreferences,
                            rate: Number(event.target.value),
                          })
                        }
                      />
                      <small>
                        Saved only in this browser. These choices apply to
                        browser speech and local fallback if cloud speech is
                        configured.
                      </small>
                    </article>
                    <article className="fact">
                      <h3>External actions</h3>
                      <p>
                        {readiness.actions.state === "disabled"
                          ? "Disabled. No tool task can run."
                          : readiness.actions.state === "missing_configuration"
                            ? "Opted in, but MCP servers or allowed tools are missing. Complete the local configuration first."
                            : "Configured, not tested live. Each tool invocation still needs your approval."}
                      </p>
                    </article>
                  </>
                )}
                <article className="fact acceptance-checklist">
                  <h3>First-device acceptance</h3>
                  <p>
                    Work through the checks on this device. These boxes are
                    manual notes saved only in this browser; checking one does
                    not run a test or prove a capability by itself.
                  </p>
                  <div className="acceptance-steps">
                    {acceptanceSteps.map((step) => (
                      <div className="acceptance-step" key={step.id}>
                        <label>
                          <input
                            type="checkbox"
                            checked={acceptanceChecks[step.id] === true}
                            onChange={(event) => {
                              const next = {
                                ...acceptanceChecks,
                                [step.id]: event.target.checked,
                              };
                              setAcceptanceChecks(next);
                              try {
                                localStorage.setItem(
                                  acceptanceStorageKey,
                                  JSON.stringify(next),
                                );
                              } catch {
                                setError(
                                  "Could not save these checklist notes in this browser.",
                                );
                              }
                            }}
                          />
                          <span>{step.title}</span>
                        </label>
                        <p>{step.detail}</p>
                        {step.tab !== "setup" && (
                          <button
                            type="button"
                            onClick={() => setTab(step.tab)}
                          >
                            Open{" "}
                            {step.tab === "memory"
                              ? "Memory"
                              : step.tab === "actions"
                                ? "Actions"
                                : "Conversation"}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setAcceptanceChecks({});
                      try {
                        localStorage.removeItem(acceptanceStorageKey);
                      } catch {
                        setError(
                          "Could not clear these checklist notes in this browser.",
                        );
                      }
                    }}
                  >
                    Clear checklist notes
                  </button>
                </article>
                {checkinPreferences && (
                  <article className="fact checkin-settings">
                    <h3>Companion check-ins</h3>
                    <p>
                      Optional and off by default. AURA checks in only while
                      this app is open, after your chosen idle interval, and
                      outside quiet hours. Check-ins stay in local memory.
                    </p>
                    <form
                      onSubmit={async (event) => {
                        event.preventDefault();
                        try {
                          const saved = await api<CheckinPreferences>(
                            "preferences",
                            checkinPreferences,
                          );
                          setCheckinPreferences(saved);
                          setStatus((current) =>
                            current
                              ? { ...current, preferences: saved }
                              : current,
                          );
                          setError("Check-in preferences saved.");
                        } catch (e) {
                          setError(String(e));
                        }
                      }}
                    >
                      <label>
                        <input
                          type="checkbox"
                          checked={checkinPreferences.checkins_enabled}
                          onChange={(event) =>
                            setCheckinPreferences({
                              ...checkinPreferences,
                              checkins_enabled: event.target.checked,
                            })
                          }
                        />
                        Allow AURA to check in
                      </label>
                      <label>
                        Quiet hours start
                        <input
                          type="time"
                          value={checkinPreferences.quiet_start}
                          onChange={(event) =>
                            setCheckinPreferences({
                              ...checkinPreferences,
                              quiet_start: event.target.value,
                            })
                          }
                        />
                      </label>
                      <label>
                        Quiet hours end
                        <input
                          type="time"
                          value={checkinPreferences.quiet_end}
                          onChange={(event) =>
                            setCheckinPreferences({
                              ...checkinPreferences,
                              quiet_end: event.target.value,
                            })
                          }
                        />
                      </label>
                      <label>
                        Check in after this many idle hours
                        <input
                          type="number"
                          min={4}
                          max={168}
                          value={checkinPreferences.checkin_interval_hours}
                          onChange={(event) =>
                            setCheckinPreferences({
                              ...checkinPreferences,
                              checkin_interval_hours: Number(
                                event.target.value,
                              ),
                            })
                          }
                        />
                      </label>
                      <button className="primary">
                        Save check-in preferences
                      </button>
                    </form>
                  </article>
                )}
              </div>
            ) : tab === "memory" ? (
              <div className="details">
                <span className="eyebrow">CONTINUITY, NOT A FRESH START</span>
                <h2>Your companion remembers.</h2>
                <p>
                  These are the facts in your existing AURA memory.
                  Conversations and feedback continue in the same database.
                </p>
                <a className="memory-export" href="/api/memory/export" download>
                  Download all my AURA data (JSON)
                </a>
                <button
                  className="memory-export"
                  onClick={async () => {
                    if (
                      !window.confirm(
                        "Clear all saved conversation messages and replies? Saved facts, routines, and observations will remain. This cannot be undone.",
                      )
                    )
                      return;
                    try {
                      const result = await api<{ deleted: number }>(
                        "conversations/clear",
                        {},
                      );
                      await refresh();
                      setError(
                        `Conversation history cleared (${result.deleted} messages).`,
                      );
                    } catch (e) {
                      setError(String(e));
                    }
                  }}
                >
                  Clear conversation history
                </button>
                {status.facts.length === 0 ? (
                  <p>No facts yet. Start a conversation.</p>
                ) : (
                  status.facts.map((f) => (
                    <article className="fact" key={f.id}>
                      <small>{f.fact_key.replaceAll("_", " ")}</small>
                      {editingFact === f.id ? (
                        <form
                          onSubmit={async (event) => {
                            event.preventDefault();
                            try {
                              await api("fact/update", {
                                fact_id: f.id,
                                value: factDraft,
                              });
                              await refresh();
                              setEditingFact(null);
                              setError("Memory corrected.");
                            } catch (e) {
                              setError(String(e));
                            }
                          }}
                        >
                          <label htmlFor={"fact-" + f.id}>
                            Correct what AURA remembers
                          </label>
                          <textarea
                            id={"fact-" + f.id}
                            value={factDraft}
                            maxLength={2000}
                            onChange={(event) =>
                              setFactDraft(event.target.value)
                            }
                            required
                          />
                          <button
                            className="primary"
                            disabled={!factDraft.trim()}
                          >
                            Save correction
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingFact(null)}
                          >
                            Cancel
                          </button>
                        </form>
                      ) : (
                        <>
                          <p>{f.fact_value}</p>
                          <div className="memory-controls">
                            <button
                              onClick={() => {
                                setEditingFact(f.id);
                                setFactDraft(f.fact_value);
                              }}
                            >
                              Correct
                            </button>
                            <button
                              onClick={async () => {
                                if (
                                  !window.confirm(
                                    "Forget this memory? AURA removes this saved summary and will not automatically save it again. Your original messages remain in chat history and may still inform recent context.",
                                  )
                                )
                                  return;
                                try {
                                  await api("fact/delete", { fact_id: f.id });
                                  await refresh();
                                  setError("Memory forgotten.");
                                } catch (e) {
                                  setError(String(e));
                                }
                              }}
                            >
                              Forget
                            </button>
                          </div>
                        </>
                      )}
                    </article>
                  ))
                )}
                <section className="memory-review">
                  <h3>Routines</h3>
                  {status.routines.length === 0 ? (
                    <p>No routines have been saved.</p>
                  ) : (
                    status.routines.map((routine) => (
                      <article className="fact" key={routine.id}>
                        <small>
                          {routine.routine_key.replaceAll("_", " ")}
                        </small>
                        {editingRoutine === routine.id ? (
                          <form
                            onSubmit={async (event) => {
                              event.preventDefault();
                              try {
                                await api("routine/update", {
                                  routine_id: routine.id,
                                  value: routineDraft,
                                });
                                await refresh();
                                setEditingRoutine(null);
                                setError("Routine corrected.");
                              } catch (e) {
                                setError(String(e));
                              }
                            }}
                          >
                            <label htmlFor={`routine-${routine.id}`}>
                              Correct this routine
                            </label>
                            <textarea
                              id={`routine-${routine.id}`}
                              value={routineDraft}
                              maxLength={2000}
                              required
                              onChange={(event) =>
                                setRoutineDraft(event.target.value)
                              }
                            />
                            <button className="primary">Save correction</button>
                            <button
                              type="button"
                              onClick={() => setEditingRoutine(null)}
                            >
                              Cancel
                            </button>
                          </form>
                        ) : (
                          <>
                            <p>{routine.routine_value}</p>
                            <div className="fact-actions">
                              <button
                                onClick={() => {
                                  setEditingRoutine(routine.id);
                                  setRoutineDraft(routine.routine_value);
                                }}
                              >
                                Correct
                              </button>
                              <button
                                onClick={async () => {
                                  if (
                                    !window.confirm(
                                      "Forget this routine? AURA will not automatically save it again unless you explicitly tell AURA to remember it.",
                                    )
                                  )
                                    return;
                                  try {
                                    await api("routine/delete", {
                                      routine_id: routine.id,
                                    });
                                    await refresh();
                                    setError("Routine forgotten.");
                                  } catch (e) {
                                    setError(String(e));
                                  }
                                }}
                              >
                                Forget
                              </button>
                            </div>
                          </>
                        )}
                      </article>
                    ))
                  )}
                </section>
                <section className="memory-review">
                  <h3>Recent observations</h3>
                  {status.observations.length === 0 ? (
                    <p>No observations have been saved.</p>
                  ) : (
                    status.observations.map((observation) => (
                      <article className="fact" key={observation.id}>
                        <small>
                          {observation.event_type.replaceAll("_", " ")} ·{" "}
                          {observation.source}
                        </small>
                        <p>{observation.event_summary}</p>
                        <time>{observation.created_at}</time>
                        <div className="fact-actions">
                          <button
                            onClick={async () => {
                              if (
                                !window.confirm(
                                  "Delete this saved observation from AURA memory?",
                                )
                              )
                                return;
                              try {
                                await api("observation/delete", {
                                  observation_id: observation.id,
                                });
                                await refresh();
                                setError("Observation deleted.");
                              } catch (e) {
                                setError(String(e));
                              }
                            }}
                          >
                            Delete observation
                          </button>
                        </div>
                      </article>
                    ))
                  )}
                </section>
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
