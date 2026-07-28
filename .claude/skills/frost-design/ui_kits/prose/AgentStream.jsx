/* Prose · AgentStream — the center column. User bubbles, agent messages with
   tool chips, a suggestions row, and the composer field. */
(function () {
  const { ToolChip, Field, IconButton, Button } = window.FrostDesignSystemProse_5680eb;
  const { useState, useRef, useEffect } = React;

  // Render **bold** spans inside agent text.
  function RichText({ text }) {
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return (
      <p style={{ fontSize: 14, lineHeight: 1.75, color: "var(--label)", margin: 0 }}>
        {parts.map((p, i) =>
          p.startsWith("**") ? (
            <strong key={i} style={{ fontWeight: 600 }}>{p.slice(2, -2)}</strong>
          ) : (
            <React.Fragment key={i}>{p}</React.Fragment>
          )
        )}
      </p>
    );
  }

  function UserBubble({ text }) {
    return (
      <div
        style={{
          alignSelf: "flex-end",
          maxWidth: "78%",
          background: "var(--blue)",
          color: "#fff",
          padding: "9px 15px",
          borderRadius: "16px 16px 4px 16px",
          fontSize: 14,
          lineHeight: 1.65,
        }}
      >
        {text}
      </div>
    );
  }

  function AgentMessage({ msg }) {
    return (
      <div style={{ maxWidth: "88%", display: "flex", flexDirection: "column", gap: 10 }}>
        {(msg.chips || []).map((c, i) => (
          <ToolChip key={i} {...c} />
        ))}
        {msg.text ? <RichText text={msg.text} /> : null}
      </div>
    );
  }

  function AgentStream({ data }) {
    const [thread, setThread] = useState(data.thread);
    const [draft, setDraft] = useState("");
    const [busy, setBusy] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    }, [thread]);

    function send(text) {
      const value = (text != null ? text : draft).trim();
      if (!value || busy) return;
      setDraft("");
      setBusy(true);
      setThread((t) => [...t, { role: "user", text: value }]);
      // Fake the agent working, then drop in the canned reply.
      setTimeout(() => {
        setThread((t) => [...t, data.reply]);
        setBusy(false);
      }, 950);
    }

    return (
      <div style={{ background: "var(--surface)", display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div
          ref={scrollRef}
          style={{ flex: 1, overflow: "auto", padding: "26px 30px 12px", display: "flex", flexDirection: "column", gap: 18 }}
        >
          {thread.map((m, i) =>
            m.role === "user" ? <UserBubble key={i} text={m.text} /> : <AgentMessage key={i} msg={m} />
          )}
          {busy ? (
            <div style={{ maxWidth: "88%" }}>
              <ToolChip running label="正在生成…" />
            </div>
          ) : null}
        </div>

        <div style={{ padding: "10px 22px 4px", display: "flex", gap: 8, flexWrap: "wrap" }}>
          {data.suggestions.map((s) => (
            <Button key={s} variant="default" size="sm" onClick={() => send(s)}>{s}</Button>
          ))}
        </div>

        <div style={{ padding: "8px 22px 18px" }}>
          <Field
            size="lg"
            icon="plus-circle"
            placeholder="向智能体描述下一步…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            inputProps={{ onKeyDown: (e) => { if (e.key === "Enter") send(); } }}
            trailing={<IconButton icon="paper-plane-tilt" label="发送" filled onClick={() => send()} />}
          />
        </div>
      </div>
    );
  }

  window.ProseAgentStream = AgentStream;
})();
