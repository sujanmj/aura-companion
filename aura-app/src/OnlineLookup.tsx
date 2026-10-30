import { useEffect, useRef, useState } from "react";

type Lookup = {
  query: string;
  lookup_id?: string;
  retrieved_at: string;
  unavailable: number;
  sources: { id: number; title: string; url: string; excerpt: string; truncated: boolean; ambiguous: boolean }[];
};

type GroundedAnswer = {
  response: string;
  provider: string;
  answered_at: string;
  saved: false;
  online_verified: false;
};

export function OnlineLookup({ provider }: { provider?: string }) {
  const [query, setQuery] = useState("");
  const [approved, setApproved] = useState(false);
  const [result, setResult] = useState<Lookup | null>(null);
  const [question, setQuestion] = useState("");
  const [answerConsent, setAnswerConsent] = useState(false);
  const [answer, setAnswer] = useState<GroundedAnswer | null>(null);
  const [answerBusy, setAnswerBusy] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  function clearResult() {
    if (result?.lookup_id) {
      void fetch("/api/online/clear", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lookup_id: result.lookup_id }) }).catch(() => {});
    }
    setResult(null);
    setQuestion("");
    setAnswerConsent(false);
    setAnswer(null);
  }

  function cancel() {
    request.current?.abort();
    request.current = null;
    setBusy(false);
    setApproved(false);
    setError("Lookup cancelled. The query may already have reached Wikipedia.");
  }

  return <details className="memory-review" name="conversation-extras">
    <summary>Check an online source</summary>
    <p>Review the exact query below. Only this query goes to English Wikipedia; AURA sends no private memories or ambient transcripts. Results stay in this view and are not saved. Wikipedia may log requests under its privacy policy.</p>
    <form onSubmit={async event => {
      event.preventDefault();
      if (!approved || busy) return;
      const controller = new AbortController();
      request.current = controller;
      setBusy(true);
      setResult(null);
      setError("");
      setApproved(false);
      try {
        const response = await fetch("/api/online/lookup", { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, approved: true }), signal: controller.signal });
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || "Online source unavailable.");
        if (request.current === controller) setResult(body);
      } catch (e) {
        if (!controller.signal.aborted && request.current === controller)
          setError(e instanceof Error ? e.message : "Online source unavailable.");
      } finally {
        if (request.current === controller) { request.current = null; setBusy(false); }
      }
    }}>
      <label htmlFor="online-query">Query to send to Wikipedia</label>
      <input id="online-query" value={query} maxLength={300} disabled={busy || answerBusy} required
      onChange={event => { clearResult(); setQuery(event.target.value); setApproved(false); }} />
      <label><input type="checkbox" checked={approved} disabled={busy}
        onChange={event => setApproved(event.target.checked)} />Approve this exact Wikipedia query.</label>
      <button disabled={!approved || busy || !query.trim()}>Look up approved query</button>
      {busy && <button type="button" onClick={cancel}>Cancel lookup</button>}
    </form>
    {busy && <p role="status">Checking Wikipedia…</p>}
    {error && <p role="status">{error}</p>}
    {result && <section aria-label="Online source results">
      <p>Sources retrieved {new Date(result.retrieved_at).toLocaleString()} for “{result.query}”. These are source excerpts, not independently verified facts. They may be incomplete, outdated or unrelated to your question; this is not a live news or emergency service.</p>
      {result.sources.length === 0 && <p>No usable source was returned. AURA has not verified an answer.</p>}
      {result.unavailable > 0 && <p>Some source summaries were unavailable.</p>}
      {result.sources.map((source, index) => <article key={source.id}>
        <a href={source.url} target="_blank" rel="noopener noreferrer">[{index + 1}] {source.title} — Wikipedia</a>
        {source.ambiguous && <p>This topic has multiple meanings; refine your query.</p>}
        <blockquote>{source.excerpt}{source.truncated ? "…" : ""}</blockquote>
        <small>Wikipedia contributors · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a>{source.truncated ? " · excerpt shortened" : ""}</small>
      </article>)}
      {provider === "local" && result.sources.length > 0 && <p>AURA is set to local-only mode, so it will not send a model request. The reviewed excerpts remain available, but a source-based summary cannot be generated in this mode.</p>}
      {result.sources.length > 0 && result.lookup_id && provider !== "local" && <form onSubmit={async event => {
        event.preventDefault();
        if (!answerConsent || answerBusy || !result.lookup_id) return;
        setAnswerBusy(true);
        setAnswer(null);
        try {
          const response = await fetch("/api/online/answer", { method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lookup_id: result.lookup_id, question, approved: true }) });
          const body = await response.json();
          if (!response.ok) throw new Error(body.error || "Source-based answer unavailable.");
          setAnswer(body);
        } catch (e) { setError(e instanceof Error ? e.message : "Source-based answer unavailable."); }
        finally { setAnswerBusy(false); setAnswerConsent(false); }
      }}>
        <label htmlFor="grounded-question">Question for AURA to answer from these excerpts</label>
        <textarea id="grounded-question" maxLength={1000} value={question} disabled={answerBusy}
          onChange={event => { setQuestion(event.target.value); setAnswer(null); setAnswerConsent(false); }} required />
        <p>The configured {provider || "AURA"} language model receives only this question and the displayed excerpts. It receives no saved memory and has no tools. If it is hosted, its retention policy applies.</p>
        <label><input type="checkbox" checked={answerConsent} disabled={answerBusy}
          onChange={event => setAnswerConsent(event.target.checked)} />I reviewed the question and excerpts and approve sending them for a temporary answer.</label>
        <small>Once sent to a provider, the request cannot be recalled.</small>
        <button disabled={!answerConsent || answerBusy || !question.trim()}>{answerBusy ? "Preparing answer…" : "Answer from these sources"}</button>
      </form>}
      {answer && <article aria-label="Source-based answer">
        <small>{answer.provider} · temporary · not saved · not independently verified</small>
        <p>{answer.response}</p>
        <small>Reviewed source excerpts are listed above. AURA has not checked them independently.</small>
      </article>}
      <button disabled={answerBusy} onClick={() => { clearResult(); setQuery(""); }}>Clear online results</button>
    </section>}
  </details>;
}
