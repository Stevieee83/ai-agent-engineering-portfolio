const { useState, useEffect, useRef, useMemo } = React;

// ---------------------------------------------------------------- helpers
const api = async (path, body) => {
  const res = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
};
const newSessionId = () => Math.random().toString(36).slice(2, 10);
const renderMarkdown = (text) => ({ __html: DOMPurify.sanitize(marked.parse(text || "")) });
const isoInDays = (days) => new Date(Date.now() + days * 864e5).toISOString().slice(0, 10);

const KIND_STYLE = {
  rag:    { icon: "📚", label: "RAG",     cls: "bg-sky-50 border-sky-200 text-sky-800" },
  graph:  { icon: "🕸️", label: "Graph",   cls: "bg-violet-50 border-violet-200 text-violet-800" },
  skill:  { icon: "🧩", label: "Skill",   cls: "bg-amber-50 border-amber-200 text-amber-800" },
  mcp:    { icon: "🔌", label: "MCP",     cls: "bg-emerald-50 border-emerald-200 text-emerald-800" },
  llm:    { icon: "🤖", label: "LLM",     cls: "bg-slate-50 border-slate-200 text-slate-700" },
  memory: { icon: "💾", label: "Memory",  cls: "bg-pink-50 border-pink-200 text-pink-800" },
  error:  { icon: "⚠️", label: "Error",   cls: "bg-red-50 border-red-200 text-red-800" },
};

const NODE_COLOURS = {
  Traveller: "#e11d48", City: "#0284c7", Airport: "#0891b2", Airline: "#059669", Alliance: "#65a30d",
  LoyaltyProgramme: "#d97706", Preference: "#9333ea", Trip: "#db2777", Event: "#ea580c", TravelPolicy: "#475569",
};

const EXAMPLES = {
  "traveller:alex": [
    "Get me to Amsterdam for the data summit, with a hotel",
    "I need to be in London on 2026-10-20 for a client meeting",
    "Plan a week in New York in November, what do I need before I go?",
  ],
  "traveller:sam": [
    "Family trip to Dublin on 2026-10-17 for 3 nights with a hotel",
    "Can we see the northern lights in Iceland this winter?",
    "What's the cheapest way to get the kids to Paris for Disneyland?",
  ],
  "": [
    "Fly me from Edinburgh to Paris on 2026-10-30",
    "Get me to Amsterdam for the data summit and book it",
  ],
};

// ---------------------------------------------------------------- small UI pieces
function Toggle({ checked, onChange, label, hint, icon, disabled }) {
  return (
    <label className={`flex items-start gap-3 rounded-lg p-2 ${disabled ? "opacity-70" : "cursor-pointer hover:bg-slate-50"}`}>
      <button type="button" disabled={disabled} onClick={() => onChange(!checked)}
        className={`mt-0.5 relative inline-flex h-5 w-9 shrink-0 rounded-full transition ${checked ? "bg-indigo-600" : "bg-slate-300"}`}>
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${checked ? "left-4.5" : "left-0.5"}`} />
      </button>
      <span className="text-sm">
        <span className="font-medium">{icon} {label}</span>
        <span className="block text-xs text-slate-500">{hint}</span>
      </span>
    </label>
  );
}

function Card({ title, children, right }) {
  return (
    <section className="rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
        <h2 className="text-sm font-semibold text-slate-700">{title}</h2>{right}
      </div>
      <div className="p-3">{children}</div>
    </section>
  );
}

// ---------------------------------------------------------------- left sidebar
function TravellerPicker({ travellers, value, onChange }) {
  const options = [...travellers, { id: "", name: "Guest (no profile)", role: "Unknown traveller - nothing in the graph" }];
  return (
    <div className="space-y-2">
      {options.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)}
          className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${value === t.id ? "border-indigo-500 bg-indigo-50 ring-1 ring-indigo-500" : "border-slate-200 hover:border-slate-300"}`}>
          <div className="font-medium">{t.name}</div>
          <div className="text-xs text-slate-500">{t.role}{t.party_size > 1 ? ` · party of ${t.party_size}` : ""}</div>
        </button>
      ))}
    </div>
  );
}

function TripForm({ airports, hasProfile, onSubmit, disabled }) {
  const [form, setForm] = useState({ from: "", to: "AMS", depart: isoInDays(21), ret: "", travellers: 1, cabin: "economy", budget: "", hotel: true, notes: "" });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const label = (code) => { const a = airports.find((x) => x.code === code); return a ? `${a.city} (${a.code})` : code; };

  const submit = (e) => {
    e.preventDefault();
    const from = form.from ? `from ${label(form.from)} ` : "";
    const nights = form.ret ? Math.max(1, Math.round((new Date(form.ret) - new Date(form.depart)) / 864e5)) : 3;
    let msg = `Plan a trip ${from}to ${label(form.to)} departing ${form.depart}${form.ret ? `, returning ${form.ret}` : ""}. `;
    msg += `${form.travellers} traveller${form.travellers > 1 ? "s" : ""}, ${form.cabin.replace("_", " ")} cabin`;
    msg += form.budget ? `, total budget £${form.budget}.` : ".";
    if (form.hotel) msg += ` I need a hotel for ${nights} nights.`;
    if (form.notes.trim()) msg += ` ${form.notes.trim()}`;
    onSubmit(msg);
  };

  const input = "w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";
  return (
    <form onSubmit={submit} className="space-y-2 text-sm">
      <div className="grid grid-cols-2 gap-2">
        <label className="space-y-1"><span className="text-xs text-slate-500">From</span>
          <select className={input} value={form.from} onChange={set("from")}>
            <option value="">{hasProfile ? "My home (let the agent pick)" : "— choose —"}</option>
            {airports.map((a) => <option key={a.code} value={a.code}>{a.city} ({a.code})</option>)}
          </select>
        </label>
        <label className="space-y-1"><span className="text-xs text-slate-500">To</span>
          <select className={input} value={form.to} onChange={set("to")}>
            {airports.map((a) => <option key={a.code} value={a.code}>{a.city} ({a.code})</option>)}
          </select>
        </label>
        <label className="space-y-1"><span className="text-xs text-slate-500">Depart</span>
          <input type="date" className={input} value={form.depart} onChange={set("depart")} required />
        </label>
        <label className="space-y-1"><span className="text-xs text-slate-500">Return (optional)</span>
          <input type="date" className={input} value={form.ret} min={form.depart} onChange={set("ret")} />
        </label>
        <label className="space-y-1"><span className="text-xs text-slate-500">Travellers</span>
          <input type="number" min="1" max="9" className={input} value={form.travellers} onChange={set("travellers")} />
        </label>
        <label className="space-y-1"><span className="text-xs text-slate-500">Cabin</span>
          <select className={input} value={form.cabin} onChange={set("cabin")}>
            <option value="economy">Economy</option><option value="premium_economy">Premium economy</option><option value="business">Business</option>
          </select>
        </label>
        <label className="space-y-1"><span className="text-xs text-slate-500">Budget £ (optional)</span>
          <input type="number" min="0" className={input} value={form.budget} onChange={set("budget")} placeholder="e.g. 800" />
        </label>
        <label className="flex items-end gap-2 pb-2"><input type="checkbox" checked={form.hotel} onChange={set("hotel")} className="h-4 w-4 accent-indigo-600" /> <span>Need a hotel</span></label>
      </div>
      <textarea className={input} rows="2" placeholder="Anything else? e.g. aisle seat, travelling with a toddler…" value={form.notes} onChange={set("notes")} />
      <button disabled={disabled} className="w-full rounded-md bg-indigo-600 px-3 py-2 font-medium text-white hover:bg-indigo-700 disabled:opacity-50">✈️ Plan my trip</button>
    </form>
  );
}

// ---------------------------------------------------------------- chat
function MessageMeta({ result }) {
  const steps = result.trace || [];
  const count = (k) => steps.filter((s) => s.kind === k).length;
  const pills = [
    result.context?.rag?.length ? `📚 ${result.context.rag.length} docs` : null,
    result.context?.graph ? `🕸️ ${result.context.graph.triples.length} facts` : null,
    count("skill") ? `🧩 ${steps.filter((s) => s.kind === "skill").map((s) => s.title.replace("Loaded skill: ", "")).join(", ")}` : null,
    count("mcp") ? `🔌 ${count("mcp")} MCP call${count("mcp") > 1 ? "s" : ""}` : null,
    count("memory") ? `💾 memory updated` : null,
  ].filter(Boolean);
  if (!pills.length) return <div className="mt-2 text-xs text-slate-400">No context augmentation - plain LLM + tools</div>;
  return <div className="mt-2 flex flex-wrap gap-1">{pills.map((p) => <span key={p} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{p}</span>)}</div>;
}

function Chat({ messages, loading, selected, onSelect, onSend, examples }) {
  const [text, setText] = useState("");
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);
  const send = (e) => { e.preventDefault(); if (text.trim() && !loading) { onSend(text.trim()); setText(""); } };

  return (
    <div className="flex h-full flex-col rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="mx-auto max-w-md pt-10 text-center text-slate-500">
            <div className="text-4xl">🧳</div>
            <p className="mt-2 font-medium text-slate-700">Where would you like to go?</p>
            <p className="mt-1 text-sm">Use the trip form, type a request, or try an example:</p>
            <div className="mt-4 space-y-2">
              {examples.map((ex) => (
                <button key={ex} onClick={() => onSend(ex)} className="block w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-sm hover:border-indigo-400 hover:bg-indigo-50">{ex}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => m.role === "user" ? (
          <div key={i} className="flex justify-end">
            <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2 text-sm text-white">{m.content}</div>
          </div>
        ) : (
          <div key={i} className="flex">
            <div onClick={() => onSelect(i)}
              className={`max-w-[92%] cursor-pointer rounded-2xl rounded-bl-sm border px-4 py-2 text-sm transition ${selected === i ? "border-indigo-400 bg-indigo-50/40 ring-1 ring-indigo-300" : "border-slate-200 bg-slate-50 hover:border-slate-300"}`}>
              <div className="md" dangerouslySetInnerHTML={renderMarkdown(m.content)} />
              {m.result && <MessageMeta result={m.result} />}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span className="flex gap-1">{[0, 1, 2].map((d) => <span key={d} className="h-2 w-2 animate-bounce rounded-full bg-indigo-400" style={{ animationDelay: `${d * 0.15}s` }} />)}</span>
            Agent is retrieving context and calling tools…
          </div>
        )}
        <div ref={endRef} />
      </div>
      <form onSubmit={send} className="flex gap-2 border-t border-slate-100 p-3">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask the travel agent… (e.g. “yes, book it”)"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
        <button disabled={loading || !text.trim()} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">Send</button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------- inspector (right panel)
function TraceView({ steps }) {
  if (!steps?.length) return <Empty text="Send a message to see each step the agent takes." />;
  return (
    <ol className="space-y-2">
      {steps.map((s, i) => {
        const k = KIND_STYLE[s.kind] || KIND_STYLE.llm;
        return (
          <li key={i} className={`rounded-lg border px-3 py-2 text-xs ${k.cls}`}>
            <details>
              <summary className="cursor-pointer list-none">
                <span className="mr-1">{k.icon}</span><span className="font-semibold">{k.label}</span>
                <span className="ml-1">{s.title}</span>
                {s.ms !== undefined && <span className="float-right opacity-60">{s.ms} ms</span>}
              </summary>
              {s.detail != null && (
                <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-white/70 p-2 text-[11px] text-slate-700">
                  {typeof s.detail === "string" ? s.detail : JSON.stringify(s.detail, null, 2)}
                </pre>
              )}
            </details>
          </li>
        );
      })}
    </ol>
  );
}

function RagView({ chunks }) {
  if (!chunks?.length) return <Empty text="No knowledge retrieved (RAG off, or nothing relevant)." />;
  const max = Math.max(...chunks.map((c) => c.score));
  return (
    <div className="space-y-2">
      {chunks.map((c, i) => (
        <div key={c.id} className="rounded-lg border border-slate-200 p-3 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-slate-700">[{i + 1}] {c.title}</span>
            <span className="shrink-0 font-mono text-slate-500">{c.score.toFixed(3)}</span>
          </div>
          <div className="my-1.5 h-1.5 rounded bg-slate-100"><div className="h-1.5 rounded bg-sky-500" style={{ width: `${(c.score / max) * 100}%` }} /></div>
          <p className="text-slate-600">{c.text}</p>
          <p className="mt-1 text-slate-400">source: knowledge_base/{c.source}</p>
        </div>
      ))}
    </div>
  );
}

// A tiny force-directed layout so the subgraph can be drawn without a graph library
function useForceLayout(nodes, edges, width, height) {
  return useMemo(() => {
    const pos = {};
    nodes.forEach((n, i) => {
      const a = (2 * Math.PI * i) / nodes.length;
      pos[n.id] = n.type === "Traveller" ? { x: width / 2, y: height / 2 } : { x: width / 2 + Math.cos(a) * width * 0.35, y: height / 2 + Math.sin(a) * height * 0.35 };
    });
    for (let iter = 0; iter < 250; iter++) {
      const force = Object.fromEntries(nodes.map((n) => [n.id, { x: 0, y: 0 }]));
      for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
        const a = pos[nodes[i].id], b = pos[nodes[j].id];
        let dx = a.x - b.x, dy = a.y - b.y; const d2 = Math.max(dx * dx + dy * dy, 25); const f = 2200 / d2;
        const d = Math.sqrt(d2); dx /= d; dy /= d;
        force[nodes[i].id].x += dx * f; force[nodes[i].id].y += dy * f; force[nodes[j].id].x -= dx * f; force[nodes[j].id].y -= dy * f;
      }
      edges.forEach((e) => {
        const a = pos[e.source], b = pos[e.target]; if (!a || !b) return;
        // Spring pulling linked nodes towards a rest length of 60px
        const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - 60) * 0.05;
        force[e.source].x += (dx / d) * f; force[e.source].y += (dy / d) * f;
        force[e.target].x -= (dx / d) * f; force[e.target].y -= (dy / d) * f;
      });
      nodes.forEach((n) => {
        const p = pos[n.id], f = force[n.id];
        f.x += (width / 2 - p.x) * 0.01; f.y += (height / 2 - p.y) * 0.01;
        p.x = Math.min(width - 20, Math.max(20, p.x + Math.max(-8, Math.min(8, f.x))));
        p.y = Math.min(height - 14, Math.max(14, p.y + Math.max(-8, Math.min(8, f.y))));
      });
    }
    return pos;
  }, [nodes, edges, width, height]);
}

function GraphView({ graph }) {
  const [hover, setHover] = useState(null);
  const W = 380, H = 340;
  const nodes = graph?.nodes || [], edges = graph?.edges || [];
  const pos = useForceLayout(nodes, edges, W, H);
  if (!graph) return <Empty text="Context graph is switched off for this turn." />;
  const touching = (e) => hover && (e.source === hover || e.target === hover);

  return (
    <div className="space-y-3 text-xs">
      {graph.profile && (
        <div className="rounded-lg bg-rose-50 p-3 ring-1 ring-rose-200">
          <div className="font-semibold text-rose-800">{graph.profile.name}</div>
          <div className="text-rose-700">{graph.profile.role} · home {graph.profile.home_city} · party of {graph.profile.party_size}</div>
          <div className="mt-1 text-rose-700">Prefers: {graph.profile.preferences.join("; ")}</div>
        </div>
      )}
      {graph.insights?.length > 0 && (
        <div>
          <h3 className="mb-1 font-semibold text-slate-700">Derived insights (multi-hop reasoning)</h3>
          <ul className="list-disc space-y-1 pl-4 text-slate-600">{graph.insights.map((s, i) => <li key={i}>{s}</li>)}</ul>
        </div>
      )}
      {nodes.length > 0 && (
        <div>
          <h3 className="mb-1 font-semibold text-slate-700">Retrieved subgraph <span className="font-normal text-slate-400">(hover a node)</span></h3>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-lg bg-slate-50 ring-1 ring-slate-200">
            {edges.map((e, i) => pos[e.source] && pos[e.target] && (
              <g key={i}>
                <line x1={pos[e.source].x} y1={pos[e.source].y} x2={pos[e.target].x} y2={pos[e.target].y}
                  stroke={touching(e) ? "#4f46e5" : "#cbd5e1"} strokeWidth={touching(e) ? 1.6 : 0.8} />
                {touching(e) && <text x={(pos[e.source].x + pos[e.target].x) / 2} y={(pos[e.source].y + pos[e.target].y) / 2} fontSize="7" fill="#4338ca" textAnchor="middle">{e.relation}</text>}
              </g>
            ))}
            {nodes.map((n) => pos[n.id] && (
              <g key={n.id} onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} className="cursor-pointer">
                <circle cx={pos[n.id].x} cy={pos[n.id].y} r={n.type === "Traveller" ? 9 : 5.5} fill={NODE_COLOURS[n.type] || "#64748b"} stroke="white" strokeWidth="1.5" />
                {(hover === n.id || n.type === "Traveller" || n.type === "City") && (
                  <text x={pos[n.id].x} y={pos[n.id].y - 9} fontSize="8" textAnchor="middle" fill="#0f172a" style={{ paintOrder: "stroke", stroke: "white", strokeWidth: 3 }}>{n.label}</text>
                )}
              </g>
            ))}
          </svg>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
            {Object.entries(NODE_COLOURS).map(([t, c]) => <span key={t} className="flex items-center gap-1 text-[10px] text-slate-500"><span className="h-2 w-2 rounded-full" style={{ background: c }} />{t}</span>)}
          </div>
        </div>
      )}
      <details>
        <summary className="cursor-pointer font-semibold text-slate-700">Facts passed to the LLM ({graph.triples.length})</summary>
        <ul className="mt-1 space-y-0.5 font-mono text-[10px] text-slate-600">{graph.triples.map((t, i) => <li key={i}>{t}</li>)}</ul>
      </details>
    </div>
  );
}

function SkillsView({ skills, loaded, steps }) {
  const instructions = Object.fromEntries((steps || []).filter((s) => s.kind === "skill").map((s) => [s.title.replace("Loaded skill: ", ""), s.detail]));
  return (
    <div className="space-y-2 text-xs">
      <p className="text-slate-500">Only the one-line descriptions sit in the prompt. The agent loads a skill's full instructions on demand (progressive disclosure).</p>
      {skills.map((s) => {
        const isLoaded = loaded.includes(s.name);
        return (
          <div key={s.name} className={`rounded-lg border p-3 ${isLoaded ? "border-amber-300 bg-amber-50" : "border-slate-200"}`}>
            <div className="flex items-center justify-between">
              <span className="font-mono font-semibold">🧩 {s.name}</span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] ${isLoaded ? "bg-amber-200 text-amber-900" : "bg-slate-100 text-slate-500"}`}>{isLoaded ? "loaded" : "available"}</span>
            </div>
            <p className="mt-1 text-slate-600">{s.description}</p>
            {instructions[s.name] && typeof instructions[s.name] === "string" && (
              <details className="mt-2"><summary className="cursor-pointer text-amber-800">Instructions loaded this turn</summary>
                <div className="md mt-1 rounded bg-white p-2" dangerouslySetInnerHTML={renderMarkdown(instructions[s.name])} />
              </details>
            )}
          </div>
        );
      })}
    </div>
  );
}

function BookingsView({ bookings }) {
  if (!bookings?.length) return <Empty text="No bookings yet. The agent will ask you to confirm before booking." />;
  return (
    <div className="space-y-2 text-xs">
      {bookings.map((b) => (
        <div key={b.confirmation} className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
          <div className="flex justify-between font-semibold text-emerald-900">
            <span>{b.type === "flight" ? "✈️" : "🏨"} {b.confirmation}</span><span>£{b.total_price_gbp.toFixed(2)}</span>
          </div>
          {b.type === "flight" ? (
            <div className="mt-1 text-emerald-800">
              {b.flight.airline} {b.flight.flight_number} · {b.flight.origin} → {b.flight.destination}{b.flight.via ? ` via ${b.flight.via}` : ""}<br />
              {b.flight.departure_time} · {b.cabin.replace("_", " ")} · {b.passengers} pax · {b.passenger_name}
            </div>
          ) : (
            <div className="mt-1 text-emerald-800">{b.hotel.name} ({b.hotel.stars}★) · {b.hotel.check_in} · {b.nights} nights · {b.guest_name}</div>
          )}
        </div>
      ))}
    </div>
  );
}

const Empty = ({ text }) => <p className="py-8 text-center text-xs text-slate-400">{text}</p>;

function Inspector({ result, config, bookings }) {
  const [tab, setTab] = useState("trace");
  const tabs = [
    ["trace", "🧭 Trace"], ["rag", "📚 RAG"], ["graph", "🕸️ Graph"], ["skills", "🧩 Skills"], ["bookings", `🎫 Bookings${bookings.length ? ` (${bookings.length})` : ""}`],
  ];
  return (
    <div className="flex h-full flex-col rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
      <div className="flex gap-1 overflow-x-auto border-b border-slate-100 p-2">
        {tabs.map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} className={`whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium ${tab === id ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {tab === "trace" && <TraceView steps={result?.trace} />}
        {tab === "rag" && <RagView chunks={result?.context?.rag} />}
        {tab === "graph" && (result ? <GraphView graph={result.context?.graph} /> : <Empty text="Send a message to see the retrieved subgraph." />)}
        {tab === "skills" && <SkillsView skills={config.skills} loaded={result?.context?.skills_loaded || []} steps={result?.trace} />}
        {tab === "bookings" && <BookingsView bookings={bookings} />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- app
function App() {
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(null);
  const [travellerId, setTravellerId] = useState("traveller:alex");
  const [opts, setOpts] = useState({ use_rag: true, use_graph: true, use_skills: true });
  const [sessionId, setSessionId] = useState(newSessionId);
  const [messages, setMessages] = useState([]);
  const [selected, setSelected] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api("/api/config").then(setConfig).catch((e) => setError(e.message)); }, []);

  const reset = async () => {
    await api("/api/reset", { session_id: sessionId }).catch(() => {});
    setSessionId(newSessionId()); setMessages([]); setSelected(null); setBookings([]);
  };
  const changeTraveller = (id) => { setTravellerId(id); reset(); };

  const send = async (text) => {
    const history = [...messages, { role: "user", content: text }];
    setMessages(history); setLoading(true);
    try {
      const result = await api("/api/chat", { session_id: sessionId, message: text, traveller_id: travellerId, ...opts });
      setMessages([...history, { role: "assistant", content: result.reply, result }]);
      setSelected(history.length);
      setBookings(result.bookings || []);
    } catch (e) {
      setMessages([...history, { role: "assistant", content: `⚠️ Request failed: ${e.message}` }]);
    } finally { setLoading(false); }
  };

  if (error) return <div className="p-8 text-red-700">Could not reach the API: {error}. Is <code>python server.py</code> running?</div>;
  if (!config) return <div className="p-8 text-slate-500">Connecting to the agent…</div>;

  const selectedResult = selected != null ? messages[selected]?.result : null;
  const toggle = (k) => (v) => setOpts({ ...opts, [k]: v });

  return (
    <div className="flex h-screen flex-col">
      <header className="flex flex-wrap items-center justify-between gap-2 bg-gradient-to-r from-indigo-700 to-violet-700 px-5 py-3 text-white shadow">
        <div>
          <h1 className="text-lg font-semibold">✈️ Context-Engineered Travel Agent</h1>
          <p className="text-xs text-indigo-100">Example 3 · RAG + Context Graph + Skills + MCP · Dundee Data Meetup</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={`rounded-full px-2.5 py-1 ${config.mode === "openai" ? "bg-emerald-500/90" : "bg-amber-500/90"}`}>
            {config.mode === "openai" ? `🤖 ${config.model}` : "🛠️ Offline planner (set OPENAI_API_KEY for the LLM)"}
          </span>
          <span className="rounded-full bg-white/15 px-2.5 py-1">🔌 {config.mcp_tools.length} MCP tools</span>
          <span className="rounded-full bg-white/15 px-2.5 py-1">📚 {config.knowledge_chunks} chunks</span>
          <span className="rounded-full bg-white/15 px-2.5 py-1">🕸️ {config.graph.nodes} nodes / {config.graph.edges} edges</span>
          <button onClick={reset} className="rounded-full bg-white px-3 py-1 font-medium text-indigo-700 hover:bg-indigo-50">↺ New conversation</button>
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto p-4 lg:grid-cols-[300px_minmax(0,1fr)_420px] lg:overflow-hidden">
        <aside className="space-y-4 lg:overflow-y-auto">
          <Card title="👤 Who is travelling?"><TravellerPicker travellers={config.travellers} value={travellerId} onChange={changeTraveller} /></Card>
          <Card title="🧠 Context augmentation" right={<span className="text-[10px] text-slate-400">applies to next message</span>}>
            <Toggle icon="📚" label="RAG" hint="Retrieve policies & guides from the knowledge base" checked={opts.use_rag} onChange={toggle("use_rag")} />
            <Toggle icon="🕸️" label="Context graph" hint="Traveller profile, relationships, memory" checked={opts.use_graph} onChange={toggle("use_graph")} />
            <Toggle icon="🧩" label="Skills" hint="Load expert procedures on demand" checked={opts.use_skills} onChange={toggle("use_skills")} />
            <Toggle icon="🔌" label="MCP tools" hint="Always on - the agent's hands (search & book)" checked={true} disabled onChange={() => {}} />
          </Card>
          <Card title="🗺️ Trip request"><TripForm airports={config.airports} hasProfile={!!travellerId} onSubmit={send} disabled={loading} /></Card>
        </aside>

        <section className="min-h-[60vh] lg:min-h-0">
          <Chat messages={messages} loading={loading} selected={selected} onSelect={setSelected} onSend={send} examples={EXAMPLES[travellerId] || EXAMPLES[""]} />
        </section>

        <section className="min-h-[60vh] lg:min-h-0">
          <Inspector result={selectedResult} config={config} bookings={bookings} />
        </section>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
