# 2-Minute Video: AI-Human Process Explainer

## Overview

A two-minute video demonstrating my full-stack vibe coding workflow -- how I leverage AI strategically while maintaining engineering rigor to build production-quality products.

---

## Act 1: Context & Credibility (~20 seconds)

> "I'm building my second startup, Titan Tracker -- a voice-first workout tracker. My first startup is profitable, and I'm applying the same discipline here. I'm an avid gym-goer, so I'm building something I use every single day."

- **Visual:** Quick shot of the app running (3-5 sec screen recording)
- **Visual:** Flash the PRD, sprint plan, architecture doc

> "Everything you see here -- the PRD, architecture docs, sprint plans, CloudFormation templates, code, unit tests -- is AI-generated with meticulous human-in-the-loop iteration."

> **"Writing docs and code is not my bottleneck. Reviewing them, testing them, and evolving the project to match my vision -- that's where I spend my time."**

---

## Act 2: The Planning Workflow (~20 seconds)

> "Before any code gets written, I create a highly detailed plan. I use Cursor to draft it in a simple markdown file. The plan itself goes through multiple iterations with the biggest models available -- Opus, GPT-5.2 -- because this is where precision matters most."

- **Visual:** Show a plan file in Cursor, scroll through it briefly
- **Key point:** Big models for planning, cheaper models for execution

> "Then I hand the plan to Claude Code with Sonnet 4.5 to implement. It's cheaper, and Claude Code is exceptional at long-running, multi-file tasks."

**What this demonstrates:** Strategic model selection -- the right model for the right job. That's engineering judgment, not just prompting.

---

## Act 3: Implementation Hand-Off (~10 seconds)

- **Visual:** Claude Code running, implementing the plan across multiple files
- Brief mention of the efficiency of this approach

---

## Act 4: The Review & The Catch (~35 seconds)

> "Then comes the real work -- meticulous code review."

- **Visual:** Scanning through code in Cursor, scrolling, reading
- Slow down here. Let them *see* you reading code.

> "Here, as I'm scanning through, I spot something -- there's a database query per exercise. I do 50 exercises in a session. If I have 1,000 users, that's 50,000 database calls. That's an N+1 query problem and it won't scale."

- **Visual:** Highlight the offending code

> "This is exactly why human review matters. The AI wrote correct code -- it works -- but it doesn't understand my scale constraints. Let me refactor this. For a performance-critical fix like this, I reach for the biggest model available -- let's try GPT-5.3, released just yesterday."

- **Visual:** Show the prompt, the fix coming back, the refactored code

> "And there it is -- batch query, single round trip. Fixed."

**What this demonstrates:** You can *read* code. You understand performance. You know when AI gets it wrong. You pick the right tool to fix it.

---

## Act 5: The Final Quality Gate (~15 seconds)

> "And before anything gets checked in -- one last step. I run Cursor's built-in bug finder. It's incredible at catching the low-level stuff: a missing try-catch block, an incorrect regex pattern, edge cases you'd miss on a manual scan."

- **Visual:** Run the bug finder, show it flagging something real
- Quick fix if it catches something

> "I never check in code without this step. AI wrote it, I reviewed it, and now the tooling validates it. Three layers of quality."

---

## Act 6: Close (~15 seconds)

> "This is how I build: plan deeply with the best models, implement efficiently, review everything with engineering judgment, and validate with tooling before anything ships. AI is my force multiplier -- but quality is non-negotiable."

---

## Timing Summary

| Section                      | Time  | What You Show                                              |
| ---------------------------- | ----- | ---------------------------------------------------------- |
| **Context & Credibility**    | ~20s  | App demo, PRD, docs -- "reviewing is my job, not writing"  |
| **Planning Workflow**        | ~20s  | Plan in Cursor, big models for planning, cheaper for exec  |
| **Implementation Hand-Off**  | ~10s  | Claude Code with Sonnet 4.5                                |
| **The Review & The Catch**   | ~35s  | Spot N+1 query, fix with GPT-5.3                          |
| **Bug Finder Quality Gate**  | ~15s  | Cursor bug finder, "never check in without it"             |
| **Close**                    | ~15s  | "Three layers: AI generates, I review, tooling validates"  |
| **Total**                    | ~2:10 |                                                            |

---

## Key Themes

| They Want                  | You Show                                            |
| -------------------------- | --------------------------------------------------- |
| Understands technology     | Catches N+1 query, understands DB scaling           |
| Builds solid products      | Real app, real PRD, real architecture                |
| Instructs AI effectively   | Strategic model selection, detailed plans            |
| High quality output        | Human review loop, performance awareness             |
| Full stack                 | Voice app + DB + AWS infra + frontend                |

---

## Narrative Arc

1. **I'm credible** -- real startup, real product, real user
2. **I plan deliberately** -- right model for the right job
3. **I catch what AI misses** -- performance, architecture, scale
4. **I use every tool available** -- manual review + automated bug finding
5. **Nothing ships without passing all three gates**

---

## Three Layers of Quality

1. **AI generates** -- leveraging the best models for planning and implementation
2. **I review** -- engineering judgment catches what AI can't (scale, performance, vision)
3. **Tooling validates** -- Cursor bug finder catches low-level issues before check-in
