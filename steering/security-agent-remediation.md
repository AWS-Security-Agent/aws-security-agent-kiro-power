---
inclusion: auto
name: security-agent-remediation
description: Pull AWS Security Agent findings (penetration tests and code reviews) and drive remediation. Use this whenever the user mentions Security Agent, security findings pentest or penetration test results, code review findings, vulnerabilities found in their AWS account, "Help me remediate my findings", remediating or triaging security risks, or wants to start fixing reported vulnerabilities — even if they don't name the service explicitly. Trigger it for phrases like "let's fix the pentest results", or "triage the security report". The skill discovers scans, exports findings to a gitignored local directory (so sensitive exploit detail is never committed), produces prioritized triage summary, and offers to start a spec session to fix the highest-risk issues.
---

# Security Agent Remediation

AWS Security Agent is a frontier agent that runs on-demand penetration tests and code
reviews against a customer's applications and reports verified security risks. This skill
takes you from "I have findings somewhere in AWS" to "I'm actively fixing the most
important ones," while keeping the sensitive exploit detail out of source control.

The flow has four stages, and they matter in order:

1. **Discover** which scans exist and how the account is configured (live, read-only).
2. **Export** the findings to a local gitignored directory using a deterministic script.
3. **Triage** the findings into a prioritized, human-readable plan.
4. **Remediate** by offering to start a Kiro spec session for the top issues.

## Why the ordering and the guardrails matter

Findings contain working attack scripts, reproduction steps, file paths, and sometimes
leaked secrets or environment details. If that lands in a Git repo, a customer can
accidentally commit and publish a step-by-step exploit for their own production system.
So the non-negotiable rule is: **findings are written only to `.security-agent/`, and that
path is gitignored before anything is written.** The bundled script enforces this with a
belt-and-suspenders `.gitignore` inside the directory too, but you should still confirm
the repo-level ignore is in place.

Discovery is read-only and uses live AWS calls so the user sees their real scans. The bulk
findings pull is a deterministic Python script (boto3) rather than ad-hoc calls, because
pagination, batching, and confidence filtering should behave the same way every time and
not depend on the model improvising CLI invocations.

## Stage 1: Discover scans (live, read-only)

Find out what the account has. Prefer the AWS API MCP server (the `call_api` tool) so the
calls are visible and audited; if it isn't available, run the same commands with the AWS
CLI directly. All commands are read-only `list-*` operations.

AWS Security Agent organizes data as a hierarchy — work down it:

```
Application (account + Region)
└── Agent Space        (workspace for design review, code review, and pentests)
    ├── Penetration test → Pentest job → Findings
    └── Code review      → Code review job → Findings
```

Run these to orient yourself and show the user what exists:

```bash
aws securityagent list-agent-spaces
aws securityagent list-pentests          --agent-space-id <as-...>
aws securityagent list-code-reviews      --agent-space-id <as-...>
aws securityagent list-pentest-jobs-for-pentest         --agent-space-id <as-...> --pentest-id <pt-...>
aws securityagent list-code-review-jobs-for-code-review --agent-space-id <as-...> --code-review-id <cr-...>
```

Job `status` is one of `IN_PROGRESS`, `STOPPING`, `STOPPED`, `FAILED`, `COMPLETED`. Only
`COMPLETED` jobs have a stable, full set of findings.

### Match the codebase to a scan, then confirm

Agent spaces, pentests, and code reviews are named after the application they target.
Before asking the user to pick from a raw list, make an informed guess about which scan
corresponds to *this* repository — the user is working in a codebase for a reason, and
the relevant findings are almost always for the app in front of them.

Infer the app identity from the workspace using cheap, high-signal sources:

- The repository / root directory name and the Git remote URL (`git remote -v`).
- Project manifests and their `name`/`description` (`package.json`, `pyproject.toml`,
  `*.csproj`, `go.mod`, `Cargo.toml`).
- README titles, product/steering docs, and any obvious product or company name.
- Distinctive frameworks or domains that match a scan title.

Compare those signals against the agent space / scan names (case-insensitive, allow
partial and fuzzy matches in a README maps to an agent space).
Then **always confirm before exporting** — present your best guess and your reasoning, and
let the user correct it:

> "This repo looks like **<product>** (from `<signal>`), which matches the **<name>** agent
> space. Use that, or pick another? [Other Agent Space names, ...]"

If nothing matches with reasonable confidence, say so plainly and show the full list rather
than forcing a wrong guess. If several scans match, surface the top candidates and ask.
Never export from a guessed scan without the user's confirmation — pulling the wrong app's
findings wastes time and writes unrelated sensitive data locally. Once the user confirms,
pass the chosen IDs explicitly to the export script rather than relying on its
"most recent" default.

## Stage 2: Export findings to `.security-agent/` (gitignored)

Pull the findings yourself with direct AWS Security Agent API calls. The Security Agent
power bundles an MCP server, so prefer the `call_api` tool from that server — it gives
visible, audited calls and avoids shelling out. Use `get_api_guide` if you need to
discover operation names. Fall back to the AWS CLI (`aws securityagent ...`) only if the
MCP tools aren't available. Write everything into `.security-agent/` in the repo — never
to chat or stdout — because findings include working attack scripts, reproduction steps,
and sometimes leaked secrets.

`call_api` takes an operation in PascalCase and a `params` JSON object whose keys are
camelCase (e.g. `agentSpaceId`, `pentestJobId`, `findingIds`). All examples below show the
operation + params you should pass.

### 1. Lock down the output directory before pulling anything

Create `.security-agent/.gitignore` containing `*` so the directory is gitignored.

### 2. Resolve the agent space, scan, and latest COMPLETED job

You should already have the `agentSpaceId` (and the pentest / code-review id) from
Stage 1's confirmation step — pass them explicitly. If the user didn't pin them, fall
back to the most recently updated entry from `ListAgentSpaces` / `ListPentests` /
`ListCodeReviews` (sort by `updatedAt`, take the max). Then list jobs for the chosen
scan and pick the latest `COMPLETED` one — that's the only status with a stable, full
set of findings:

```text
# Pentest jobs:
call_api(operation="ListPentestJobsForPentest",
         params={"agentSpaceId": "as-...", "pentestId": "pt-..."})

# Code review jobs:
call_api(operation="ListCodeReviewJobsForCodeReview",
         params={"agentSpaceId": "as-...", "codeReviewId": "cr-..."})
```

Paginate every list call by passing the previous response's `nextToken` back as
`params["nextToken"]` until it's absent. Filter the `*JobSummaries` to
`status == "COMPLETED"`. If the filtered list is empty (no completed jobs exist), stop
and tell the user "No completed jobs found. Please wait for a job to complete or check
job statuses." Otherwise, pick the COMPLETED job with the greatest `createdAt` timestamp.

### 3. List finding summaries for the chosen job and filter by confidence

```text
# Pentest:
call_api(operation="ListFindings",
         params={"agentSpaceId": "as-...", "pentestJobId": "ptj-..."})

# Code review:
call_api(operation="ListFindings",
         params={"agentSpaceId": "as-...", "codeReviewJobId": "crj-..."})
```

Paginate on `nextToken` until exhausted. Confidence values reported by the service,
weakest → strongest, are: `FALSE_POSITIVE`, `UNCONFIRMED`, `LOW`, `MEDIUM`, `HIGH`.
**Keep only `HIGH` and `MEDIUM` by default.** The lower bands are noisy; widen only when
the user explicitly asks.

### 4. Fetch full detail in batches of 25

`BatchGetFindings` accepts at most 25 ids per call. Chunk the filtered finding ids into
groups of 25, call it once per chunk, then concatenate every `findings` array:

```text
call_api(operation="BatchGetFindings",
         params={"agentSpaceId": "as-...",
                 "findingIds": ["fid-1", "fid-2", "...", "fid-25"]})
```

Tag each returned finding with its source — `"source": "pentest"` or
`"source": "code-review"` — before writing, so triage in Stage 3 can tell them apart.

### 5. Write findings into `.security-agent/`

Group findings by job id. For each job, write:

- `findings_<jobId>.md` — the full response from the BatchGetFindings call. Do not leave
  off any fields.

### Edge cases

- **No agent space, scan, or COMPLETED job** — stop and surface that to the user rather
  than retrying. It usually means the scan hasn't finished or credentials point at the
  wrong account.
- **Credentials or service unavailable** — confirm with `aws sts get-caller-identity` and
  check the Region (default `us-east-1`; Security Agent is regional).
- **Don't paste finding contents into chat** beyond short titles and counts. The detail
  belongs in the gitignored files.

## Stage 3: Triage into a prioritized plan

Rank by risk, because remediation time is finite and a CRITICAL unauthenticated RCE
outranks a LOW informational finding every time. Read the exported `findings_*.md`
files from `.security-agent/` and sort them deterministically — don't eyeball the order.

### Ranking rules

Sort ascending by this composite key (lower wins, i.e. more urgent first):

1. **Risk level**, in this order:
   `CRITICAL` (0) → `HIGH` (1) → `MEDIUM` (2) → `LOW` (3) → `INFORMATIONAL` (4) →
   `UNKNOWN` / missing (5).
2. **Risk score**, highest first. `riskScore` is a numeric string on pentest findings
   (e.g. `"10.0"`), often absent on code-review findings — coerce it to a float, treat
   missing as the lowest possible score so it sorts after scored findings of the same
   level.
3. **Confidence**, in this order:
   `HIGH` (0) → `MEDIUM` (1) → `LOW` (2) → `UNCONFIRMED` (3) → `FALSE_POSITIVE` (4).

Also compute a severity-count summary across all findings (e.g. `2 CRITICAL · 5 HIGH ·
3 MEDIUM`) for the header of the report.

### Pulling the code location

For each finding, derive a single short `location` string:

- If `filePath` is set, use it as-is.
- Otherwise, take `codeLocations[0]`. Strip the scanner's sandbox prefix from `filePath`
  (everything up to and including that marker) so the path is repo-relative; if that
  marker isn't present, fall back to the basename. Append `:<lineStart>` when present.
- If neither is available (typical for some pentest findings), leave it blank and
  describe the affected endpoint or attack chain in the impact line instead.

### Summary format

Use the ranked output to write a compact summary for the user with this structure:

```
## Security Agent triage — <agent space name>

<N> findings exported (<P pentest, C code review>) · confidence: <levels> · severity: <counts>

### Priority order
1. [CRITICAL · score 10.0 · HIGH confidence] <finding name>
   - Type: <riskType> · Source: <pentest|code-review>
   - Where: <file:line or endpoint, if present>
   - Impact: <one-line plain-language summary>
2. [HIGH · ...] ...

### Recommended remediation order
<short rationale: which to fix first and why — e.g. "1 and 3 are both
unauthenticated RCE on internet-facing endpoints; fix those before the
stored-XSS issues.">
```

If the user asked for "just the top N" or you have more than ~10 findings, show the top
N in detail and summarize the rest as a count by severity at the bottom.

### What to keep out of chat

The full `description`, `reasoning`, and `attackScript` stay in the gitignored files —
they contain working exploit detail. In the chat summary keep impact lines to one line
each, in plain language. Code-review findings usually carry a `filePath`/location and a
`suggestedFix`; call those out since they map directly to repo changes. Pentest findings
describe endpoints and attack chains; map them to the responsible code where you can.
Look for findings that corroborate each other (a pentest and a code review flagging the
same root cause) — those are strong signals for what to fix first.

## Stage 4: Offer to remediate via a spec session

After presenting the triage, offer to start fixing — don't silently begin editing code.
Security fixes change behavior (auth, validation, parsing) and deserve a deliberate plan,
so the natural next step is a **bugfix spec session** scoped to the top finding(s).

Ask the user something like: "Want me to start a spec session to fix the top finding(s)?
I'd recommend starting with #1 (<name>)." If they agree, kick off a spec by describing the
selected finding as a bug to fix — feed in the finding's title, affected location, impact,
and the suggested fix (for code reviews) as the seed for the spec. Reference the finding by
`findingId` and pull detail from the gitignored file rather than restating exploit steps in
the spec prose.

If the user wants to handle several findings, scope one spec per finding (or one per tightly
related cluster) so each fix stays reviewable, and proceed in the priority order from
Stage 3.
