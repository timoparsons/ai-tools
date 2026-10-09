import copy, json, os, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

FAKE = ["FAKE-SECRET-aaaa1111", "sk-FAKEFAKEFAKEFAKE1234", "hunter2FAKEPASS", "FAKEHEADERVALUE99",
        "0123456789abcdef0123456789abcdef0123456789"]
CALLS = []

BASE_CLIENTS = [{
    "config": {"name": "proxmox", "client_id": "proxmox-id", "connection_type": "http",
               "connection_string": "http://user:hunter2FAKEPASS@10.1.1.5:8811/mcp?token=FAKE-SECRET-aaaa1111",
               "auth_type": "headers", "headers": {"X-Api-Key": "FAKEHEADERVALUE99"},
               "tools_to_execute": ["*"], "allow_on_all_virtual_keys": False,
               "vk_configs": [{"virtual_key_name": "claude"}]},
    "state": "healthy", "tools": [{"name": "list_lxc"}, {"name": "get_job"}]},
    {"config": {"name": "stdio1", "client_id": "stdio1", "connection_type": "stdio",
                "stdio_config": {"command": "python3", "args": ["s.py", "--token", "sk-FAKEFAKEFAKEFAKE1234", "--api-key=FAKE-SECRET-aaaa1111"],
                                 "envs": ["BIFROST_API_KEY=FAKE-SECRET-aaaa1111", "HOME"]}},
     "state": "error", "last_failure": "401 Bearer 0123456789abcdef0123456789abcdef0123456789", "tools": []},
    {"config": {"name": "bifrost_admin", "client_id": "admin-id", "connection_type": "stdio",
                "stdio_config": {"command": "python", "args": ["server.py"], "envs": []}},
     "state": "healthy", "tools": []}]
CLIENTS = copy.deepcopy(BASE_CLIENTS)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        CALLS.append(("GET", self.path, self.headers.get("Authorization")))
        p = self.path.split("?")[0]
        if p == "/api/mcp/clients": self._send({"clients": CLIENTS, "count": len(CLIENTS)})
        elif p == "/api/config": self._send({"client_config": {"drop_excess_requests": False, "allowed_origins": ["x"]},
                                           "auth_config": {"admin_username": "admin", "admin_password": "hunter2FAKEPASS"},
                                           "db": {"connection_string": "postgres://u:hunter2FAKEPASS@db/x"}})
        elif p == "/api/plugins": self._send([{"name": "p", "config": {"api_key": "FAKE-SECRET-aaaa1111", "mode": "on"}}])
        elif p in ("/health", "/api/version"): self._send({"ok": True, "v": "1.0"})
        else: self.send_response(404); self.end_headers()

    def do_POST(self):
        body = self._body()
        CALLS.append(("POST", self.path, body))
        if self.path == "/api/mcp/client":
            cfg = dict(body, client_id=body["name"] + "-id")
            CLIENTS.append({"config": cfg, "state": "healthy", "tools": []})
        self._send({"status": "ok"})

    def do_PUT(self):
        body = self._body()
        CALLS.append(("PUT", self.path, body))
        cid = self.path.rsplit("/", 1)[1]
        for c in CLIENTS:
            if c["config"]["client_id"] == cid:
                c["config"].update(body)
        self._send({"status": "ok"})

    def do_DELETE(self):
        CALLS.append(("DELETE", self.path, None))
        cid = self.path.rsplit("/", 1)[1]
        CLIENTS[:] = [c for c in CLIENTS if c["config"]["client_id"] != cid]
        self._send({"status": "ok"})


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        os.environ["BIFROST_BASE_URL"] = "http://127.0.0.1:%d" % cls.srv.server_port
        os.environ["BIFROST_API_KEY"] = "FAKE-SECRET-aaaa1111"
        global tools, api
        import tools, bifrost_api as api

    def setUp(self):
        CLIENTS[:] = copy.deepcopy(BASE_CLIENTS)
        CALLS.clear()
        for k in ("BIFROST_DISABLE_WRITES", "BIFROST_ALLOW_STDIO_CREATE"):
            os.environ.pop(k, None)

    def writes(self):
        return [c for c in CALLS if c[0] in ("POST", "PUT", "DELETE")]

    def no_leak(self, text):
        for f in FAKE:
            self.assertNotIn(f, text)

    # --- original read-side tests
    def test_outputs_have_no_secrets(self):
        for out in (tools.bifrost_list_mcp_clients(), tools.bifrost_get_mcp_client("proxmox"),
                    tools.bifrost_get_mcp_client("stdio1"), tools.bifrost_get_config(),
                    tools.bifrost_list_plugins(), tools.bifrost_status(),
                    tools.bifrost_delete_mcp_client("proxmox"),
                    tools.bifrost_update_mcp_client("proxmox", disabled=True)):
            self.no_leak(out)

    def test_useful_content_kept(self):
        d = json.loads(tools.bifrost_get_mcp_client("proxmox"))
        self.assertEqual(d["tools"], ["list_lxc", "get_job"])
        self.assertEqual(d["header_names"], ["X-Api-Key"])
        self.assertEqual(d["url"], "http://10.1.1.5:8811/mcp")
        s = json.loads(tools.bifrost_get_mcp_client("stdio1"))
        self.assertEqual(s["stdio"]["env_names"], ["BIFROST_API_KEY", "HOME"])

    def test_auth_sent_but_not_returned(self):
        tools.bifrost_status()
        self.assertTrue(any(c[2] == "Bearer FAKE-SECRET-aaaa1111" for c in CALLS))

    def test_allowlist(self):
        for p in ("/api/providers", "/api/governance/virtual-keys", "/api/logs", "/api/../x", "/api/config?x=1"):
            with self.assertRaises(api.BifrostError): api.get(p)
        for m, p in (("DELETE", "/api/mcp/clients"), ("PUT", "/api/config"), ("POST", "/api/config"),
                     ("DELETE", "/api/governance/virtual-keys/x"), ("PUT", "/api/mcp/client/a/b"),
                     ("POST", "/api/mcp/client/x"), ("PATCH", "/api/mcp/client/x")):
            with self.assertRaises(api.BifrostError): api.request(m, p)

    def test_reconnect_needs_confirm(self):
        self.assertIn("Dry run", tools.bifrost_reconnect_mcp_client("proxmox"))
        self.assertFalse(self.writes())
        tools.bifrost_reconnect_mcp_client("proxmox", confirm=True)
        self.assertIn(("POST", "/api/mcp/client/proxmox-id/reconnect", {}), CALLS)

    def test_remote_refused(self):
        old = os.environ["BIFROST_BASE_URL"]; os.environ["BIFROST_BASE_URL"] = "http://10.1.1.200:8085"
        try:
            self.assertIn("Refusing", tools.bifrost_status())
        finally:
            os.environ["BIFROST_BASE_URL"] = old

    def test_unreachable_error_clean(self):
        old = os.environ["BIFROST_BASE_URL"]; os.environ["BIFROST_BASE_URL"] = "http://127.0.0.1:1"
        try:
            out = tools.bifrost_status(); self.assertIn("Cannot reach", out); self.no_leak(out)
        finally:
            os.environ["BIFROST_BASE_URL"] = old

    # --- create
    def test_create_http_dry_run_then_confirm(self):
        out = tools.bifrost_create_mcp_client("obsidian", "http", url="http://127.0.0.1:27123/mcp/",
                                              header_env_refs={"Authorization": "env.OBSIDIAN_MCP_AUTH"})
        self.assertIn("dry_run", out); self.assertFalse(self.writes())
        out = tools.bifrost_create_mcp_client("obsidian", "http", url="http://127.0.0.1:27123/mcp/",
                                              header_env_refs={"Authorization": "env.OBSIDIAN_MCP_AUTH"},
                                              confirm=True)
        body = self.writes()[0][2]
        self.assertEqual(body["connection_string"], "http://127.0.0.1:27123/mcp/")
        self.assertEqual(body["auth_type"], "headers")
        self.assertEqual(body["headers"], {"Authorization": "env.OBSIDIAN_MCP_AUTH"})
        self.assertEqual(body["tools_to_execute"], ["*"]); self.assertTrue(body["is_code_mode_client"])
        self.assertIn('"created": "obsidian"', out)

    def test_create_refuses_literal_secrets_and_bad_input(self):
        bad = [dict(name="x", connection_type="http", url="http://h/mcp", header_env_refs={"Authorization": "Bearer FAKEHEADERVALUE99"}),
               dict(name="x", connection_type="http", url="http://u:hunter2FAKEPASS@h/mcp"),
               dict(name="x", connection_type="http", url="http://h/mcp?token=FAKE-SECRET-aaaa1111"),
               dict(name="my-tool", connection_type="http", url="http://h/mcp"),
               dict(name="proxmox", connection_type="http", url="http://h/mcp"),
               dict(name="x", connection_type="ftp", url="http://h/mcp"),
               dict(name="x", connection_type="stdio", command="/bin/sh")]
        for kw in bad:
            out = tools.bifrost_create_mcp_client(confirm=True, **kw)
            self.assertTrue(out.startswith("Error"), (kw, out)); self.no_leak(out)
        self.assertFalse(self.writes())

    def test_create_stdio_needs_opt_in_and_names_only(self):
        os.environ["BIFROST_ALLOW_STDIO_CREATE"] = "1"
        out = tools.bifrost_create_mcp_client("s2", "stdio", command="/usr/bin/python3", env_names=["TOKEN=FAKE-SECRET-aaaa1111"], confirm=True)
        self.assertTrue(out.startswith("Error")); self.no_leak(out)
        tools.bifrost_create_mcp_client("s2", "stdio", command="/usr/bin/python3", args=["x.py"], env_names=["HOME"], confirm=True)
        self.assertEqual(self.writes()[0][2]["stdio_config"], {"command": "/usr/bin/python3", "args": ["x.py"], "envs": ["HOME"]})

    # --- update
    def test_update_partial(self):
        out = tools.bifrost_update_mcp_client("proxmox", tools_to_execute=["list_lxc"])
        self.assertIn("dry_run", out); self.assertFalse(self.writes())
        tools.bifrost_update_mcp_client("proxmox", disabled=True, confirm=True)
        self.assertEqual(self.writes()[0][:2], ("PUT", "/api/mcp/client/proxmox-id"))
        self.assertEqual(self.writes()[0][2], {"disabled": True, "name": "proxmox"})

    def test_update_cannot_disable_self(self):
        out = tools.bifrost_update_mcp_client("bifrost_admin", disabled=True, confirm=True)
        self.assertTrue(out.startswith("Error")); self.assertFalse(self.writes())

    # --- delete
    def test_delete_flow(self):
        self.assertIn("dry_run", tools.bifrost_delete_mcp_client("stdio1")); self.assertFalse(self.writes())
        out = json.loads(tools.bifrost_delete_mcp_client("stdio1", confirm="true"))
        self.assertEqual(self.writes()[0][:2], ("DELETE", "/api/mcp/client/stdio1"))
        self.assertTrue(out["verified_gone"])
        self.assertIn("No MCP client", tools.bifrost_delete_mcp_client("nope", confirm=True))

    def test_delete_self_refused(self):
        out = tools.bifrost_delete_mcp_client("bifrost_admin", confirm=True)
        self.assertTrue(out.startswith("Error")); self.assertFalse(self.writes())

    def test_kill_switch(self):
        os.environ["BIFROST_DISABLE_WRITES"] = "1"
        for out in (tools.bifrost_delete_mcp_client("proxmox", confirm=True),
                    tools.bifrost_update_mcp_client("proxmox", disabled=True, confirm=True),
                    tools.bifrost_create_mcp_client("x", "http", url="http://h/mcp", confirm=True)):
            self.assertIn("disabled by configuration", out)
        self.assertFalse(self.writes())


if __name__ == "__main__":
    unittest.main()
