#!/usr/bin/env python3
"""
ramp-cli — logs MCP server
Author: Syed Ateef

Two modes:
  • LOCAL  (RAMP_LOG_DIR set): reads log *files* on disk — no AWS, no creds, no cost.
           Each log group maps to <RAMP_LOG_DIR>/<last-segment-of-log-group>.log
           (e.g. /aws/lambda/ramp-worker -> $RAMP_LOG_DIR/ramp-worker.log).
           Use this to test ramp end-to-end against sample logs.
  • AWS    (RAMP_LOG_DIR not set): read-only CloudWatch Logs via boto3.
           Use RAMP_AWS_PROFILE (a dedicated read-only profile) + AWS_REGION.

Speed-first: every query is filtered and capped. boto3 is imported lazily so LOCAL mode
needs only the `mcp` package.
"""

import os
import time
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ramp-logs")

MAX_EVENTS = 200
DEFAULT_LIMIT = 80
ERROR_TOKENS = ("error", "exception", "traceback", "fail", "fatal")


# ---------------------------------------------------------------- local mode --
def _local_dir() -> Optional[str]:
    d = os.environ.get("RAMP_LOG_DIR")
    return d if d else None


def _local_path(log_group: str) -> str:
    name = log_group.rstrip("/").split("/")[-1]
    return os.path.join(_local_dir(), name + ".log")


def _local_read(log_group: str) -> list[dict]:
    path = _local_path(log_group)
    if not os.path.exists(path):
        return [{"message": f"(no local log file at {path})"}]
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            # optional leading "YYYY-MM-DD HH:MM:SS " timestamp
            t, msg = "", line
            if len(line) > 19 and line[4] == "-" and line[13] == ":":
                t, msg = line[:19], line[20:]
            out.append({"time": t, "message": msg})
    return out


# ------------------------------------------------------------------ aws mode --
def _aws_client():
    import boto3  # lazy: only needed in AWS mode
    region = os.environ.get("AWS_REGION", "ap-south-1")
    profile = os.environ.get("RAMP_AWS_PROFILE")
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return session.client("logs", region_name=region)


def _aws_filter(log_group: str, minutes_back: int, pattern: str, limit: int) -> list[dict]:
    client = _aws_client()
    start = int((time.time() - minutes_back * 60) * 1000)
    kwargs = {"logGroupName": log_group, "startTime": start, "limit": min(limit, MAX_EVENTS)}
    if pattern:
        kwargs["filterPattern"] = pattern
    resp = client.filter_log_events(**kwargs)
    return [{"time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e.get("timestamp", 0) / 1000)),
             "message": (e.get("message") or "").rstrip()} for e in resp.get("events", [])]


# --------------------------------------------------------------------- tools --
@mcp.tool()
def get_recent_errors(log_group: str, minutes_back: int = 30, limit: int = DEFAULT_LIMIT) -> list[dict]:
    """FAST PATH — return only ERROR/Exception/Traceback/FAIL lines from a log group.
    Make this call first when something broke: it skips the noise and shows the failures."""
    if _local_dir():
        lines = _local_read(log_group)
        hits = [e for e in lines if any(t in e["message"].lower() for t in ERROR_TOKENS)]
        return hits[:limit]
    return _aws_filter(log_group, minutes_back,
                       "?ERROR ?Error ?error ?Exception ?Traceback ?FAIL ?Fatal", limit)


@mcp.tool()
def query_logs(log_group: str, minutes_back: int = 30, filter_pattern: str = "",
               limit: int = DEFAULT_LIMIT) -> list[dict]:
    """Fetch log events from a log group, optionally containing a specific value (a request
    id, a collection name, a variable value). Use AFTER get_recent_errors to trace a value."""
    if _local_dir():
        lines = _local_read(log_group)
        if filter_pattern:
            needle = filter_pattern.strip('"').lower()
            lines = [e for e in lines if needle in e["message"].lower()]
        return lines[:limit]
    return _aws_filter(log_group, minutes_back, filter_pattern, limit)


@mcp.tool()
def search_value_across_groups(value: str, log_groups: list[str], minutes_back: int = 30,
                               limit_per_group: int = 40) -> dict:
    """Trace a single value (request id, collection name, S3 key) across MULTIPLE services'
    log groups at once — this is how you correlate a failure across the distributed system.
    Shows where the value appeared and where it diverged."""
    out = {}
    for lg in log_groups:
        try:
            out[lg] = query_logs(lg, minutes_back=minutes_back,
                                 filter_pattern=value, limit=limit_per_group)
        except Exception as exc:
            out[lg] = [{"error": f"could not query {lg}: {exc}"}]
    return out


@mcp.tool()
def list_log_groups(name_prefix: str = "") -> list[dict]:
    """List available log groups. In LOCAL mode, lists the .log files in RAMP_LOG_DIR."""
    if _local_dir():
        d = _local_dir()
        return [{"name": f[:-4]} for f in sorted(os.listdir(d)) if f.endswith(".log")]
    client = _aws_client()
    kwargs = {"limit": 50}
    if name_prefix:
        kwargs["logGroupNamePrefix"] = name_prefix
    return [{"name": g["logGroupName"]} for g in client.describe_log_groups(**kwargs).get("logGroups", [])]


if __name__ == "__main__":
    mcp.run()
