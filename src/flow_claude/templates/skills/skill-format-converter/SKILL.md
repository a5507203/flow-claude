---
name: skill-format-converter
description: Converts existing SKILL.md files to the extractable format required by the SkillLoader extraction system. Use when skill files need to be reformatted for selective section extraction, when creating SKILL_new.md variants, or when auditing skill modularization. Triggers on requests to convert skills, reformat skills for extraction, or analyze skill header structure.
---

# Skill Format Converter

## Shared Definitions

This skill converts SKILL.md files to a format compatible with the SkillLoader extraction system. The extraction system allows selective loading of skill sections by `## ` header name, reducing context window usage by loading only relevant sections.

**Output**: For each skill, create a `SKILL_new.md` file in the same directory with the adjusted format.

**Key Principle**: Modularization only helps when sections serve different user intents. Sequential workflows where all sections are always needed together should use a single `## All Contents` header.

## Extraction Logic

The SkillLoader (`extract_worker_skill.py`) works as follows:

1. **Parses YAML frontmatter** between `---` markers for `name` and `description`
2. **Splits markdown body by `## ` (H2 headers)** using regex `(?m)^##\s+(.+?)\s*$`
3. **Stores sections as dictionary**: `header_name -> "## header_name\n{content}"`
4. **Extracts requested headers** by name and concatenates them

**Critical implication**: Any content before the first `## ` header is LOST during extraction.

### Extraction Code Pattern
```python
# How sections are parsed
parts = header_pattern.split(body)  # splits by ## headers
for i in range(1, len(parts), 2):
    header_name = parts[i].strip()
    section_content = f"## {header_name}\n{parts[i+1].strip()}"
    sections[header_name] = section_content

# How sections are retrieved
for header in required_headers:
    if header in sections:
        final_context.append(sections[header])
```

## Conversion Workflow

### Step 1: Analyze Skill Structure

Read the existing SKILL.md and classify it:

**Question**: Can different user intents be served by different sections?

| Pattern | Example | Modularizable? |
|---------|---------|----------------|
| Operation-type separation | Read vs Write vs Delete operations | YES - different tasks need different sections |
| Reference material | Colors, Fonts, API endpoints | MAYBE - depends on usage patterns |
| Sequential workflow | Step 1 → Step 2 → Step 3 | NO - all steps always needed |
| Linear creative process | Philosophy → Implementation → Refinement | NO - can't skip steps |

### Step 2: Attempt Independent Content Identification

For skills that appear sequential, look for hidden independence:

**Questions to ask**:
1. Could a user need just the "reference" part without the "workflow" part?
2. Are there conceptually separate concerns (e.g., "technical requirements" vs "creative guidance")?
3. Could someone use this skill for different purposes requiring different information?

**Examples of hidden independence**:
- A "canvas-design" skill might separate "Design Philosophy Guidelines" (reusable theory) from "Canvas Creation Steps" (specific workflow)
- A "doc-coauthoring" skill might separate "Tips for Effective Guidance" (reference) from the sequential stages

**If independence found**: Create separate `## ` headers for each independent concern.

### Step 3: Choose Structure

**If independent sections exist** → Multiple `## ` headers:
```markdown
## Shared Definitions
Common context needed by all sections.

## Independent Section A
Content for user intent A.

## Independent Section B
Content for user intent B.
```

**If purely sequential/coupled** → Single `## All Contents` header:
```markdown
## All Contents
[Entire skill content here, using ### for subsections]

### Step 1: First Step
...

### Step 2: Second Step
...
```

### Step 4: Create SKILL_new.md

Transform the content following the chosen structure:

1. Keep frontmatter unchanged (name, description)
2. Move any intro content under first `## ` header
3. Use `### ` for subsections within `## ` sections
4. Validate no content exists before first `## `

## Format Templates

### Template A: Modularizable Skill (operation-type separation)
```markdown
---
name: skill-name
description: What it does and when to use it.
---

# Skill Title

## Shared Definitions
Overview, common context, output formats.

## Read Operations
How to read/analyze. Examples for read-only tasks.

## Write Operations
How to create/modify. Examples for write tasks.

## Reference
Dependencies, code style, additional resources.
```

### Template B: Sequential Workflow (not modularizable)
```markdown
---
name: skill-name
description: What it does and when to use it.
---

# Skill Title

## All Contents

### Overview
What this skill does.

### Step 1: First Step
Instructions for step 1.

### Step 2: Second Step
Instructions for step 2.

### Step 3: Final Step
Instructions for step 3.

### Resources
Dependencies, references.
```

## Decision Examples

### Example 1: docx skill → MODULARIZE
**Analysis**: User intents vary significantly
- "Read a docx" → needs Reading section only
- "Create new docx" → needs Creation section only
- "Edit with tracked changes" → needs Redlining section only

**Result**: Multiple `## ` headers (Read, Create, Edit, Redline)

### Example 2: algorithmic-art skill → SINGLE HEADER
**Analysis**: Linear creative workflow
- Philosophy → Conceptual Seed → Implementation → Artifact
- Cannot skip philosophy to jump to implementation
- All users need all steps

**Result**: Single `## All Contents` header

### Example 3: brand-guidelines skill → MODULARIZE (small)
**Analysis**: Reference material with distinct concerns
- Colors/Typography → quick lookup
- Technical Details → implementation specifics

**Result**: Keep separate headers, but skill is small enough that overhead is minimal

## Validation Checklist

After conversion:
- [ ] No content before first `## ` header
- [ ] If modularized: each section serves a distinct user intent
- [ ] If single header: uses `### ` for internal structure
- [ ] Frontmatter preserved with name and description
- [ ] All original content retained (just restructured)
