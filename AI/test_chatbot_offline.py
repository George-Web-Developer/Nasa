import http.server
import json
import re
import socketserver
import subprocess
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_nasa_data import CHROME, ROOT, eval_js_in_chrome


class TestChatbotIntegrationAndOffline(unittest.TestCase):
    def test_app_shell_head_load_and_dynamic_api_base(self):
        res = eval_js_in_chrome(
            """
            localStorage.clear();
            const S = window.BioShell;
            if (!S) throw new Error('window.BioShell missing');
            if (typeof S.getChatbotApiBase !== 'function' || typeof S.setChatbotApiBase !== 'function' || typeof S.resolveChatbotApiBase !== 'function') {
              throw new Error('Dynamic API base helpers missing on BioShell');
            }
            const localDefault = S.getChatbotApiBase();
            const remoteUnconfigured = S.resolveChatbotApiBase({ protocol: 'https:', hostname: 'example.github.io', search: '' });
            S.setChatbotApiBase('https://bio-astro-bot.onrender.com///');
            const afterSet = S.CHATBOT_API_BASE;
            const remoteConfigured = S.resolveChatbotApiBase({ protocol: 'https:', hostname: 'example.github.io', search: '' });
            S.setChatbotApiBase('');
            const afterReset = S.getChatbotApiBase();
            return { localDefault, remoteUnconfigured, afterSet, remoteConfigured, afterReset };
            """,
            extra_scripts=["nasa-data.js", "ai-model.js", "app-shell.js"],
        )
        self.assertTrue(res.get("ok"), f"Chrome JS evaluation failed: {res.get('error')}")
        d = res["data"]
        self.assertEqual(d["localDefault"], "http://127.0.0.1:8000")
        self.assertEqual(d["remoteUnconfigured"], "")
        self.assertEqual(d["afterSet"], "https://bio-astro-bot.onrender.com")
        self.assertEqual(d["remoteConfigured"], "https://bio-astro-bot.onrender.com")
        self.assertEqual(d["afterReset"], "http://127.0.0.1:8000")

    def test_widget_offline_mode_shortcircuits_fetch_and_replies_via_copilot(self):
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(ROOT), **kwargs)

            def do_GET(self):
                if self.path == "/__widget_offline_test__.html":
                    html_txt = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="/nasa-data.js"></script>
<script src="/ai-model.js"></script>
<script src="/Chat%20Bot/web/widget.js"></script>
</head><body>
<pre id="out"></pre>
<script>
(async function () {
  let fetchCalls = 0;
  window.fetch = function () {
    fetchCalls += 1;
    return Promise.reject(new Error('network disabled in test'));
  };

  const el = document.createElement('astro-chat');
  el.setAttribute('mode', 'tab');
  el.setAttribute('api-base', '');
  el.setAttribute('language', 'en');
  document.body.appendChild(el);

  await new Promise((r) => setTimeout(r, 120));
  const callsAfterInit = fetchCalls;

  const input = el.shadowRoot.getElementById('messageInput');
  const form = el.shadowRoot.getElementById('chatForm');
  input.value = 'How to manage station radiation?';
  form.dispatchEvent(new Event('submit', { cancelable: true }));

  await new Promise((r) => setTimeout(r, 150));
  const msgs = Array.from(el.shadowRoot.querySelectorAll('.astro-msg')).map((m) => m.textContent || '');
  document.getElementById('out').textContent = JSON.stringify({
    callsAfterInit,
    callsAfterSend: fetchCalls,
    isBackendOffline: Boolean(el.isBackendOffline),
    msgs,
  });
})();
</script>
</body></html>"""
                    raw = html_txt.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                super().do_GET()

            def log_message(self, format, *args):
                pass

        with socketserver.TCPServer(("127.0.0.1", 0), QuietHandler) as httpd:
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                proc = subprocess.run(
                    [
                        CHROME,
                        "--headless=new",
                        "--disable-gpu",
                        "--virtual-time-budget=2500",
                        "--dump-dom",
                        f"http://127.0.0.1:{port}/__widget_offline_test__.html",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=25,
                )
                m = re.search(r'<pre id="out">(.*?)</pre>', proc.stdout, re.S)
                self.assertIsNotNone(m, f"#out missing: {proc.stdout[-800:]}")
                raw = m.group(1).replace("&quot;", '"').replace("&amp;", "&")
                d = json.loads(raw)
                self.assertEqual(d["callsAfterInit"], 0, "Empty api-base should not call window.location.origin")
                self.assertEqual(d["callsAfterSend"], 0, "Offline widget must not retry failed fetch on every user message")
                self.assertTrue(d["isBackendOffline"])
                self.assertTrue(any("Live ML Assessment:" in msg for msg in d["msgs"]), f"Expected Offline Copilot reply in {d['msgs']}")
            finally:
                httpd.shutdown()

    def test_assistant_page_viewport_fit_and_backend_url_controls(self):
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(ROOT), **kwargs)

            def do_GET(self):
                if self.path == "/assistant.html?test_layout=1":
                    html_txt = (ROOT / "assistant.html").read_text(encoding="utf-8")
                    probe = """
<script>
window.addEventListener('load', function () {
  setTimeout(function () {
    const widget = document.querySelector('#assistantChatMount astro-chat');
    const footer = widget && widget.shadowRoot ? widget.shadowRoot.getElementById('chatForm') : null;
    const rect = footer ? footer.getBoundingClientRect() : null;
    const pre = document.createElement('pre');
    pre.id = 'layout-probe';
    pre.textContent = JSON.stringify({
      innerHeight: window.innerHeight,
      footerBottom: rect ? rect.bottom : null,
      footerHeight: rect ? rect.height : null,
      hasApiInput: Boolean(document.getElementById('chatApiBaseInput')),
      hasSaveApiBtn: Boolean(document.getElementById('saveChatApiBtn')),
      hasResetApiBtn: Boolean(document.getElementById('resetChatApiBtn'))
    });
    document.body.appendChild(pre);
  }, 500);
});
</script>"""
                    raw = html_txt.replace("</body>", probe + "\n</body>").encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                super().do_GET()

            def log_message(self, format, *args):
                pass

        with socketserver.TCPServer(("127.0.0.1", 0), QuietHandler) as httpd:
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                proc = subprocess.run(
                    [
                        CHROME,
                        "--headless=new",
                        "--disable-gpu",
                        "--window-size=1280,720",
                        "--virtual-time-budget=3500",
                        "--dump-dom",
                        f"http://127.0.0.1:{port}/assistant.html?test_layout=1",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=25,
                )
                m = re.search(r'<pre id="layout-probe">(.*?)</pre>', proc.stdout, re.S)
                self.assertIsNotNone(m, f"layout-probe missing from DOM: {proc.stdout[-800:]}")
                raw = m.group(1).replace("&quot;", '"').replace("&amp;", "&")
                probe = json.loads(raw)
                self.assertTrue(probe["hasApiInput"], "assistant.html must expose #chatApiBaseInput")
                self.assertTrue(probe["hasSaveApiBtn"], "assistant.html must expose #saveChatApiBtn")
                self.assertTrue(probe["hasResetApiBtn"], "assistant.html must expose #resetChatApiBtn")
                self.assertIsNotNone(probe["footerBottom"], "chat input form must render inside Shadow DOM")
                self.assertGreater(probe["footerHeight"], 20)
                self.assertLessEqual(
                    probe["footerBottom"],
                    probe["innerHeight"],
                    f"Chat input bar pushed below 720px laptop viewport: bottom={probe['footerBottom']} > innerHeight={probe['innerHeight']}",
                )
            finally:
                httpd.shutdown()

    def test_widget_offline_7q_checkin_flow_has_zero_network_calls(self):
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(ROOT), **kwargs)

            def do_GET(self):
                if self.path == "/__widget_7q_test__.html":
                    html = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<script src="/nasa-data.js"></script>
<script src="/ai-model.js"></script>
<script src="/Chat%20Bot/web/widget.js"></script>
<astro-chat id="w7q" mode="tab" session-mode="session" api-base="" language="en"></astro-chat>
<script>
window.__fetchCalls = [];
window.fetch = function (url) {
  window.__fetchCalls.push(String(url));
  return Promise.reject(new Error('unexpected fetch'));
};
window.addEventListener('load', async function () {
  const w = document.getElementById('w7q');
  await new Promise(r => setTimeout(r, 150));
  const initialMsgs = Array.from(w.shadowRoot.querySelectorAll('.astro-msg.assistant')).map(el => el.textContent);
  for (let i = 1; i <= 7; i++) {
    w.messageInput.value = 'Answer ' + i + ' nominal sleep and focus';
    await w.handleUserSend();
  }
  const afterMsgs = Array.from(w.shadowRoot.querySelectorAll('.astro-msg.assistant')).map(el => el.textContent);
  const actionVisible = w.actionCard.classList.contains('visible');
  await w.switchToCompanion();
  const modeAfterSwitch = w.sessionMode;
  const out = document.createElement('pre');
  out.id = 'out7q';
  out.textContent = JSON.stringify({
    fetches: window.__fetchCalls.length,
    initialMsgs,
    afterCount: afterMsgs.length,
    lastMsg: afterMsgs[afterMsgs.length - 1] || '',
    actionVisible,
    modeAfterSwitch,
  });
  document.body.appendChild(out);
});
</script></body></html>"""
                    raw = html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                super().do_GET()

            def log_message(self, format, *args):
                pass

        with socketserver.TCPServer(("127.0.0.1", 0), QuietHandler) as httpd:
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                proc = subprocess.run(
                    [
                        CHROME,
                        "--headless=new",
                        "--disable-gpu",
                        "--virtual-time-budget=3000",
                        "--dump-dom",
                        f"http://127.0.0.1:{port}/__widget_7q_test__.html",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=25,
                )
                m = re.search(r'<pre id="out7q">(.*?)</pre>', proc.stdout, re.S)
                self.assertIsNotNone(m, f"#out7q missing: {proc.stdout[-800:]}")
                raw = m.group(1).replace("&quot;", '"').replace("&amp;", "&")
                d = json.loads(raw)
                self.assertEqual(d["fetches"], 0)
                self.assertTrue(any("1/7" in x for x in d["initialMsgs"]), f"Expected Q1/7 prompt, got {d['initialMsgs']}")
                self.assertTrue(d["actionVisible"], "Expected completion card visible after 7 offline answers")
                self.assertEqual(d["modeAfterSwitch"], "companion")
                self.assertIn("Live ML Assessment:", d["lastMsg"])
            finally:
                httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
