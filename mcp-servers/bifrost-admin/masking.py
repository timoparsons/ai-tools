"""Masking helpers for bifrost-admin.

Everything returned to the model passes through here. Keep names and
structure, drop values that could be secrets. Fail closed: when unsure,
redact.
"""
import json
import re

REDACTED = "<redacted>"
MAX_STRING = 400

# Keys whose values must never be returned (and neither may anything below them).
SENSITIVE_KEY = re.compile(
    r"(key|token|secret|passw|authoriz|bearer|credential|cookie|signature|pem|private|cert)", re.I
)
# Containers whose children carry secret values: keep the names, drop the values.
VALUE_CONTAINERS = {"headers", "extra_headers", "env", "envs", "environment", "env_vars"}
URL_KEYS = {"connection_string", "url", "base_url", "endpoint"}

# Strings that look like credentials, wherever they appear.
TOKEN_PATTERNS = [
    re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),  # JWT
    re.compile(r"\b(?:sk|pk|rk|xox[abp]|ghp|gho|ghs|github_pat|tok)[-_][A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-~+/=]{8,}"),
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),  # long hex (API keys, hashes)
]


def scrub_string(value):
    """Replace credential-looking substrings and cap the length."""
    if not isinstance(value, str):
        return value
    for pat in TOKEN_PATTERNS:
        value = pat.sub("<redacted-token>", value)
    if len(value) > MAX_STRING:
        value = value[:MAX_STRING] + "...[truncated]"
    return value


def safe_url(url):
    """Drop userinfo, query string and fragment from a URL."""
    if not isinstance(url, str) or not url:
        return url
    url = re.sub(r"//[^/@\s]*@", "//", url)
    url = url.split("#", 1)[0].split("?", 1)[0]
    return scrub_string(url)


def safe_args(args):
    """Command-line args with values of secret-looking flags removed."""
    out, hide_next = [], False
    for arg in args or []:
        arg = str(arg)
        if hide_next:
            out.append(REDACTED)
            hide_next = False
        elif arg.startswith("-") and "=" in arg:
            flag, _, val = arg.partition("=")
            out.append(flag + "=" + (REDACTED if SENSITIVE_KEY.search(flag) else scrub_string(val)))
        elif arg.startswith("-") and SENSITIVE_KEY.search(arg):
            out.append(arg)
            hide_next = True
        else:
            out.append(scrub_string(arg))
    return out


def env_names(envs):
    """Environment variable names only, whether given as a list or a dict."""
    if isinstance(envs, dict):
        return sorted(envs)
    return [str(e).split("=", 1)[0] for e in (envs or [])]


def mask_tree(obj, key="", hide=False):
    """Mask an arbitrary JSON structure (used for payloads without a fixed shape)."""
    hide = hide or bool(SENSITIVE_KEY.search(key))
    lower = key.lower()
    if isinstance(obj, dict):
        if lower in VALUE_CONTAINERS:
            return {name: REDACTED for name in obj}
        return {name: mask_tree(val, name, hide) for name, val in obj.items()}
    if isinstance(obj, list):
        if lower in VALUE_CONTAINERS:
            return [str(item).split("=", 1)[0] for item in obj]
        return [mask_tree(item, key, hide) for item in obj]
    if isinstance(obj, str):
        if hide and obj:
            return REDACTED
        if lower in URL_KEYS:
            return safe_url(obj)
        return scrub_string(obj)
    return obj


def dumps(obj, limit=20000):
    text = json.dumps(obj, indent=2, default=str)
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"
