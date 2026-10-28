import { useEffect, useRef, useState } from "react";

type Lookup = {
  query: string;
  retrieved_at: string;
  unavailable: number;
  sources: { id: number; title: string; url: string; excerpt: string; truncated: boolean; ambiguous: boolean }[];
};

export function OnlineLookup() {
  const [query, setQuery] = useState("");
  const [approved, setApproved] = useState(false);
  const [result, setResult] = useState<Lookup | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

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
      <input id="online-query" value={query} maxLength={300} disabled={busy} required
        onChange={event => { setQuery(event.target.value); setApproved(false); setResult(null); }} />
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
      {result.sources.map(source => <article key={source.id}>
        <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title} — Wikipedia</a>
        {source.ambiguous && <p>This topic has multiple meanings; refine your query.</p>}
        <blockquote>{source.excerpt}{source.truncated ? "…" : ""}</blockquote>
        <small>Wikipedia contributors · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a>{source.truncated ? " · excerpt shortened" : ""}</small>
      </article>)}
      <button onClick={() => { setResult(null); setQuery(""); }}>Clear online results</button>
    </section>}
  </details>;
}
