# ramp-cli — TODO / parked decisions
Author: V Syed Ateef Quadri

Things deliberately deferred so we could ship. Revisit after launch + feedback.

## Decisions to revisit
- [ ] **goose dependency — Path A vs Path B.** Right now ramp runs ON goose and credits it
      honestly (kept in, on purpose). Later decide:
      - Path A: keep goose as the engine, ramp is the brand (honest "runs on goose" line).
      - Path B: build ramp's OWN agent loop so it's standalone / zero-goose (real build, days).
- [ ] **Before any public push:** confirm the Contravault employment contract allows personal
      OSS (moonlighting + IP-assignment clause, or company OSS policy). Code is clean & in a
      different category, but clear the contract first. (Gate is yours.)

## Features to build (post-launch)
- [ ] **Repo registry + picker UX** — make it work for ANY repos at ANY paths, not a fixed set.
      `ramp repo add/list` → repos.yaml. Interactive multi-select picker (like the model picker):
      tick repos in scope per prompt; un-ticked repos get lazy-pulled if the trail leads there.
      (Design already in prompts/session_router.md.)
- [ ] **Invisible context / sub-sessions** — branch unrelated queries into clean sub-sessions,
      lazy-pull parent context on demand, hidden from the user. (spec: prompts/session_router.md)
- [ ] **AWS mode end-to-end** — deploy ramp-testbed via SAM, run with RAMP_AWS_PROFILE (read-only),
      verify ramp against real CloudWatch (not just local sample logs).
- [ ] **Fill the blog demo** — blog/invisible-context.md has a [demo] placeholder; drop in a real
      transcript once AWS mode (or a bigger local run) is captured.

## v2 / later
- [ ] Auto-discover topology from IaC (CDK / Terraform / serverless config) instead of hand-writing ramp.yaml.
- [ ] Trace-id correlation when structured tracing exists.
- [ ] Metrics (CloudWatch alarms) + logs together.
- [ ] `ramp watch` — proactively diagnose the moment an alarm fires.
- [ ] Index staleness auto-detect (git diff since index.meta.yaml commit → re-index only changed services).
