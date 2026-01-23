# Helios C2: The Whole Platform (Feynman-Style)

Helios C2 is a **teaching and simulation** project.
It is not a real command system, and the “actions” it produces are **pretend**.

---

## 1) The one-sentence idea

Helios is like a **factory** that takes lots of little observations and turns them into a neat list of:

- what seems to be happening, and
- what you might want to do next.

---

## 2) The main characters (big parts)

Think of Helios as having seven big characters:

1) **Inputs** (where information comes from)
2) **The assembly line** (steps that clean up and combine the information)
3) **The rule book** (simple “if this happens, say that it matters” rules)
4) **The decider** (turns “what happened” into “what to do” suggestions)
5) **Safety and oversight** (stops bad ideas, slows runaway ideas, requires humans to approve)
6) **The record keeper** (writes down what happened so you can review it)
7) **The dashboard** (a web page that shows results and lets you interact)

There are also some “bonus helpers”:

- an **investigator’s notebook** (cases, evidence, and theories)
- a **corkboard view** (a picture of how things relate)
- a **toy robot world** (pretend vehicles that can receive commands and send back updates)

---

## 3) A run, explained like a story

Here’s what happens when you “run Helios”:

### Step A: Gather observations

Helios can get observations in a few ways:

- From a prepared script (a pretend scenario)
- By watching a growing log of observations (like “follow the newest lines as they arrive”)
- By looking at media (like video/audio) using built-in demo modules and turning their findings into observations
- From vehicle updates (pretend “status reports” like location, battery, and whether something is moving)

The important idea is:

> No matter where the observation came from, Helios reshapes it into one common format so the rest of the system can treat everything the same.

### Step B: Group related observations

If several observations seem related (for example, they look like the same thing seen over time), Helios groups them together into a simple “track.”

This does not try to be perfect.
It’s just enough to say: “these observations probably belong together.”

### Step C: Apply the rule book

Now Helios asks:

- “Do any of our simple rules match this observation?”

When a rule matches, Helios creates a “something happened” item.

Rules are meant to be easy to understand, like:

- “If this number is below a limit, raise a warning.”
- “If a special flag is true, raise a warning.”
- “If a message contains a certain keyword, raise a warning.”

### Step D: Safety check #1 (what’s allowed to be said)

Before Helios goes further, it applies policy like a safety inspector.

It can:

- ignore certain areas entirely
- ignore certain kinds of events
- reduce how “serious” something is allowed to be in an area

### Step E: Decide what to do next

For each “something happened” item, Helios creates one or more “what to do” suggestions.

Some suggestions might be:

- “investigate”
- “notify someone”
- “lock something”
- “unlock something”

Important: in this repo, these are still just suggestions.

### Step F: Safety check #2 (what’s allowed to be done)

Helios checks the suggested actions against policy.
If an action is forbidden, it gets removed.

### Step G: Human approval (when required)

Some suggestions are allowed to go forward automatically.
Others get marked as “waiting for approval.”

The idea is simple:

> A person can be “in the loop” so the system can’t run away and do too much on its own.

### Step H: Guardrails (stop runaway output)

Even if suggestions are valid, Helios can limit how many it produces.
For example:

- only a certain number total
- only a certain number for one area
- only a certain number caused by one incident
- only a certain number affecting one specific asset

This is like putting speed limits on the assembly line.

### Step I: Risk throttling (hold back during overload)

If there’s too much going on, Helios can temporarily hold back some high-severity suggestions so the system doesn’t get overwhelmed.
It can also wait longer and longer if the noise continues.

### Step J: Make a simple plan

Helios groups the approved suggestions into a very simple plan, mostly so it’s easier to review.

### Step K: Write everything down

Finally, Helios writes its results into an **output folder**.

Think of that output folder like a binder with:

- what Helios saw
- what it thinks happened
- what it recommends
- what needs approval
- what it decided to hold back

---

## 4) The dashboard (how humans see it)

There is a simple web dashboard that shows:

- what the system observed
- what it thinks happened
- what it recommends
- what is waiting for approval
- a timeline of what the system did

The dashboard mostly works by reading the files Helios wrote into the output folder.

---

## 5) The record keeper (the “what happened” diary)

Helios keeps a running diary of steps it took.

Two important properties:

1) It’s **append-only** (new entries get added at the end).
2) It’s **tamper-evident** (if someone changes an older entry, you can detect it).

That makes it useful for review and learning:

- “What did the system do first?”
- “Why did it recommend that?”
- “Did policy block anything?”
- “Did guardrails drop anything?”

---

## 6) Investigator helpers (optional, but useful)

These helpers are for organizing and exploring what Helios produced.

### Notebook: cases, evidence, and theories

You can create:

- a case (like a folder)
- evidence (things that support the case)
- theories (explanations you’re considering)

### Entity summaries (best-effort)

If you used media inputs, Helios can build simple summaries of “things seen over time.”

These are intentionally **non-identifying** and **coarse**.
They’re meant for a demo and for thinking about patterns, not for identifying a person.

### Corkboard view (relationships)

Helios can build a “corkboard” picture that links together things like:

- incidents
- recommendations
- assets
- notebook items
- entity summaries

This is best-effort: if some pieces are missing, Helios should still run.

---

## 7) The toy robot world (optional)

Helios can also simulate a tiny “robot side”:

1) Helios creates “commands” based on approved suggestions (and optional commander plans)
2) Commands might be marked “sent” or “delayed” depending on pretend connectivity
3) A pretend vehicle simulator reads commands and changes its pretend state
4) The simulator writes back status updates (like location/battery/status)
5) Helios can read those updates in later runs

This creates a simple feedback loop:

> suggestion → command → movement → status update → better picture next time

---

## 8) Where to look next

- If you want a UI-focused walkthrough of the Sensors and Investigations pages: see the Sensors ↔ Investigations Feynman doc.
- If you want the exact list of saved outputs and what fields they contain: see the data model doc.
- If you want a more formal “which step runs where” description: see the architecture doc.
