# ramp — invisible context router (the session-routing behavior)
# Author: Syed Ateef

This is the mechanism behind "invisible sub-sessions." It governs how ramp keeps its working
context small and relevant across a long, wandering session — without the user ever seeing it.

## The behavior

On each new user query in an ongoing session, silently decide:

1. BRANCH OR CONTINUE
   - Compare the new query to the current working context (topic, files, services, entities).
   - CONTINUE (keep context) if the new query clearly builds on what's already loaded
     (shares the same service / bug / files / entities).
   - BRANCH (start a clean sub-session) if it's a different topic — different service, unrelated
     bug, new area. The sub-session inherits NOTHING by default. It's fast and focused.
   - When unsure, prefer CONTINUE for tiny follow-ups, BRANCH for anything that smells like a
     new investigation. Branching wrongly is cheap to recover; bloating forever is not.

2. LAZY PULL (only inside a branched sub-session)
   - Work on the new query with the clean context.
   - If, mid-task, you find you need a specific earlier fact (a value, a prior finding, a
     decision), RETRIEVE only that slice from the parent session / the `.ramp/index/` store —
     not the whole history. Pull the minimum that answers the need.
   - Never pre-load the parent context "just in case." Pull on demand, pay for what you use.

3. INVISIBLE
   - Do NOT announce any of this to the user. No "I'm starting a sub-session" or "I'm pulling
     parent context." The user types into one chat and it feels like one continuous, sharp
     conversation. The routing is internal plumbing.

## Why

Long sessions bloat: unrelated history makes every turn slower, costlier, and noisier (the
agent conflates topics). Branching keeps the working set small; lazy-pull keeps it from going
amnesiac. The result is a session that stays fast and accurate no matter how long it runs.

## Implementation note (goose specifics)

- The "clean sub-session" is goose's subagent capability (the `summon`/`delegate` family).
  NOTE: ramp currently disables `summon` for speed on simple diagnoses — to enable invisible
  routing, re-enable the subagent extension and gate it behind THIS router logic so it only
  branches when the branch-decision says so (not on every task).
- The "store to pull from" is the parent session transcript + `.ramp/index/`. The index is
  already the retrievable memory; the parent transcript is the episodic store.
- Start simple: a heuristic branch decision (same service/files/entities → continue, else
  branch) before anything learned. Log every branch/pull decision so you can tune it later.

## The honest hard part

The quality of (1) the branch decision and (2) what-to-pull IS the product. Dumb versions
either over-branch (lose useful context) or pull the wrong slice. This is the relevance/salience
problem — start heuristic, measure on real sessions, improve. Don't pretend it's solved.
