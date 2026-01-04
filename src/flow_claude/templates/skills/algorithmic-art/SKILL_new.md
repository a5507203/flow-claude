---
name: algorithmic-art
description: Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this when users request creating art using code, generative art, algorithmic art, flow fields, or particle systems. Create original algorithmic art rather than copying existing artists' work to avoid copyright violations.
license: Complete terms in LICENSE.txt
---

# Algorithmic Art Skill

## All Contents

Algorithmic philosophies are computational aesthetic movements that are then expressed through code. Output .md files (philosophy), .html files (interactive viewer), and .js files (generative algorithms).

This happens in two steps:
1. Algorithmic Philosophy Creation (.md file)
2. Express by creating p5.js generative art (.html + .js files)

### Philosophy Creation

To begin, create an ALGORITHMIC PHILOSOPHY (not static images or templates) that will be interpreted through:
- Computational processes, emergent behavior, mathematical beauty
- Seeded randomness, noise fields, organic systems
- Particles, flows, fields, forces
- Parametric variation and controlled chaos

**The Critical Understanding**:
- What is received: Some subtle input or instructions by the user to take into account, but use as a foundation; it should not constrain creative freedom.
- What is created: An algorithmic philosophy/generative aesthetic movement.
- What happens next: The same version receives the philosophy and EXPRESSES IT IN CODE - creating p5.js sketches that are 90% algorithmic generation, 10% essential parameters.

Consider this approach:
- Write a manifesto for a generative art movement
- The next phase involves writing the algorithm that brings it to life

The philosophy must emphasize: Algorithmic expression. Emergent behavior. Computational beauty. Seeded variation.

#### How to Generate an Algorithmic Philosophy

**Name the movement** (1-2 words): "Organic Turbulence" / "Quantum Harmonics" / "Emergent Stillness"

**Articulate the philosophy** (4-6 paragraphs - concise but complete):

To capture the ALGORITHMIC essence, express how this philosophy manifests through:
- Computational processes and mathematical relationships?
- Noise functions and randomness patterns?
- Particle behaviors and field dynamics?
- Temporal evolution and system states?
- Parametric variation and emergent complexity?

**CRITICAL GUIDELINES:**
- **Avoid redundancy**: Each algorithmic aspect should be mentioned once.
- **Emphasize craftsmanship REPEATEDLY**: The philosophy MUST stress multiple times that the final algorithm should appear as though it took countless hours to develop, was refined with care, and comes from someone at the absolute top of their field.
- **Leave creative space**: Be specific about the algorithmic direction, but concise enough that the next Claude has room to make interpretive implementation choices.

#### Philosophy Examples

**"Organic Turbulence"** - Chaos constrained by natural law, order emerging from disorder. Flow fields driven by layered Perlin noise. Thousands of particles following vector forces, their trails accumulating into organic density maps.

**"Quantum Harmonics"** - Discrete entities exhibiting wave-like interference patterns. Particles initialized on a grid, each carrying a phase value that evolves through sine waves. Simple harmonic motion generates complex emergent mandalas.

**"Recursive Whispers"** - Self-similarity across scales, infinite depth in finite space. Branching structures that subdivide recursively. L-systems or recursive subdivision generate tree-like forms.

**"Field Dynamics"** - Invisible forces made visible through their effects on matter. Vector fields constructed from mathematical functions or noise. Particles born at edges, flowing along field lines.

**"Stochastic Crystallization"** - Random processes crystallizing into ordered structures. Randomized circle packing or Voronoi tessellation.

**The algorithmic philosophy should be 4-6 paragraphs long.** Output as a .md file.

#### Essential Principles
- **ALGORITHMIC PHILOSOPHY**: Creating a computational worldview to be expressed through code
- **PROCESS OVER PRODUCT**: Beauty emerges from the algorithm's execution - each run is unique
- **PARAMETRIC EXPRESSION**: Ideas communicate through mathematical relationships, forces, behaviors
- **PURE GENERATIVE ART**: Making LIVING ALGORITHMS, not static images with randomness
- **EXPERT CRAFTSMANSHIP**: The final algorithm must feel meticulously crafted

### Conceptual Seed

**CRITICAL STEP**: Before implementing the algorithm, identify the subtle conceptual thread from the original request.

The concept is a **subtle, niche reference embedded within the algorithm itself** - not always literal, always sophisticated. Someone familiar with the subject should feel it intuitively, while others simply experience a masterful generative composition.

The reference must be so refined that it enhances the work's depth without announcing itself. Think like a jazz musician quoting another song through algorithmic harmony.

### P5.js Implementation

With the philosophy AND conceptual framework established, express it through code.

#### Step 0: Read the Template First

**CRITICAL: BEFORE writing any HTML:**

1. **Read** `templates/viewer.html` using the Read tool
2. **Study** the exact structure, styling, and Anthropic branding
3. **Use that file as the LITERAL STARTING POINT** - not just inspiration
4. **Keep all FIXED sections exactly as shown** (header, sidebar structure, Anthropic colors/fonts, seed controls, action buttons)
5. **Replace only the VARIABLE sections** marked in the file's comments

**Avoid:** Creating HTML from scratch, inventing custom styling, using system fonts or dark themes, changing the sidebar structure.

**Follow:** Copy the template's exact HTML structure, keep Anthropic branding, maintain the sidebar layout.

#### Technical Requirements

**Seeded Randomness (Art Blocks Pattern)**:
```javascript
let seed = 12345;
randomSeed(seed);
noiseSeed(seed);
```

**Parameter Structure**:
```javascript
let params = {
  seed: 12345,
  // Add parameters that control YOUR algorithm:
  // Quantities, Scales, Probabilities, Ratios, Angles, Thresholds
};
```

**Core Algorithm - EXPRESS THE PHILOSOPHY**:

If the philosophy is about **organic emergence**: Elements that accumulate/grow, random processes constrained by natural rules, feedback loops.

If the philosophy is about **mathematical beauty**: Geometric relationships, trigonometric functions, precise calculations creating unexpected patterns.

If the philosophy is about **controlled chaos**: Random variation within strict boundaries, bifurcation, order emerging from disorder.

**Canvas Setup**:
```javascript
function setup() {
  createCanvas(1200, 1200);
}

function draw() {
  // Your generative algorithm
}
```

#### Craftsmanship Requirements

- **Balance**: Complexity without visual noise, order without rigidity
- **Color Harmony**: Thoughtful palettes, not random RGB values
- **Composition**: Even in randomness, maintain visual hierarchy and flow
- **Performance**: Smooth execution, optimized for real-time if animated
- **Reproducibility**: Same seed ALWAYS produces identical output

#### Output Format

1. **Algorithmic Philosophy** - As markdown explaining the generative aesthetic
2. **Single HTML Artifact** - Self-contained interactive generative art built from `templates/viewer.html`

### Interactive Artifact Creation

Create a single, self-contained HTML artifact that works immediately in claude.ai or any browser.

**FIXED (always include exactly as shown):**
- Layout structure (header, sidebar, main canvas area)
- Anthropic branding (UI colors, fonts, gradients)
- Seed section: display, Previous/Next/Random/Jump buttons
- Actions section: Regenerate, Reset, Download PNG buttons

**VARIABLE (customize for each artwork):**
- The entire p5.js algorithm (setup/draw/classes)
- The parameters object
- The Parameters section controls (sliders, inputs)
- Colors section (optional - if art needs adjustable colors)

**Single Artifact Structure**:
```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.7.0/p5.min.js"></script>
  <style>/* All styling inline */</style>
</head>
<body>
  <div id="canvas-container"></div>
  <div id="controls"><!-- All parameter controls --></div>
  <script>
    // ALL p5.js code inline here
  </script>
</body>
</html>
```

**CRITICAL**: No external files, no imports (except p5.js CDN). Everything inline.

### Variations and Exploration

The artifact includes seed navigation by default. If the user wants specific variations:
- Include seed presets (buttons for "Variation 1: Seed 42", etc.)
- Add a "Gallery Mode" showing thumbnails of multiple seeds
- All within the same single artifact

### Creative Process

**User request** → **Algorithmic philosophy** → **Implementation**

1. **Interpret the user's intent** - What aesthetic is being sought?
2. **Create an algorithmic philosophy** (4-6 paragraphs)
3. **Implement it in code** - Build the algorithm
4. **Design appropriate parameters** - What should be tunable?
5. **Build matching UI controls** - Sliders/inputs for those parameters

### Resources

- **templates/viewer.html**: REQUIRED STARTING POINT for all HTML artifacts. Keep unchanged: Layout, Anthropic branding, seed controls, action buttons. Replace: The p5.js algorithm, parameter definitions, UI controls.

- **templates/generator_template.js**: Reference for p5.js best practices. NOT a pattern menu - use principles to build unique algorithms.
