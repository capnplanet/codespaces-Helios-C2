# Entity Profiler (Feynman-Style)

This document explains the Entity Profiler like you’re a **smart 12-year-old**.

The Entity Profiler is a helper that answers a simple question:

> “When we look at a piece of media, can we create a *repeatable* summary of the people we saw, without trying to identify them by name?”

It is designed for **pattern finding** and **investigation notes**, not for “who is this person?”

---

## 1) The simplest mental model

Imagine you’re watching a short video.

- You notice: “A person appears here… then later… then again.”
- You want a neat way to write down: “This seems like the same person across multiple moments.”

The Entity Profiler is that neat way to write it down.

It creates:

- a **page per person-like track** (an “entity”), and
- a **summary page** that tells you basic patterns (when they showed up, how often, and over what time span).

---

## 2) What it needs as input

The Entity Profiler works best when Helios runs the built-in media analysis and produces things like:

- “Here are the people-shaped detections in the frames.”
- “Here is a simple ‘walking style’ signature that helps keep the same person linked across time.”

If Helios doesn’t have a good “walking style” signal, the Entity Profiler still tries.
It just has to be more cautious and less precise.

---

## 3) What it produces

It produces two kinds of output:

### A) Detailed pages (observations)

For each tracked entity, it stores a list of “observations,” like:

- a timestamp
- which camera/source it came from (in the demo it’s usually just “media”)
- roughly where the person was in the frame
- a few **non-identifying** shape/motion clues

### B) A summary page (pattern hints)

For each entity, it also produces a simple summary, like:

- how many times it was observed
- which camera/source saw it most
- what time-of-day it appeared most often
- how long the observations span (seconds from first to last)

This is meant to help an investigator say things like:

- “This person shows up repeatedly over 3 minutes.”
- “Most sightings are around the same time.”

---

## 4) What “non-identifying” means here

The Entity Profiler is intentionally **not** doing:

- face recognition
- name matching
- personal identity lookups

It is closer to:

- “Does this look like the same moving person across frames?”

Even that can be wrong sometimes.
So treat it like a helpful sticky note, not a final answer.

---

## 5) How it fits into the whole platform

The Entity Profiler is not the main decision-maker.
It is a side helper that makes investigations easier.

A typical flow is:

1) Helios processes a media file
2) Helios produces observations from media analysis
3) Entity Profiler turns those observations into entity pages + summaries
4) The Investigations tools can display those summaries and link them to cases/evidence

---

## 6) When it works well vs. when it struggles

Works well when:

- the media is clear enough to track a person across multiple frames
- the “walking style” signal exists and is consistent

Struggles when:

- the person is only visible briefly
- the view is blocked or blurry
- many people overlap
- there’s no stable motion signal, so it can’t confidently link sightings

---

## 7) If you’re looking for the saved result

After a run, the Entity Profiler writes a file into the run’s output folder named:

- `entity_profiles.json`

That file is what the dashboard reads to show “entity profiles.”
