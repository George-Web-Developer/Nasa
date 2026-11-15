import React, { useState, useEffect, useRef } from "react";

/**
 * AstroChat React Component
 * NASA Space Apps Challenge 2026 - Health Monitoring Software
 *
 * Drop-in React chat component for embedding the astronaut psychological check-in assistant
 * directly into the main teammate web application or mission telemetry dashboard.
 *
 * Props:
 * @param {string} apiBase - Base URL of the backend API (e.g., "http://localhost:8000" or production URL)
 * @param {number} astronautId - ID of the astronaut conducting check-in (e.g., 1)
 * @param {number} missionDay - Current mission flight day (e.g., 42)
 * @param {string} language - Preferred language ("en" or "ar")
 * @param {function} onSessionCompleted - Optional callback when daily check-in analysis finishes
 * @param {function} onEscalate - Optional callback when crisis escalation is triggered
 */
export default function AstroChat({
  apiBase = "http://localhost:8000",
  astronautId = 1,
  missionDay = 42,
  language = "en",
  onSessionCompleted = null,
  onEscalate = null,
}) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [mode, setMode] = useState("session"); // "session" | "companion"
  const [isLoading, setIsLoading] = useState(false);
  const [sessionShouldEnd, setSessionShouldEnd] = useState(false);
  const [isEscalated, setIsEscalated] = useState(false);
  const [currentLang, setCurrentLang] = useState(language);

  const messagesEndRef = useRef(null);
  const isArabic = currentLang === "ar";

  // Auto-scroll to bottom of conversation
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Start Check-in Session on Mount
  useEffect(() => {
    let isMounted = true;

    async function initSession() {
      setIsLoading(true);
      try {
        const response = await fetch(`${apiBase}/sessions/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            astronaut_id: astronautId,
            mission_day: missionDay,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to initialize session: HTTP ${response.status}`);
        }

        const data = await response.json();
        if (isMounted) {
          setSessionId(data.session_id);

          // Detect Arabic script automatically if first message contains Arabic characters
          if (/[\u0600-\u06FF]/.test(data.first_message)) {
            setCurrentLang("ar");
          }

          setMessages([
            {
              role: "assistant",
              content: data.first_message,
              time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            },
          ]);
        }
      } catch (err) {
        console.error("Session start error:", err);
        if (isMounted) {
          setMessages([
            {
              role: "assistant",
              content: isArabic
                ? "تعذر بدء الجلسة. يرجى التحقق من اتصال الخادم."
                : "Unable to connect to check-in server. Please ensure backend is running.",
              time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            },
          ]);
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    initSession();

    return () => {
      isMounted = false;
    };
  }, [apiBase, astronautId, missionDay]);

  // Handle User Message Submission
  const handleSendMessage = async (e) => {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (!trimmed || !sessionId || isLoading) return;

    const userMsg = {
      role: "user",
      content: trimmed,
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    setIsLoading(true);

    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: trimmed,
        }),
      });

      if (!response.ok) {
        throw new Error(`Chat error: HTTP ${response.status}`);
      }

      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.reply,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);

      if (data.escalate) {
        setIsEscalated(true);
        if (onEscalate) onEscalate(data);
      }

      const shouldEnd = data.session_should_end || data.should_end;
      if (shouldEnd && mode === "session") {
        setSessionShouldEnd(true);
        // Automatically finalize session & trigger analyzer
        try {
          const endRes = await fetch(`${apiBase}/sessions/${sessionId}/end`, {
            method: "POST",
          });
          if (endRes.ok && onSessionCompleted) {
            const analysisData = await endRes.json();
            onSessionCompleted(analysisData);
          }
        } catch (endErr) {
          console.warn("End session notice:", endErr);
        }
      }
    } catch (err) {
      console.error("Chat communication error:", err);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: isArabic ? "حدث خطأ أثناء معالجة الرسالة." : "An error occurred while communicating with the assistant.",
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Switch to Companion Mode
  const handleSwitchToCompanion = async () => {
    if (!sessionId) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${apiBase}/sessions/${sessionId}/companion`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error(`Companion switch error: HTTP ${response.status}`);
      }

      const data = await response.json();
      setMode("companion");
      setSessionShouldEnd(false);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.opening_message,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } catch (err) {
      console.error("Failed to switch to companion mode:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: "100%",
        maxWidth: "500px",
        height: "640px",
        backgroundColor: "#0b0f19",
        color: "#e2e8f0",
        borderRadius: "16px",
        border: "1px solid #1e293b",
        boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5)",
        overflow: "hidden",
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        direction: isArabic ? "rtl" : "ltr",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 18px",
          backgroundColor: "#111827",
          borderBottom: "1px solid #1f2937",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "50%",
              background: "linear-gradient(135deg, #0284c7, #38bdf8)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "16px",
            }}
          >
            🚀
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 600, color: "#f8fafc" }}>
              {isArabic ? "المساعد النفسي لرائد الفضاء" : "Astronaut Check-in Assistant"}
            </h3>
            <p style={{ margin: 0, fontSize: "11px", color: "#94a3b8" }}>
              {isArabic
                ? `يوم المهمة ${missionDay} • رائد الفضاء #${astronautId}`
                : `Mission Day ${missionDay} • Astronaut #${astronautId}`}
            </p>
          </div>
        </div>

        <span
          style={{
            fontSize: "11px",
            padding: "4px 10px",
            borderRadius: "999px",
            backgroundColor: mode === "companion" ? "#4338ca" : "#0369a1",
            color: "#ffffff",
            fontWeight: 500,
            textTransform: "uppercase",
            letterSpacing: "0.5px",
          }}
        >
          {mode === "companion"
            ? isArabic ? "الرفيق" : "Companion"
            : isArabic ? "فحص يومي" : "Check-in"}
        </span>
      </div>

      {/* Escalation Safety Banner */}
      {isEscalated && (
        <div
          style={{
            backgroundColor: "#451a03",
            color: "#fef3c7",
            borderBottom: "1px solid #92400e",
            padding: "10px 16px",
            fontSize: "12px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span>🛡️</span>
          <span>
            {isArabic
              ? "تم إشعار طبيب الرحلة والدعم الأرضي. لست وحدك، الفريق يتابعك بكل عناية."
              : "Flight surgeon and ground support notified. You are not alone. Reassuring support active."}
          </span>
        </div>
      )}

      {/* Message List */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
          backgroundColor: "#0b0f19",
        }}
      >
        {messages.map((msg, index) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={index}
              style={{
                alignSelf: isUser ? "flex-end" : "flex-start",
                maxWidth: "80%",
                padding: "10px 14px",
                borderRadius: "12px",
                backgroundColor: isUser ? "#0284c7" : "#1e293b",
                color: "#f8fafc",
                fontSize: "13.5px",
                lineHeight: "1.5",
                border: isUser ? "none" : "1px solid #334155",
              }}
            >
              <div>{msg.content}</div>
              <div
                style={{
                  fontSize: "10px",
                  color: "rgba(255, 255, 255, 0.5)",
                  marginTop: "4px",
                  textAlign: isUser ? "right" : "left",
                }}
              >
                {msg.time}
              </div>
            </div>
          );
        })}

        {/* Typing indicator */}
        {isLoading && (
          <div
            style={{
              alignSelf: "flex-start",
              padding: "8px 14px",
              backgroundColor: "#1e293b",
              borderRadius: "12px",
              fontSize: "12px",
              color: "#94a3b8",
            }}
          >
            {isArabic ? "جاري التفكير والكتابة..." : "Assistant is typing..."}
          </div>
        )}

        {/* Transition Card when check-in questions completed */}
        {sessionShouldEnd && mode === "session" && (
          <div
            style={{
              backgroundColor: "#1e1b4b",
              border: "1px solid #4338ca",
              borderRadius: "12px",
              padding: "14px",
              textAlign: "center",
              marginTop: "8px",
            }}
          >
            <div style={{ fontSize: "13px", fontWeight: 600, color: "#c7d2fe", marginBottom: "8px" }}>
              {isArabic ? "اكتمل الفحص اليومي بنجاح." : "Daily Check-in Complete"}
            </div>
            <button
              onClick={handleSwitchToCompanion}
              style={{
                backgroundColor: "#4f46e5",
                color: "#ffffff",
                border: "none",
                padding: "8px 18px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              {isArabic ? "مواصلة الحديث (وضع الرفيق)" : "Keep Talking (Companion Mode)"}
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form
        onSubmit={handleSendMessage}
        style={{
          display: "flex",
          gap: "8px",
          padding: "12px 14px",
          backgroundColor: "#111827",
          borderTop: "1px solid #1f2937",
        }}
      >
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={isArabic ? "اكتب رسالتك هنا..." : "Type your message..."}
          disabled={isLoading}
          style={{
            flex: 1,
            backgroundColor: "#1f2937",
            border: "1px solid #374151",
            borderRadius: "8px",
            padding: "10px 14px",
            color: "#f9fafb",
            fontSize: "13.5px",
            outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={isLoading || !inputValue.trim()}
          style={{
            backgroundColor: "#0284c7",
            color: "#ffffff",
            border: "none",
            borderRadius: "8px",
            padding: "0 18px",
            fontWeight: 600,
            fontSize: "13.5px",
            cursor: isLoading || !inputValue.trim() ? "not-allowed" : "pointer",
            opacity: isLoading || !inputValue.trim() ? 0.6 : 1,
          }}
        >
          {isArabic ? "إرسال" : "Send"}
        </button>
      </form>
    </div>
  );
}
