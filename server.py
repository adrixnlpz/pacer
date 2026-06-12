#!/usr/bin/env python3
"""
Claude Usage Dashboard Server
Reads real data from:
  - ~/.claude/projects/**/*.jsonl  → session/model/tool stats
  - ~/Library/Application Support/Tokemon/usage_history.json → plan usage
"""

import json
import os
import glob
import re
import subprocess
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import anthropic

# ── Auth: read API key from .env file or environment ─────────────────────────
def get_api_key():
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("ANTHROPIC_API_KEY", "")

# ── Pricing (USD per 1M tokens) ──────────────────────────────────────────────
PRICING = {
    "claude-opus-4-6":    {"input": 15.0,  "output": 75.0,  "cache_write": 18.75, "cache_read": 1.50},
    "claude-opus-4-5":    {"input": 15.0,  "output": 75.0,  "cache_write": 18.75, "cache_read": 1.50},
    "claude-sonnet-4-6":  {"input":  3.0,  "output": 15.0,  "cache_write":  3.75, "cache_read": 0.30},
    "claude-sonnet-4-5":  {"input":  3.0,  "output": 15.0,  "cache_write":  3.75, "cache_read": 0.30},
    "claude-haiku-4-5":   {"input":  0.80, "output":  4.0,  "cache_write":  1.00, "cache_read": 0.08},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0, "cache_write": 1.00, "cache_read": 0.08},
}
DEFAULT_PRICE = {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.30}

def token_cost(model, input_tok, output_tok, cache_write_tok, cache_read_tok):
    p = PRICING.get(model, DEFAULT_PRICE)
    return (
        input_tok      * p["input"]       / 1_000_000 +
        output_tok     * p["output"]      / 1_000_000 +
        cache_write_tok* p["cache_write"] / 1_000_000 +
        cache_read_tok * p["cache_read"]  / 1_000_000
    )

# ── Time range helper ─────────────────────────────────────────────────────────
RANGES = {
    "all":   None,
    "30d":   timedelta(days=30),
    "7d":    timedelta(days=7),
    "1d":    timedelta(days=1),
    "10hrs": timedelta(hours=10),
    "1hr":   timedelta(hours=1),
}

def cutoff_for(range_key):
    delta = RANGES.get(range_key.lower())
    if delta is None:
        return None
    return datetime.now(timezone.utc) - delta

# ── Parse JSONL files ─────────────────────────────────────────────────────────
JSONL_GLOB = os.path.expanduser("~/.claude/projects/**/*.jsonl")

def parse_sessions(range_key="7d"):
    cutoff = cutoff_for(range_key)
    sessions = {}          # file_path → session stats
    daily    = {}          # "MM-DD" → {cost, calls}
    by_model = {}          # model_name → {cost, calls, input, output, cached, written}
    tools    = {}          # tool_name → count

    for fpath in glob.glob(JSONL_GLOB, recursive=True):
        session_id = os.path.basename(fpath).replace(".jsonl", "")
        session_data = {"calls": 0, "cost": 0.0, "has_data": False}

        with open(fpath, encoding="utf-8", errors="ignore") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if obj.get("type") != "assistant":
                    continue

                msg = obj.get("message", {})
                usage = msg.get("usage")
                if not usage:
                    continue

                # Parse timestamp
                ts_str = obj.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    continue

                if cutoff and ts < cutoff:
                    continue

                model = msg.get("model", "unknown")
                in_tok  = usage.get("input_tokens", 0)
                out_tok = usage.get("output_tokens", 0)
                cw_tok  = usage.get("cache_creation_input_tokens", 0)
                cr_tok  = usage.get("cache_read_input_tokens", 0)
                cost    = token_cost(model, in_tok, out_tok, cw_tok, cr_tok)

                # Session aggregation
                session_data["calls"] += 1
                session_data["cost"]  += cost
                session_data["has_data"] = True

                # Daily aggregation
                day_key = ts.strftime("%m-%d")
                if day_key not in daily:
                    daily[day_key] = {"cost": 0.0, "calls": 0}
                daily[day_key]["cost"]  += cost
                daily[day_key]["calls"] += 1

                # Model aggregation
                if model not in by_model:
                    by_model[model] = {"cost": 0.0, "calls": 0,
                                       "input": 0, "output": 0,
                                       "cached": 0, "written": 0}
                by_model[model]["cost"]    += cost
                by_model[model]["calls"]   += 1
                by_model[model]["input"]   += in_tok
                by_model[model]["output"]  += out_tok
                by_model[model]["cached"]  += cr_tok
                by_model[model]["written"] += cw_tok

                # Tool usage (from content array)
                content = msg.get("content", [])
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        name = item.get("name", "unknown")
                        # Shorten MCP/internal tool names
                        if "__" in name:
                            name = name.split("__")[-1]
                        tools[name] = tools.get(name, 0) + 1

        if session_data["has_data"]:
            sessions[session_id] = session_data

    # ── Summary ──────────────────────────────────────────────────────────────
    total_cost  = sum(s["cost"]  for s in sessions.values())
    total_calls = sum(s["calls"] for s in sessions.values())
    total_input   = sum(m["input"]   for m in by_model.values())
    total_output  = sum(m["output"]  for m in by_model.values())
    total_cached  = sum(m["cached"]  for m in by_model.values())
    total_written = sum(m["written"] for m in by_model.values())
    cache_hit_rate = round(total_cached / (total_cached + total_input) * 100) if (total_cached + total_input) > 0 else 0

    # Sort daily by date, keep last 14 entries for readability
    sorted_daily = sorted(daily.items())[-14:]

    # Model list sorted by cost desc
    max_cost = max((m["cost"] for m in by_model.values()), default=1)
    model_list = sorted(
        [{"model": k,
          "display": k.replace("claude-", "").replace("-4-6", " 4.6").replace("-4-5", " 4.5").title(),
          "cost": round(v["cost"], 4),
          "calls": v["calls"],
          "pct": round(v["cost"] / max_cost * 100) if max_cost else 0}
         for k, v in by_model.items()],
        key=lambda x: x["cost"], reverse=True
    )

    # Tool list sorted by calls desc
    max_tool = max(tools.values(), default=1)
    tool_list = sorted(
        [{"name": k, "calls": v, "pct": round(v / max_tool * 100)}
         for k, v in tools.items()],
        key=lambda x: x["calls"], reverse=True
    )[:12]

    return {
        "range": range_key,
        "summary": {
            "total_cost": round(total_cost, 4),
            "total_calls": total_calls,
            "sessions": len(sessions),
            "cache_hit_rate": cache_hit_rate,
            "tokens_in": total_input,
            "tokens_out": total_output,
            "tokens_cached": total_cached,
            "tokens_written": total_written,
        },
        "daily": [{"date": d, "cost": round(c["cost"], 4), "calls": c["calls"]}
                  for d, c in sorted_daily],
        "by_model": model_list,
        "tools": tool_list,
    }

# ── Plan usage from Tokemon ───────────────────────────────────────────────────
TOKEMON_HISTORY = os.path.expanduser(
    "~/Library/Application Support/Tokemon/usage_history.json"
)

def get_plan_usage(range_key="7d"):
    try:
        with open(TOKEMON_HISTORY) as f:
            history = json.load(f)
    except Exception:
        return {"primary_pct": 0, "seven_day_pct": 0, "history": []}

    cutoff = cutoff_for(range_key)
    filtered = []
    for entry in history:
        try:
            ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
        except Exception:
            continue
        if cutoff and ts < cutoff:
            continue
        filtered.append({
            "timestamp": entry["timestamp"],
            "primary_pct": entry.get("primaryPercentage", 0),
            "seven_day_pct": entry.get("sevenDayPercentage", 0),
        })

    # Latest values
    latest = history[-1] if history else {}
    return {
        "primary_pct": round(latest.get("primaryPercentage", 0)),
        "seven_day_pct": round(latest.get("sevenDayPercentage", 0)),
        "source": latest.get("source", "unknown"),
        "updated_at": latest.get("timestamp"),
        "history": filtered[-200:],  # cap for response size
    }

# ── AI Recommendation via Claude ──────────────────────────────────────────────
def get_recommendation(stats):
    key = get_api_key()
    if not key:
        raise ValueError("No API key found. Add ANTHROPIC_API_KEY=sk-ant-... to dashboard/.env")
    client = anthropic.Anthropic(api_key=key)

    prompt = f"""You are analyzing Claude Code usage stats to give actionable recommendations.

Stats (last {stats.get('range', '?')}):
- Total cost: ${stats['summary']['total_cost']}
- Total API calls: {stats['summary']['total_calls']}
- Sessions: {stats['summary']['sessions']}
- Cache hit rate: {stats['summary']['cache_hit_rate']}%
- Tokens in: {stats['summary']['tokens_in']:,}
- Tokens out: {stats['summary']['tokens_out']:,}

Model usage breakdown:
{json.dumps(stats['by_model'], indent=2)}

Top tools used:
{json.dumps(stats['tools'][:8], indent=2)}

Respond with ONLY valid JSON in this exact structure (no markdown, no explanation):
{{
  "model_suggestions": [
    {{
      "model": "Sonnet 4.6",
      "badge_class": "sonnet",
      "reason": "one sentence why"
    }}
  ],
  "tool_delegations": [
    {{
      "icon": "emoji",
      "tool": "Tool name",
      "reason": "one sentence advice"
    }}
  ],
  "summary": "one sentence overall assessment"
}}

Rules:
- model_suggestions: 2-3 items max, sorted best-fit first
- tool_delegations: 3-4 items max, based on actual tool usage patterns
- badge_class must be one of: opus, sonnet, haiku
- Keep each reason under 20 words
- Be specific and actionable, not generic"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()
    return json.loads(raw)

# ── HTTP Handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default access log

    def send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, mime):
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_file(os.path.join(os.path.dirname(__file__), "index.html"), "text/html")

        elif path == "/api/data":
            r = qs.get("range", ["7d"])[0]
            stats = parse_sessions(r)
            plan  = get_plan_usage(r)
            stats["plan"] = plan
            self.send_json(stats)

        elif path == "/api/recommend":
            r = qs.get("range", ["7d"])[0]
            stats = parse_sessions(r)
            try:
                rec = get_recommendation(stats)
            except Exception as e:
                rec = {"error": str(e)}
            self.send_json(rec)

        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    port = 8765
    host = "0.0.0.0"
    print(f"  PACER backend")
    print(f"  http://localhost:{port}")
    print(f"  Press Ctrl+C to stop\n")
    HTTPServer((host, port), Handler).serve_forever()
