---
name: doc-coauthoring
description: Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content. This workflow helps users efficiently transfer context, refine content through iteration, and verify the doc works for readers. Trigger when user mentions writing docs, creating proposals, drafting specs, or similar documentation tasks.
---

# Doc Co-Authoring Workflow

## All Contents

This skill provides a structured workflow for guiding users through collaborative document creation. Act as an active guide, walking users through three stages: Context Gathering, Refinement & Structure, and Reader Testing.

### When to Offer This Workflow

**Trigger conditions:**
- User mentions writing documentation: "write a doc", "draft a proposal", "create a spec"
- User mentions specific doc types: "PRD", "design doc", "decision doc", "RFC"
- User seems to be starting a substantial writing task

**Initial offer:**
Offer the user a structured workflow for co-authoring the document. Explain the three stages:

1. **Context Gathering**: User provides all relevant context while Claude asks clarifying questions
2. **Refinement & Structure**: Iteratively build each section through brainstorming and editing
3. **Reader Testing**: Test the doc with a fresh Claude (no context) to catch blind spots

Ask if they want to try this workflow or prefer to work freeform. If user declines, work freeform. If user accepts, proceed to Stage 1.

### Stage 1: Context Gathering

**Goal:** Close the gap between what the user knows and what Claude knows.

#### Initial Questions

Ask the user for meta-context:
1. What type of document is this?
2. Who's the primary audience?
3. What's the desired impact when someone reads this?
4. Is there a template or specific format to follow?
5. Any other constraints or context?

**If user provides a template:** Ask if they have a template document to share, fetch it if possible.

**If user mentions editing an existing shared document:** Read the current state, check for images without alt-text.

#### Info Dumping

Encourage the user to dump all context:
- Background on the project/problem
- Related team discussions or shared documents
- Why alternative solutions aren't being used
- Organizational context
- Timeline pressures or constraints
- Technical architecture or dependencies
- Stakeholder concerns

Advise them not to worry about organizing it. Offer multiple ways to provide context (info dump, point to channels, link to docs).

**During context gathering:** Track what's being learned and what's still unclear. If integrations are available, use them to pull context directly.

**Asking clarifying questions:** When user signals they've done their initial dump, generate 5-10 numbered questions based on gaps. Allow shorthand answers.

**Exit condition:** Sufficient context when questions show understanding of edge cases and trade-offs without needing basics explained.

**Transition:** Ask if there's more context to provide, or if it's time to move on to drafting.

### Stage 2: Refinement and Structure

**Goal:** Build the document section by section through brainstorming, curation, and iterative refinement.

Explain the process: For each section, clarifying questions → brainstorm 5-20 options → user curates → draft → refine through surgical edits.

Start with whichever section has the most unknowns.

**If document structure is unclear:** Suggest 3-5 sections appropriate for the doc type.

**Once structure is agreed:** Create initial document structure with placeholder text for all sections (use artifact or file).

#### For Each Section

**Step 1: Clarifying Questions** - Ask 5-10 questions about what should be included.

**Step 2: Brainstorming** - Generate 5-20 numbered options based on section complexity.

**Step 3: Curation** - Ask which points to keep/remove/combine. Accept freeform feedback.

**Step 4: Gap Check** - Ask if anything important is missing.

**Step 5: Drafting** - Use `str_replace` to replace placeholder text with drafted content.

**Step 6: Iterative Refinement** - Make edits via `str_replace`, never reprint whole doc. Continue until user is satisfied.

**Key instruction for user (first section):** Ask them to indicate what to change rather than editing directly, to help learn their style.

**Quality Checking:** After 3 consecutive iterations with no substantial changes, ask if anything can be removed.

**Near Completion (80%+ done):** Re-read entire document, check for flow, consistency, redundancy, contradictions, and "slop."

### Stage 3: Reader Testing

**Goal:** Test the document with a fresh Claude (no context bleed) to verify it works for readers.

#### Testing with Sub-Agents (if available)

**Step 1: Predict Reader Questions** - Generate 5-10 realistic questions readers would ask.

**Step 2: Test with Sub-Agent** - For each question, invoke a sub-agent with just the document and the question. Summarize results.

**Step 3: Run Additional Checks** - Check for ambiguity, false assumptions, contradictions.

**Step 4: Report and Fix** - If issues found, loop back to refinement.

#### Testing Without Sub-Agents

Provide testing instructions:
1. Open a fresh Claude conversation
2. Paste or share the document content
3. Ask Reader Claude the generated questions
4. Also ask about ambiguity, assumed knowledge, contradictions

**Iterate Based on Results:** Fix gaps based on what Reader Claude got wrong.

**Exit Condition:** Reader Claude consistently answers correctly and doesn't surface new gaps.

### Final Review

When Reader Testing passes:
1. Recommend a final read-through by the user
2. Suggest double-checking facts, links, technical details
3. Ask them to verify it achieves the intended impact

Provide final tips:
- Consider linking this conversation in an appendix
- Use appendices to provide depth without bloating the main doc
- Update the doc as feedback is received from real readers

### Tips for Effective Guidance

**Tone:** Be direct and procedural. Explain rationale briefly when it affects user behavior.

**Handling Deviations:** If user wants to skip a stage, ask if they want to write freeform. Always give user agency.

**Context Management:** Proactively ask when context is missing. Don't let gaps accumulate.

**Artifact Management:** Use `create_file` for drafting, `str_replace` for all edits, provide artifact link after every change.

**Quality over Speed:** Don't rush through stages. Each iteration should make meaningful improvements.
