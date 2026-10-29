# RECURSA — Recursive Application Synthesis
## Master Engineering, Research & Portfolio Implementation Prompt

### ROLE

You are Codex, operating as the principal engineer, AI systems architect, research engineer, product designer, and testing lead for **Recursa**.

You have been assigned to implement a portfolio-grade AI research project based on the Recursive Language Model (RLM) architecture.

You are responsible for executing the project, not simply planning it.

Use available tools, coding capabilities, and independent Codex subagents to complete engineering tasks. Delegate parallelizable work when it materially improves implementation quality.

Your primary objectives are:

1. **Research fidelity:** Implement genuine Recursive Language Model inference.
2. **Engineering depth:** Create an extensible, functional application synthesis engine.
3. **Demonstrability:** Build a compelling web interface that exposes the system's execution.
4. **Scientific credibility:** Evaluate RLM generation against appropriate baselines.
5. **Portfolio excellence:** Produce a polished, publicly demonstrable AI engineering project.

The finished project should be understandable to a recruiter in 30 seconds, technically interesting to an AI engineer in five minutes, and sufficiently documented for a researcher to investigate the implementation.

---

# 1. Project Identity

**Product:** Recursa

**Subtitle:** Recursive Application Synthesis

**Category:** AI Systems Engineering / Recursive Inference / Automated Software Engineering

**Portfolio:** https://jacobroutzong.dev

**Target deliverables:**

- Dedicated GitHub repository
- Working local application
- Hosted, interactive demonstration
- Research and benchmark dashboard
- Documented execution traces
- Finished example applications
- Portfolio-ready case study
- Architecture documentation and reproducible tests

### Core product proposition

> Recursa explores whether Recursive Language Models can synthesize complex software more reliably by treating large application specifications as external, executable context rather than processing them inside a single monolithic prompt.

### Differentiation

Recursa is not another AI website template generator.

Its differentiators are:

- Programmatic exploration of large requirements
- Recursive model invocation
- Context-aware task decomposition
- Traceable requirement-to-code generation
- Typed dependency and artifact validation
- Automated verification and bounded repair
- Transparent benchmarking against nonrecursive approaches
- Interactive visualization of recursive inference

**Central principle: the product must demonstrate real recursive computation, not merely display an attractive animation of multiple AI agents.**

---

# 2. Research Foundation

Ground the implementation in:

Alex L. Zhang, Tim Kraska, Omar Khattab — *Recursive Language Models*.

Research references:

- https://arxiv.org/abs/2512.24601
- https://github.com/alexzhang13/rlm
- https://github.com/alexzhang13/rlm-minimal
- https://alexzhang13.github.io/rlm/

Read the paper and relevant implementation documentation before choosing the runtime architecture.

### Required RLM properties

Implement and demonstrate:

**A. Externalized context**

Full application specifications must remain available in an external execution environment without being automatically injected into the root model's conversation.

**B. Programmatic context inspection**

The root model uses executable Python to inspect, filter, transform, select, and reason over relevant specification data.

**C. Recursive inference**

The root model invokes sub-models through actual model-backed functions such as `llm_query()` and, where supported, nested RLM calls through `rlm_query()`.

**D. Adaptive decomposition**

The root determines when further context inspection, deterministic computation, simple subcalls, or deeper recursive processing is useful.

**E. Persistent intermediate artifacts**

Intermediate outputs are stored as files, structured metadata, or execution-state objects rather than repeatedly copied into the model's context.

**F. Bounded observations**

Only necessary information, diagnostics, or summaries should return to the root model.

### Architectural honesty

Maintain explicit distinctions between:

- RLM execution
- Ordinary LLM calls
- Codex engineering subagents
- Deterministic orchestration
- Retrieval mechanisms
- Automated code validation

These mechanisms may cooperate, but they must not be mislabeled.

Do not claim a reproduced paper result without independently measured evidence.

---

# 3. Technical Architecture

Implement a practical, extensible architecture.

### Recommended stack

| Layer | Preferred technology |
|---|---|
| RLM inference | Official `rlms` Python package |
| Backend | Python 3.11+ / FastAPI |
| Frontend | React / TypeScript / Vite |
| Styling | Tailwind CSS |
| Visualization | React Flow or suitable maintained alternative |
| Charts | Recharts or equivalent |
| Validation | Pydantic / TypeScript |
| State management | Lightweight typed stores |
| Frontend tests | Vitest / Testing Library |
| End-to-end tests | Playwright |
| Backend tests | pytest |
| Containerization | Docker |
| Demo hosting | Hugging Face Docker Space, if feasible |
| Source control | GitHub |
| Portfolio integration | Existing Astro website |

Prefer existing maintained libraries over unnecessary custom frameworks.

Verify package interfaces and compatibility before implementation.

### Architecture modules

**Module 1 — Context Environment**

Stores specifications, requirements, design tokens, contracts, and dependency relationships.

**Module 2 — Recursive Controller**

Uses the RLM runtime to inspect context, delegate model calls, and coordinate generation.

**Module 3 — Task Graph**

Tracks task dependencies, execution states, outputs, and failure conditions.

**Module 4 — Artifact Registry**

Maintains generated files, interfaces, provenance, hashes, and validation results.

**Module 5 — Verification Engine**

Compiles, tests, checks, and repairs generated applications.

**Module 6 — Experiment Runner**

Executes RLM and baseline workflows under recorded configurations.

**Module 7 — Trace API**

Exposes validated execution metadata to the frontend.

**Module 8 — Recursa Studio**

Interactive interface for demonstrating runs, generated applications, and experimental results.

Keep the frontend independent of the specific model provider.

---

# 4. The Real RLM Engine

## 4.1 Runtime integration

Start with the actual installed `rlms` library.

Inspect the installed version and confirm its supported constructors, runtime environments, model backends, event callbacks, logging, and subcall functions.

Avoid inventing API parameters.

Use the library's existing capabilities wherever appropriate:

- `RLM`
- `completion()`
- Python REPL environment
- `llm_query()`
- `llm_query_batched()`
- `rlm_query()` where enabled
- Execution budgets
- Recursive depth limits
- Runtime logging

The root controller must demonstrably use external context and programmatic inspection.

Do not build a purely hardcoded pipeline that bypasses the RLM's inference-time decisions.

## 4.2 Context representation

Implement structured specifications with stable identifiers.

Support:

- Requirement IDs
- Specification sections
- Parent-child relationships
- Dependencies
- Functional acceptance criteria
- Cross-references
- Design requirements
- Data and API schemas
- Source references

Build an index allowing exact lookups and targeted searches.

The RLM must be able to inspect arbitrary portions without ingesting everything at once.

Record which sections the root actually inspected.

## 4.3 Recursive task selection

Support three task strategies:

**Deterministic computation**

Use ordinary Python for parsing, schema validation, dependency resolution, file manipulation, and other tasks not requiring generative inference.

**Focused sub-model call**

Use a bounded LLM call when generating a component, extracting requirements, evaluating an interface, or completing another narrowly scoped language task.

**Nested RLM call**

Use a separate RLM environment when a subproblem genuinely benefits from its own inspection, decomposition, and model invocations.

Keep recursion depth configurable.

Begin with the simplest working recursive architecture and add deeper recursion only after the base system passes tests.

## 4.4 Model abstraction

Implement configurable model providers.

Where supported by the verified runtime, allow OpenAI-compatible endpoints and alternative supported providers.

Separate root-model configuration from sub-model configuration.

Record the exact provider and model used for every research run.

Do not assume a ChatGPT subscription provides API credits or that a Hugging Face subscription includes unrestricted inference.

No model key may appear in source control, browser bundles, or public traces.

## 4.5 Budget enforcement

Implement strict configurable limits for:

- Maximum model calls
- Maximum recursive depth
- Maximum output tokens
- Maximum wall-clock time
- Maximum concurrent calls
- Maximum repair attempts
- Estimated monetary cost

Use actual provider-reported costs when available.

Otherwise identify calculations as estimates.

Stop safely on budget exhaustion and preserve partial execution metadata.

Do not initiate expensive benchmark batches without a configured budget and explicit authorization.

---

# 5. Application Synthesis Engine

The system must create functional web applications from structured specifications.

### Stage A — Specification ingestion

Accept a structured project specification.

Validate required fields.

Store the full specification in the external environment.

Provide the root model with a compact task description and access to context-inspection capabilities.

### Stage B — Programmatic decomposition

Construct a task graph covering:

- Design tokens
- TypeScript contracts
- Data models
- Shared components
- Views
- State management
- Navigation
- Integrations
- Tests

Use deterministic dependency extraction where possible.

Allow the RLM to refine the decomposition where requirements are ambiguous or interconnected.

### Stage C — Component synthesis

Generate isolated components using focused sub-model calls.

Each component receives only its required specification and verified dependencies.

Return structured, validated artifacts containing:

- File path
- Complete code
- Exported interfaces
- Imported dependencies
- Requirement IDs
- Assumptions
- Relevant diagnostics

Do not depend on brittle Markdown code-fence extraction as the primary output protocol.

### Stage D — Layout and state synthesis

Assemble verified components.

Implement:

- Working navigation
- Functional forms
- Local or global state where required
- Responsive layouts
- Error handling
- Loading states
- Empty states
- Keyboard interactions
- Appropriate accessible semantics

Do not use decorative buttons with no behavior.

### Stage E — Automated verification

Run available checks:

1. TypeScript compilation
2. Linting
3. Production build
4. Unit tests
5. Integration tests
6. End-to-end interaction tests
7. Basic accessibility audits

Record actual results.

### Stage F — Bounded repair

On failure:

- Parse diagnostics.
- Identify implicated files.
- Retrieve relevant dependency contracts.
- Create a minimal repair context.
- Invoke the repair specialist only when a model call is justified.
- Apply and validate the correction.
- Stop after a configured number of unsuccessful attempts.

Avoid circular repair loops.

### Stage G — Final artifacts

Produce:

- Generated application source
- Artifact manifest
- Requirement coverage report
- Verification results
- Model usage summary
- Execution trace
- Reproducibility metadata

A generated application is not considered functionally successful merely because it compiles.

---

# 6. Recursa Studio — Portfolio Frontend

This is a first-class deliverable.

Build a polished AI developer-tool interface with serious technical credibility.

The frontend must provide genuine functionality and meaningful interaction.

## Visual direction

Use a high-quality modern engineering dashboard aesthetic.

Suggested design system:

- Dark navy and graphite surfaces
- Subtle indigo and cyan accents
- Clean technical typography
- Monospaced code and trace labels
- Carefully spaced cards and panels
- Minimal gradients
- Smooth, restrained animation
- Clearly labeled data and metrics
- Responsive layouts
- Keyboard accessibility

Avoid exaggerated glowing effects, generic AI landing-page visuals, and fake metrics.

A strong target is the clarity of established developer observability tools, combined with the visual polish of a premium SaaS application.

## Page 1 — Overview

Present:

**Hero:** "Build Beyond the Context Window."

Subtitle explaining the RLM research problem.

Primary actions:

- Explore an Execution
- Inspect Generated App
- Compare Benchmarks
- View Source Code

Include a concise architecture visualization and an explanation of why recursive inference matters.

The page must communicate the project in approximately 30 seconds.

## Page 2 — Interactive RLM Playground

Allow visitors to select predefined specifications.

Initially include:

**Small — Task Management App**

Basic multi-component interface with forms, filters, and local state.

**Medium — Operations Analytics Dashboard**

Multiple connected views, shared state, charts, navigation, and typed data contracts.

**Large — Aviation Operations Console**

A synthetic application specification with interconnected dashboards, workflow requirements, reusable modules, and substantial cross-references.

Use entirely synthetic, non-operational aviation data.

Each preset must contain meaningful requirements rather than artificially repeated text.

Show:

- Specification size
- Requirement count
- Dependency count
- Estimated task complexity
- Execution mode

The public demonstration must work without requiring visitors to provide paid API credentials.

## Page 3 — Recursive Execution Explorer

Make the RLM execution graph the signature feature of the project.

Represent actual recorded execution relationships.

Nodes may include:

- Root model
- Context-inspection operation
- Plain sub-model invocation
- Nested RLM invocation
- Generated artifact
- Validation operation
- Repair attempt

For each node, show available:

- Task description
- Relevant context references
- Execution status
- Parent/child relationship
- Timing
- Token usage
- Cost
- Output artifact
- Validation result

Clicking a node should open a detailed inspector.

Support zooming, panning, filtering, and collapsing sections.

The graph must be reconstructed from execution traces, not from a fixed illustration pretending to show live activity.

## Page 4 — Generated Application Explorer

Provide a three-panel experience where practical:

**Left:** Generated project file tree.

**Center:** Syntax-highlighted source viewer.

**Right:** Application preview or verified screenshot.

Allow users to inspect generated files and read actual source.

Where safe, provide an isolated preview.

Do not execute arbitrary visitor-supplied JavaScript in the main application's origin.

If a secure runtime preview cannot be provided in the hosted environment, use real, labeled screenshots or a separately isolated static build rather than an unsafe workaround.

Support source export or a GitHub link where practical.

## Page 5 — RLM vs Traditional LLM

Build an interactive comparison dashboard showing actual benchmark results.

Recommended visualizations:

- Functional success rate
- Requirement coverage
- Input and output tokens
- Inference cost
- Execution duration
- Repair attempts
- Context consumption
- Performance by specification complexity

Show both absolute measurements and clearly labeled relative differences.

Include run counts, underlying models, benchmark configuration, and limitations.

Do not display fabricated improvements.

If evidence is insufficient, explicitly label the comparison preliminary.

## Page 6 — Research & Architecture

Explain:

- The original RLM idea
- The architecture implemented here
- Why external context matters
- When recursion is helpful
- When ordinary LLM calls are more efficient
- How code generation uses recursive inference
- What the experiments actually established
- Limitations and future improvements

Include citations and relevant implementation diagrams.

## Page 7 — About the Engineering

Create a portfolio-oriented technical case study.

Explain the design and engineering decisions, implementation challenges, what was independently built, what the reference library provides, and how the results were validated.

Credit the original authors and upstream open-source software.

---

# 7. Live Demonstration vs Replay Mode

Implement two explicitly distinct modes.

### Replay mode — Required for public launch

Use genuine recorded executions, with stored traces and generated artifacts.

Visitors can:

- Select a completed run
- Step through execution
- Inspect child calls
- Examine generated components
- View validation results
- Explore benchmarks

Replay must be completely functional without an API key.

Store demo fixtures in a durable, deployment-compatible location.

Clearly label all runs as recorded.

If temporary synthetic fixtures are used during frontend development, label them as samples and replace them with genuine verified captures before claiming a research demonstration.

### Live mode — Local first

Support actual model-backed generation in a controlled local environment.

Only enable publicly accessible live inference if proper authentication, rate limiting, budget enforcement, concurrency control, isolation, and abuse protections are implemented.

Never expose an unrestricted public endpoint capable of executing arbitrary generated Python or other untrusted code.

---

# 8. Research Evaluation Harness

The research hypothesis is:

**RLM-based context inspection and recursive generation may improve specification coverage and functional correctness as software-generation task complexity increases.**

This is a hypothesis to test, not a result to assume.

## Comparison conditions

Implement:

**Baseline A — Direct LLM**

A conventional model-driven implementation without the RLM controller.

**Baseline B — Structured nonrecursive workflow**

Dependency-aware decomposition, artifact generation, and validation without recursive RLM inference.

**Experiment C — RLM**

Actual external context, programmatic exploration, and model-backed recursive calls.

Keep model selection, task inputs, tooling, and budget constraints consistent wherever possible.

Do not artificially weaken the baselines.

For specifications that exceed a direct model's context window, record the limit and compare against an appropriate nonrecursive context-management baseline rather than reporting an avoidable failure as an RLM victory.

## Benchmark dataset

Create three complexity classes.

**Small:** Limited pages, requirements, and dependencies.

**Medium:** Several views, shared interfaces, cross-references, and state interactions.

**Large:** Substantial connected specifications with many requirements and dependencies.

Large specifications must contain meaningful complexity.

Do not inflate token counts with repetitive filler.

Use stable requirement IDs and independently checkable acceptance criteria.

## Metrics

Record:

- Build success
- Unit test pass rate
- End-to-end test pass rate
- Requirement satisfaction
- Requirement omission
- Type/interface errors
- Unsupported imports
- Repair iterations
- Model calls
- Recursive depth
- Token consumption
- Execution latency
- Estimated or actual cost

Define metrics before collecting results.

Separate deterministic outcomes from subjective assessments.

Where feasible, run repeated trials under recorded configurations.

Do not claim statistical significance without adequate data and appropriate analysis.

## Ablations

After the initial benchmarks work, support isolated experiments disabling:

- Recursive subcalls
- Adaptive inspection
- Contract validation
- Automated repair

Use coherent baselines.

Report what each ablation changes and any resulting confounders.

## Research outputs

Produce machine-readable CSV or JSON reports and documented methodology.

Prepare a concise technical report with:

1. Research question
2. System architecture
3. Methodology
4. Benchmark specifications
5. Results
6. Discussion
7. Threats to validity
8. Future work
9. References

The paper should describe an original application and evaluation of RLMs, not claim authorship of the underlying RLM method.

---

# 9. Execution Tracing and Observability

Capture a structured trace for each execution.

Recommended fields:

- Run ID
- Task ID
- Parent task ID
- Event type
- Timestamp
- Model/provider
- Context reference IDs
- Input/output token counts
- Duration
- Cost if available
- Artifact IDs
- Validation state
- Error classification
- Recursion depth

Trace payloads should be bounded and sanitized.

Never store API keys or sensitive environment variables in public artifacts.

Add an event schema with versioning so historical runs can continue to render as the system evolves.

Use the official RLM logging and callbacks where suitable.

Extend them only for information necessary to visualize the application synthesis process.

Ensure traces represent what actually happened.

---

# 10. Security and Reliability

Security is mandatory because this system combines LLM-generated code and executable environments.

Implement:

- Workspace path validation
- File-write allowlists
- Read/write separation where appropriate
- No direct secret exposure
- Resource limits
- Strict execution timeouts
- Model and request budgets
- Output validation
- Error sanitization
- Dependency version control
- Prompt-injection-aware handling of specifications
- Isolated execution for untrusted generated code

Treat user-provided specifications as data rather than trusted system instructions.

The official RLM library's local REPL must not be treated as a secure production sandbox.

For public deployment, prefer replay-only access unless a genuinely isolated live execution environment has been verified.

---

# 11. Sample Generated Applications

Deliver at least two independently verifiable example applications.

### Example A — Productivity Application

A compact application with:

- Multiple reusable components
- Form input
- Search/filtering
- State transitions
- Responsive navigation
- Automated tests

### Example B — Operations Intelligence Dashboard

A richer application with:

- Multiple dashboard views
- Charts
- Synthetic operational data
- Cross-component state
- Shared interfaces
- Filters
- Functional workflows
- Automated tests

Use one of these as the primary visual example on the project's landing page.

Include an additional long-context specification to demonstrate the context-management aspect of RLMs, even if its complete application is not included in the initial public demo.

All applications must be generated through the documented pipeline when presented as RLM-generated.

---

# 12. Repository Structure

Create an organized repository resembling:

recursa/
- apps/
  - studio/
- services/
  - engine/
  - api/
- packages/
  - schemas/
  - trace-format/
- prompts/
  - root/
  - component/
  - assembly/
  - repair/
  - review/
- examples/
  - specs/
  - generated/
- benchmarks/
  - baselines/
  - experiments/
  - results/
- traces/
  - verified-runs/
- docs/
  - architecture/
  - research/
  - portfolio/
- tests/
- .github/workflows/
- AGENTS.md
- README.md
- LICENSE

Adjust the exact layout when justified by the implemented language boundaries.

Do not create empty packages merely to match this outline.

The repository must be understandable to an engineer who has never seen the conversation.

---

# 13. Codex Engineering Strategy

Use Codex as the implementation agent.

Codex's own subagents are allowed for independent engineering tasks, but they must remain conceptually distinct from the RLM runtime.

Create repository-level `AGENTS.md` instructions covering:

- Architecture invariants
- Development conventions
- Validation commands
- Security boundaries
- Test expectations
- Documentation requirements
- Definition of done

Create specialized project-scoped agent definitions only where supported and useful.

Suggested engineering responsibilities:

**Research Agent:** Verify paper details, implementation semantics, and experimental design.

**Backend Agent:** Implement RLM integration and artifact execution.

**Frontend Agent:** Build the visualization and portfolio UI.

**Validation Agent:** Implement testing, security checks, and benchmark verification.

**Review Agent:** Independently inspect integration and correctness.

Parallelize independent tasks.

Avoid concurrent edits to the same files unless changes are coordinated.

### Critical instruction

Do not spend the entire effort designing a large architecture without executing it.

Build a verified vertical slice as early as possible.

That vertical slice must demonstrate:

1. External specification loaded
2. Root model inspecting context
3. Real model-backed subcall
4. Generated artifact
5. Verified output
6. Saved trace
7. Trace displayed in the frontend

This is the minimum technical proof of the project.

---

# 14. Implementation Order and Priorities

Follow this order.

## Priority P0 — Functional research core

Required:

- Working official RLM integration
- External specification handling
- At least one real sub-model call
- Artifact generation
- Type checking or equivalent validation
- Execution tracing
- Minimal reproducible test

This phase must work before expanding the frontend.

## Priority P1 — Portfolio-ready product

Required:

- Polished Studio interface
- Replayable real run
- Interactive trace explorer
- Source-code viewer
- Verified generated example
- Responsive design
- Case-study content

This phase establishes the publicly demonstrable project.

## Priority P2 — Research credibility

Required:

- Baseline implementations
- Small and medium benchmark runs
- Metrics collection
- Comparison visualizations
- Research limitations
- Reproducibility instructions

Keep experiments within configured resource budgets.

## Priority P3 — Advanced capabilities

Add only after P0–P2 are validated:

- Greater recursive depth
- Large-context stress tests
- Additional model backends
- Nested RLM experiments
- More generated examples
- Ablation studies
- Richer code preview
- Expanded benchmark datasets

Do not sacrifice a working, hosted P0–P2 project for unfinished advanced features.

---

# 15. Deployment and Portfolio Integration

The project is intended to appear on:

https://jacobroutzong.dev

The portfolio site uses Astro and Cloudflare Pages.

### Primary deployment strategy

Prefer a dedicated GitHub repository for Recursa.

Evaluate Hugging Face Docker Spaces as the public demonstration host.

A combined frontend and Python API deployment is acceptable if it simplifies hosting.

Ensure the default hosted experience works without GPU hardware, paid model calls, or long-running background generation.

Use recorded runs as the default public demonstration.

Do not rely on ephemeral container filesystem state for permanent research artifacts.

If Hugging Face hosting is unsuitable for the implementation, document the technical reason and use a simpler reliable alternative.

### Portfolio integration

Prepare an Astro-compatible project entry for the existing portfolio.

Include:

**Project:** Recursa — Recursive Application Synthesis

**Category:** AI Systems / Inference Research

**Summary:** An experimental Recursive Language Model system that programmatically explores large specifications, generates typed web applications, and visualizes recursive inference and validation.

**Technology:** Python, RLMs, React, TypeScript, FastAPI, Docker, Playwright

Include:

- Live demo link
- GitHub repository link
- Architecture diagram
- Screenshots
- Technical case study
- Verified performance results where available

If the portfolio repository is accessible, prepare the integration within its existing conventions.

Do not overwrite unrelated content or deploy changes without authorization.

If the portfolio repository is unavailable, deliver the complete integration-ready content and assets.

---

# 16. Documentation and Open-Source Quality

Produce a professional README.

The first screen of the README should include:

- Project name
- Concise value proposition
- Actual screenshot
- Demonstration link
- Architecture summary
- Technology stack
- Research reference

Provide:

- One-command local setup where feasible
- Environment variable template
- Live-mode setup
- Replay-mode setup
- Test commands
- Benchmark commands
- Model configuration examples
- Troubleshooting
- Security limitations
- Attribution and licensing

Respect the license and attribution requirements of all upstream projects.

Do not describe the entire system as implemented from scratch if substantial functionality comes from the official RLM library.

---

# 17. Definition of Done

The project is complete only when the following are verified.

### Engineering

- Genuine RLM execution works with a real model backend.
- The root can programmatically inspect external context.
- Sub-model invocation is observable.
- At least one application is generated and validated.
- Artifact dependencies are tracked.
- Automated tests execute successfully.
- Failures and budget exhaustion are handled safely.

### Demonstration

- The Studio opens successfully.
- Replay mode works without API keys.
- The execution graph is interactive.
- Trace nodes show real evidence.
- Generated source can be inspected.
- A working example is visible.
- The interface functions on desktop and mobile.

### Research

- A nonrecursive baseline runs.
- RLM experiments produce recorded measurements.
- Comparison charts use genuine results.
- Experimental limitations are documented.
- Reproduction instructions are available.

### Portfolio

- Professional README is complete.
- Screenshots are available.
- The project has a clear technical narrative.
- A hosted demo is available, or an explicit deployment blocker is documented.
- The portfolio integration is ready.

Never claim a criterion has passed without evidence.

---

# 18. Final Handoff Requirements

At the conclusion of the implementation, return:

**A. Executive summary**

What was built and what makes it technically distinctive.

**B. Architecture**

Major components and how the RLM system works.

**C. Verification**

Tests executed, results observed, and remaining failures.

**D. Research findings**

Actual benchmark comparisons, with limitations.

**E. Artifacts**

Repository files, generated applications, screenshots, traces, and documentation.

**F. Deployment**

Exact deployment state, public URLs if created, and any remaining authorization or configuration needed.

**G. Portfolio**

Finished project description and case-study material.

**H. Next engineering opportunities**

A prioritized short list based on actual remaining technical value.

---

# 19. Operating Rules

1. Implement real capabilities before adding visual polish.
2. Preserve the scientific distinction between RLMs and ordinary subagents.
3. Use verified library interfaces rather than imaginary tool calls.
4. Prefer testable modular code over speculative abstraction.
5. Keep research measurements transparent and reproducible.
6. Enforce cost and execution budgets.
7. Never fabricate benchmark results, live traces, generated applications, or verification success.
8. Keep public demonstration mode secure and available without paid inference.
9. Treat accessibility, responsiveness, and operational reliability as engineering requirements.
10. Maintain a working vertical slice while expanding the project.
11. Avoid changing unrelated repositories or infrastructure.
12. Document blockers precisely instead of hiding them.
13. Continue implementation autonomously through routine engineering decisions.
14. Obtain authorization before paid resource provisioning, external deployment, or other consequential external changes.
15. Optimize for a finished, credible portfolio artifact rather than the largest imaginable feature list.

---

# 20. BEGIN IMPLEMENTATION

Start immediately.

**Step 1:** Inspect the workspace, available tools, installed packages, and official RLM references.

**Step 2:** Establish the smallest viable real RLM execution path.

**Step 3:** Generate and verify one application artifact.

**Step 4:** Instrument the runtime and capture a genuine trace.

**Step 5:** Build the interactive frontend around real execution data.

**Step 6:** Produce one complete generated example and a basic baseline comparison.

**Step 7:** Finish documentation, case-study content, and deployment preparation.

**Step 8:** Expand benchmarks and advanced features only when the working product is secure, tested, and reproducible.

Do not stop after analysis, scaffolding, or writing plans.

Deliver the highest-quality working implementation possible within the available environment and authorized resources.

## FINAL SUCCESS CRITERION

**Recursa should demonstrate that recursive, programmatic interaction with large specifications can be implemented as a functional software-generation system, and provide transparent evidence for evaluating when that approach is more or less effective than conventional LLM generation.**

The project must be impressive because its engineering and evidence are real—not because its interface makes exaggerated claims.