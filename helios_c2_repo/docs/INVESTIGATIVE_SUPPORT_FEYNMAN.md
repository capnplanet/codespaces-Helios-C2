# Investigative Support (Feynman-Style)

This document explains the Investigative Support module like you’re a **smart 12-year-old**.

Investigative Support is the part of Helios that helps you **organize** what you’ve seen.

It doesn’t try to “control everything.”
It tries to help you answer:

> “What do we know, what do we think, and what evidence supports it?”

---

## 1) The simplest mental model

Imagine you’re solving a mystery.

You want three things:

1) A **notebook** where you write down cases and evidence.
2) A **corkboard** where you pin things and draw strings between them.
3) A **shared language** for different kinds of evidence (video clip, report excerpt, digital clue, etc.).

That’s what Investigative Support is about.

---

## 2) The notebook: cases, evidence, and theories

### A) Case = the folder

A case is a folder with:

- a title
- a description
- a status (open/closed-ish)
- a domain/area (what kind of situation it is)

### B) Evidence = the receipts

Evidence is any “receipt” that supports a case.
Examples of evidence types this repo talks about:

- a CCTV clip
- a bodycam segment
- a report excerpt
- a digital fingerprint (like a hash)
- a behavior description (“they always do X at night”)

The important idea:

> Evidence is something you can point to and say “this is why I believe that.”

### C) Hypothesis = your current theory

A hypothesis is your best current explanation.

It can link to:

- one or more cases
- the evidence that supports it
- the evidence that contradicts it

It can also have a confidence level (how sure you feel right now).

---

## 3) The corkboard: a relationship picture

Sometimes lists are hard to reason about.

A relationship picture helps you see:

- which incidents connect to which recommendations
- which assets were involved
- which evidence supports which theory
- which entity summaries might match which case

In the Helios demo, this “corkboard” is built from whatever outputs exist.
If some pieces are missing, it still tries to build a useful picture.

---

## 4) How this connects to the rest of Helios

Investigative Support is like the **after-action desk**.

The main pipeline focuses on:

- turning observations into “what happened” items
- turning those into “what to do” suggestions
- applying safety checks and human approval

Investigative Support focuses on:

- keeping your notes organized
- attaching evidence
- building a relationship picture so humans can think clearly

So the relationship is:

- The pipeline produces outputs.
- Investigative Support helps humans make sense of them.

---

## 5) Two places you’ll see Investigative Support in this repo

### A) The working demo helpers

In the running Helios demo, the “investigations” helpers are implemented as:

- a notebook file (cases/evidence/theories)
- a relationship picture built from the run outputs

These are what the dashboard uses.

### B) The “Investigative Support” folder

There is also a folder named “Investigative Support” that defines a richer set of evidence types and investigation objects.

Think of it like:

> “Here’s a bigger menu of investigation record types a full system might want.”

It’s useful as a reference for how you might structure investigation data, even if the demo UI uses a simpler notebook file today.

---

## 6) If you’re looking for the saved results

After a run, you’ll typically see investigation-related files in the output folder such as:

- `casebook.json` (the notebook)
- `graph.json` (the corkboard picture)

And if you used media analysis:

- `entity_profiles.json` (entity summaries that investigations can reference)
