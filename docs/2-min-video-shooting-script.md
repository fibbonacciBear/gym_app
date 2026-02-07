# 2-Minute Video: Shooting Script (Tight Cut)

> Forked from [2-min-video-ai-human-process-explainer.md](2-min-video-ai-human-process-explainer.md) -- see that doc for full context, themes, and rationale.

---

## Act 1: Context & Credibility (~15s)

**VISUAL:** App running, quick flash of PRD / sprint plan / architecture doc

> "I'm building Titan Tracker -- a voice-first workout tracker. It's my second startup, my first is profitable. Everything here -- PRD, architecture, CloudFormation templates, code, unit tests -- is AI-generated with meticulous human-in-the-loop iteration."

> **"Writing is not my bottleneck. Reviewing, testing, and evolving the product to match my vision -- that's where I spend my time."**

---

## Act 2: Planning (~15s)

**VISUAL:** Scroll through a plan file in Cursor

> "Before any code is written, I create a detailed plan in a simple markdown file. Multiple iterations with the biggest models -- Opus, GPT-5.2. Big models for planning. Then I hand it to Claude Code with Sonnet 4.5 to implement -- cheaper, and amazing at long-running tasks."

**VISUAL:** Claude Code running across multiple files

---

## Act 3: The Catch (~35s)

**VISUAL:** Scanning code in Cursor. Slow, deliberate. Let them see you reading.

> "Then -- the real work. Code review."

**VISUAL:** Highlight the offending code

> "I spot a database query per exercise. I do 50 exercises a session. A thousand users -- that's 50,000 DB calls. Classic N+1 problem. It works, but it won't scale."

> "This is why human review matters. The AI wrote correct code, but it doesn't understand my scale constraints."

**VISUAL:** Prompt GPT-5.3, show the fix arriving

> "For a performance fix, I grab the biggest model -- GPT-5.3, released yesterday. Batch query, single round trip. Fixed."

---

## Act 4: Quality Gate (~15s)

**VISUAL:** Run Cursor bug finder, show it flagging something

> "Last step -- Cursor's bug finder. Missing try-catch, bad regex, edge cases. I never check in without this. AI wrote it, I reviewed it, tooling validates it. Three layers of quality."

---

## Act 5: Close (~10s)

> "AI is my force multiplier -- but I'm the engineer. Quality is non-negotiable."

---

## Timing

| Section              | Time | Narration                                        |
| -------------------- | ---- | ------------------------------------------------ |
| Context & Credibility | ~15s | App + docs flash, "reviewing is my job"          |
| Planning             | ~15s | Plan file, model strategy, Claude Code hand-off  |
| The Catch            | ~35s | N+1 query, human review, GPT-5.3 fix            |
| Quality Gate         | ~15s | Bug finder, "three layers of quality"            |
| Close                | ~10s | "Quality is non-negotiable"                      |
| **Total**            | **~1:30** | **~30s of visual breathing room = ~2:00**   |
