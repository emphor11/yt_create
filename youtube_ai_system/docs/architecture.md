# YTCreate Architecture Migration

This document records the behavior-preserving system-design migration rules.
The current product behavior remains the source of truth until a later feature
change explicitly says otherwise.

## Layer Ownership

- `routes`: Flask HTTP adapters. Parse requests, call application use cases,
  flash messages, and render or redirect.
- `application`: Workflow orchestration. Use cases coordinate repositories,
  state transitions, services, and quality gates.
- `domain`: Stable product concepts such as projects, scripts, scenes, media,
  rendering, publishing, and finance terms.
- `contracts`: Data shapes that cross pipeline boundaries. Contracts wrap the
  current dict/JSON payloads before deeper migration.
- `pipelines`: Ordered transformations such as script, story, visual, media,
  assembly, and publishing pipelines.
- `infrastructure`: External systems and side effects including SQLite, LLMs,
  voice providers, Remotion, FFmpeg, YouTube, and filesystem storage.
- `quality`: Validation and acceptance rules.
- `observability`: Structured stage events, artifact references, traces, and
  failure records.

## Dependency Direction

Dependencies should flow inward from HTTP to application to domain/contracts,
then outward only through infrastructure adapters:

```text
routes -> application/use_cases -> pipelines/domain/contracts -> infrastructure
```

Infrastructure must not call routes or application use cases.

## Behavior Preservation

Refactor-only changes must preserve:

- route URLs and form fields
- template behavior
- project states and transitions
- SQLite schema and storage paths
- service entrypoints
- Remotion composition names and props
- generated artifact locations
- upload and assembly flow
- Groq prompt behavior
- renderer visuals

Current bugs stay unless a later commit is explicitly marked as a behavior fix.

## Current Phase

Phase 1 adds the package skeleton, shared result objects, typed compatibility
contracts, observability primitives, and use-case wrappers. Production routes
may continue to call the old services directly until wrappers are fully covered
by characterization tests.

## Commit Discipline

Each commit should be labeled by intent:

- `refactor-only`: architecture, extraction, naming, boundaries, tests
- `behavior-fix`: changes product behavior to fix a known issue
- `feature`: adds new user-facing capability

Do not mix behavior fixes into refactor-only commits.
