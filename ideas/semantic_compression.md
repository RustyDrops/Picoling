# Semantic Compression & Asymmetric Prompting

This document outlines a strategy for Picoling to optimize token usage and budget while maintaining a high-quality public persona.

## 1. Core Concepts

### Semantic Compression
Instead of "Caveman Mode" (which uses broken grammar), use "Semantic Compression." This instructs the AI to use professional but high-density language, stripping away "fluff" and introductory pleasantries while preserving technical signal.

### Asymmetric Prompting
The idea of having a "Compressed Core" for internal operations and an "Expansive Edge" for public-facing content.
- **Internal Agents (Coder, Researcher):** Use ultra-concise, high-density instructions to save tokens and fit within the 520KB RAM constraints.
- **External Agents (Blogger):** Use "Re-hydration" instructions to expand technical shorthand back into an engaging narrative.

## 2. Proposed Implementation

### A. The "Compressed Core" (Internal)
**Role: Coder/Researcher**
- **Goal:** Minimize output tokens and RAM usage.
- **Constraint:** Maintain MicroPython safety primitives (`gc.collect`, `try/finally`, etc.).
- **Instruction:** "Be concise. High-density logic only. Skip comments and explanations. Stability over brevity."

### B. The "Expansive Edge" (Public)
**Role: Blogger**
- **Goal:** High engagement and brand building.
- **Instruction:** "Your task is to EXPAND. The input provided is a highly compressed memory fragment. Re-hydrate the technical shorthand into an authentic, engaging first-person narrative."

## 3. Risks & Mitigations

| Risk | Mitigation |
| :--- | :--- |
| **Loss of Chain of Thought (CoT)** | Do not over-constrain the "thinking" phase; only compress the "output" phase to ensure the AI can still reason effectively. |
| **Missing Safety Code** | Explicitly list "Stability Primitives" as mandatory inclusions in the coder prompt. |
| **Hallucinated "Re-hydration"** | Ensure the internal summaries (Input to Blogger) include key "emotional" or "contextual" tags to guide the narrative. |

## 4. Dynamic Conciseness
A future refinement where the intensity of compression is tied to the **Budget Zone**:
- **Healthy:** Standard conciseness.
- **Cautious:** Aggressive semantic compression.
- **Emergency:** Maximum shorthand/Minimal tokens.
