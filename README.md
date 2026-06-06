# ramp-cli

**Author: Syed Ateef**

An AI debugging copilot for distributed AWS systems. When something breaks in production,
`ramp` goes to the logs, correlates them with your code and config across services, and
tells you the root cause — fast — instead of you hand-grepping CloudWatch at 2am.

It does NOT reinvent the agent. It runs on [goose](https://github.com/aaif-goose/goose)
as the engine and adds three things: a topology manifest (context), a read-only CloudWatch
Logs tool (action), and a diagnosis recipe (the loop).

---

## Architecture — two modes

ramp runs in two modes depending on urgency. The first (cheap, when nothing's broken)
builds a durable understanding of the system and stores it. The second (incident-time)
*loads* that understanding so diagnosis is instant instead of cold.

```
  MODE 1 — INDEX (not urgent, run once / periodically)
  ┌──────────────────────────────┐
  │ $ ramp index                 │   reads repos, writes a durable
  │ goose crawls each repo →     │   understanding to disk:
  │ summarize flow, data flow,   │ ───────────────▶  .ramp/index/
  │ cross-service names, key     │                     system_flow.md
  │ vars, failure surfaces       │                     services/*.md
  │ (READ-ONLY on code, no AWS)  │                     index.meta.yaml  ← the MEMORY
  └──────────────────────────────┘

  MODE 2 — DIAGNOSE (urgent, when something breaks)
  ┌───────────────────────────────────────────────────────────┐
  │ $ ramp diagnose --flow upload                              │
  │ goose (glm-5.1):                                           │
  │   0. WARM START — load .ramp/index/ (instant context)      │
  │   1. errors-first logs (tight window, capped)              │
  │   2. trace the failing value across services' log groups   │
  │   3. connect to code/config in the repos                   │
  │   4. root cause + evidence (log lines + code refs)         │
  └──────┬───────────────────┬────────────────────┬────────────┘
         ▼                   ▼                     ▼
  ┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐
  │ ramp.yaml +   │   │ CloudWatch MCP   │   │ code tools       │
  │ .ramp/index/  │   │ (boto3,READ-ONLY)│   │ (goose built-in: │
  │ TOPOLOGY +    │   │ get_recent_errors│   │  shell/grep over │
  │ MEMORY        │   │ search_value_    │   │  the repos)      │
  │               │   │ across_groups    │   │                  │
  └──────────────┘   └──────────────────┘   └──────────────────┘
```

**The `.ramp/index/` directory is the persistent memory between the two modes** — the
system's semantic memory, built at index-time, retrieved at incident-time. That warm start
is what makes diagnosis fast: it never re-discovers the system from scratch.

**Everything heavy is goose** — the agent loop, the model, the code-search tools. ramp adds
only: the topology manifest, the read-only AWS-logs tool, and two recipes (index + diagnose).

### Staleness (the honest hard part)

The index goes stale as the code changes — a memory that doesn't update is a memory that
lies. `index.meta.yaml` records each repo's git commit at index time. v1: re-run `ramp index`
to refresh (cheap). v2: auto-detect drift (`git diff` since the recorded commit) and re-index
only the changed services. This is the self-updating-memory problem, in a place where it
actually pays off.

---

## Repo layout

```
ramp-cli/
├── ramp.yaml                       # topology manifest — YOU describe your system here
├── recipes/diagnose.yaml           # the goose recipe (the diagnosis loop)
├── prompts/diagnose_system.md      # the full diagnosis method
├── mcp/cloudwatch_logs_server.py   # read-only CloudWatch Logs MCP tool (boto3)
└── mcp/requirements.txt
```

---

## ⚠ The one hard rule

`ramp` reads logs and code. **Only ever point it at infrastructure you are personally
authorized to debug.** Use a dedicated, READ-ONLY AWS profile (`RAMP_AWS_PROFILE`). Do not
use credentials that can reach systems you don't own or aren't cleared to touch. This tool
is built and demoed against a personal testbed (below).

---

## Phase 0 — the safe testbed (do this first)

Build a tiny personal version of a distributed system on your OWN AWS free-tier account,
with a planted bug, so you have a real failure to diagnose:

1. Personal AWS account (free tier). Create a read-only IAM user/profile named e.g. `ramp-ro`
   with: `logs:DescribeLogGroups`, `logs:FilterLogEvents`, `logs:GetLogEvents`. Add it to
   `~/.aws/credentials` as `[ramp-ro]`.
2. Stand up 3 trivial services that log to CloudWatch:
   - `api` → writes a job to SQS
   - `worker` (Lambda) → reads SQS, writes a result under collection `WRITE_COLLECTION`
   - `synopsis` (Lambda) → reads from `READ_COLLECTION`
3. **Plant the bug:** set `worker.WRITE_COLLECTION = foo_t` but `synopsis.READ_COLLECTION = foo_c`.
   Now `synopsis` silently finds nothing. That's your test case.
4. Trigger an upload so the logs populate.

(The example `ramp.yaml` already matches this shape — just fix the paths/log-group names.)

---

## Setup

```bash
# 1. deps for the MCP tool (use a venv to keep it isolated)
cd ~/personal-projects/ramp-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -r mcp/requirements.txt

# 2. point the tool at your read-only profile + region
export RAMP_AWS_PROFILE=ramp-ro
export AWS_REGION=ap-south-1

# 3. (optional) smoke-test the MCP server lists your log groups
python3 mcp/cloudwatch_logs_server.py   # Ctrl-C to stop; goose will launch it itself
```

The recipe declares the MCP server as a stdio extension, so goose starts it automatically.

---

## Usage

```bash
cd ~/personal-projects/ramp-cli
goose run --recipe recipes/diagnose.yaml --params flow=upload
# widen the window if the first pass finds nothing:
goose run --recipe recipes/diagnose.yaml --params flow=upload --params minutes_back=120
```

ramp will: read `ramp.yaml`, pull errors-first from the involved services, trace the failing
value across their log groups, grep the repos for where that value is set, and report the
root cause with the exact log lines and code references.

---

## Speed notes (why it's fast)

- **Errors-first:** the first log call filters to ERROR/Exception/Traceback only — skips the noise.
- **Tight window:** starts at 30 min, widens only if empty.
- **Capped results:** every query is hard-capped so the agent can't pull a huge slow payload.
- **Static topology:** the manifest is read once, not rediscovered each run.
- Optional: route the cheap "fetch logs" turns to a small model and the "reason about root
  cause" turn to glm-5.1 (see goose model config).

---

## Roadmap

- v1 (now): manifest + read-only CloudWatch tool + diagnose recipe.
- v2: auto-discover topology (read CDK/Terraform/serverless config instead of hand-writing ramp.yaml).
- v2: trace-id correlation when structured tracing is present.
- v2: metrics (CloudWatch alarms) + logs together.
- v2: a `ramp watch` mode that proactively surfaces a diagnosis the moment an alarm fires.
