---
name: "aws-security-agent"
displayName: "AWS Security Agent"
description: "AI-powered security scanning, threat modeling, and penetration testing. Run threat model reviews on design docs, full or diff scans to help find code vulnerabilities, pentest live applications and triage and fix verified findings."
keywords: ["Help me remediate my findings", "is my code secure", "code security", "security scan", "security vulnerabilities", "remediate findings", "pentest", "penetration test", "test my app", "attack surface", "code review", "sast", "owasp", "cve", "audit", "compliance", "production ready", "security review", "triage findings", "security agent", "threat model", "threat modeling", "threat model review", "design review", "security posture", "STRIDE", "security concern", "doc review", "document review"]
author: "AWS"
homepage: "https://docs.aws.amazon.com/securityagent/"
repository: "https://github.com/AWS-Security-Agent/aws-security-agent-kiro-power"
---

# AWS Security Agent

You are enhanced with the AWS Security Agent, an AI-powered security scanner. You access it through the `security-agent` MCP server to run automated security code reviews and penetration tests.

---

## When to use this power

- **Direct security requests** — scans, audits, vulnerability checks
- **Workflow checkpoints** — pre-commit, pre-PR, pre-deploy, prod-readiness
- **Code change events** — after adding endpoints, auth, features, or refactors
- **Spec / design authoring** — writing or editing a spec, drafting `requirements.md` or `design.md` (e.g. under `.kiro/specs/`), or about to generate `tasks.md` from a spec
- **Pentest scenarios** — testing live apps, attack surface
- **Ambiguous code-quality requests** ("review my code") — proactively offer a security check
- **Remediating findings from scans** - start spec driven development to remediating findings in Code review and Penetration tests

---

## Tools Available

| Tool | Purpose |
|------|---------|
| `setup_check` | Verify prerequisites (AWS creds, agent space, service role) |
| `setup` | Provision or reuse: agent space, IAM role |
| `start_security_scan` | Zip code → upload → start full scan. Returns immediately with scan_id |
| `start_diff_scan` | Upload current repo + git diff → start scan focused on changes |
| `start_threat_model_review` | Upload spec docs (`requirements.md`/`design.md`) + source → start a threat model job that checks whether the design affects the security posture |
| `get_scan_status` | Check scan progress (step, elapsed time) |
| `get_scan_findings` | Get findings (works during scan for partial results or after completion) |
| `list_scans` | List recent scans |
| `stop_scan` | Cancel a running scan |
| `call_api` | Call any SecurityAgent API operation directly |
| `get_api_guide` | List all available API operations |

---

## Action mapping

When the power is activated, route to the right workflow based on user intent:

| User intent | Action |
|-------------|--------|
| Direct scan request ("scan my code", "find vulnerabilities") | Run Security Code Scan workflow |
| Workflow checkpoint ("ready to commit", "PR ready", "prod ready") | **Suggest** a diff scan: "Want a quick security scan first?" Wait for confirmation. |
| Code change event ("I added X", "refactored Y") | **Suggest** a diff scan |
| Spec/design authoring, or about to generate `tasks.md` from a spec | **Suggest** a threat model review FIRST: "Before I generate tasks, want me to run a threat model review on `requirements.md`/`design.md` to check for breaking changes to your security posture?" Wait for confirmation. |
| Pentest request ("test my app", "penetration test") | Run Pentest workflow |
| Scan status check ("how's the scan", "progress") | Call `get_scan_status` |
| View findings ("what did it find", "show results") | Call `get_scan_findings` |
| Advanced API operations ("target domains", "integrations") | Call `get_api_guide` then `call_api` |
| Remediate findings ("remediate findings", "create bug spec") | Use `security-agent-remediation.md` steering file |

### Rules for proactive suggestions
- Always ask before running — never auto-trigger scans
- Make it a single-line suggestion, not a multi-paragraph pitch
- If user declines or says "not now", don't bring it up again in the same session
- For first-time users without setup, suggest setup first
- Diff scans don't require a prior full scan — they upload the repo + diff each time

---

## Workflow: First-Time Setup

1. Call `setup_check`
2. If not ready and `existing_agent_spaces` is returned:
   - Show the list to the user: "Found these agent spaces: [names and IDs]. Would you like to use one of these, or should I create a new one?"
   - Wait for the user's response
   - If user selects an existing space: call `setup(agent_space_id="as-xxxxx")` directly — the server will check and register the role automatically.
   - If user wants a new space: Ask "Do you have an existing IAM service role, or should I create one?" Then call `setup(name="my-scans")` or `setup(name="my-scans", service_role_arn="arn:...")`
3. Ask: "What directory should scans be restricted to? This sets a security boundary so the scanner only accesses files within that path. Enter an absolute path (e.g., `/Users/you/projects`) or say 'skip' to allow scanning any directory."
   - If user provides a path → write `WORKSPACE_ROOT` into `~/.kiro/powers/installed/aws-security-agent-kiro-power/mcp.json` env block: `"WORKSPACE_ROOT": "/user/provided/path"`
   - If user says skip → leave `WORKSPACE_ROOT` unset (scans work on any absolute path)
4. Confirm: "Setup complete. You can now run security scans."
5. Run the **Auto Diff-Scan-Suggestion Hook** section below only after all the setup is completed.

---

## Auto Diff-Scan-Suggestion Hook (default ON)

After EVERY `setup_check` call (whether the result is ready or not-ready), run this check.

This hook only suggests **diff scans** (fast). Full scans are slower and should only run when the user explicitly asks for them.

The hook is **opt-out** — install it by default. Only skip if the user explicitly says no.

1. Check if `.kiro/hooks/security-diff-scan-suggester.kiro.hook` already exists in the workspace.
2. If it exists → continue silently (already configured, do not mention it).
3. If it does NOT exist:
   - Tell the user (single line, no question): "Adding a hook that will let Kiro decide on every turn if a diff scan is needed for security. You can opt out — just say 'skip the hook' or delete `.kiro/hooks/security-diff-scan-suggester.kiro.hook` anytime."
   - **Default action: install the hook.** Only skip if the user replies with an opt-out ("skip", "no", "don't install", "not now").
   - To install, create `.kiro/hooks/security-diff-scan-suggester.kiro.hook` with:
     ```json
     {
       "name": "Security Diff-Scan Suggester",
       "version": "1.0.0",
       "description": "After each agent turn, evaluate if completed security-sensitive changes warrant a diff scan.",
       "when": { "type": "agentStop" },
       "then": {
         "type": "askAgent",
         "prompt": "Evaluate the code changes from this turn. A change is security-sensitive ONLY if untrusted input (request params, headers, body, file uploads, external data) flows into a sensitive sink (SQL without parameterization, shell/subprocess, filesystem paths, network requests, deserialization, auth decisions, or secrets). Also trigger for changes to authentication, authorization, cryptography, or security configuration (CORS, headers, session handling). Do NOT trigger for: new endpoints that only read data with parameterized queries, refactoring that preserves behavior, test/doc/logging changes, cosmetic edits, or adding static configuration. Completeness check: only trigger if the work is done — the user committed, said done, or the agent completed the requested task with no pending follow-ups. Do NOT trigger if the agent indicated more work is coming, the user asked for additional changes, or implementation is partial. If security-sensitive AND complete: say one line — 'Changes affect security posture — running a diff scan.' — then run the **Diff Scan** workflow from the AWS Security Agent power (base_ref='HEAD'). No permission needed. Otherwise output absolutely nothing."
       }
     }
     ```
   - After installing, briefly confirm: "Hook installed. I'll watch for security-sensitive changes after each turn."
   - If the user opts out, say: "Skipping the hook. Say 'install diff-scan hook' anytime to set it up later." Do not ask again this session.

---

## Workflow: Security Code Scan (Full)

Use for periodic comprehensive review of the entire codebase. Slower but thorough.

1. `setup_check` → verify ready
2. `start_security_scan(path="<absolute-workspace-path>", title="<workspace-name>-<branch-name>")`
   - `path` must be an absolute path (not `"."`)
   - Title should be unique per scan — include workspace name and branch for traceability. If not provided, the server auto-generates one with client prefix and timestamp.
   - Returns immediately with scan_id
3. Tell user: "Scan started (scan_id: {id}). I'll check every 5 minutes and report when it's done — say 'check status' anytime, or 'stop polling' to opt out."
4. **Default polling pattern** (do NOT poll faster than this):
   - **Wait 5 full minutes** between each `get_scan_status` call — use `sleep 300` via Bash before each check
   - First check: at the 5-minute mark (NOT immediately after start)
   - Only respond to the user when status CHANGES (e.g., IN_PROGRESS → COMPLETED) or when scan finishes
   - Do NOT report "still in progress" multiple times — that's noise
   - If user says "stop polling" or "check later" → stop and tell them: "Say 'scan status' or 'show findings' anytime."
5. Findings can be fetched anytime with `get_scan_findings` — even during IN_PROGRESS (partial results)
6. On COMPLETED → `get_scan_findings` for final results
7. Present findings grouped by severity (see Findings Presentation section)

---

## Workflow: Diff Scan (Fast)

Use for checking only what changed since a git ref. Recommended for pre-commit, pre-PR, and pre-deploy workflows.

1. `setup_check` → verify ready. After every setup_check, also run the **Auto Diff-Scan-Suggestion Hook** section (do not skip).
2. Ask user what to scan:
   - Uncommitted changes → `base_ref="HEAD"` (default)
   - Branch vs main → `base_ref="main"`
   - Custom ref → user provides
3. `start_diff_scan(path="<absolute-workspace-path>", base_ref="<chosen-ref>")`
   - **path MUST be the user's current workspace absolute path** (e.g., `/Users/foo/my-repo`), NOT `"."` — the MCP server runs as a subprocess and `"."` resolves to its own directory
   - Uploads current repo zip + git diff patch
   - Returns immediately with scan_id
4. Tell user: "Diff scan started. I'll check every 2 minutes and report when it's done — say 'stop polling' to opt out."
5. **Default polling pattern** (do NOT poll faster than this):
   - **Wait 2 full minutes** between each `get_scan_status` call — use `sleep 120` via Bash before each check
   - First check: at the 2-minute mark (NOT immediately after start)
   - Only respond to the user when status CHANGES (e.g., IN_PROGRESS → COMPLETED) or when scan finishes
   - Do NOT report "still in progress" multiple times — that's noise
   - If user says "stop polling" or "check later" → stop and tell them: "Say 'scan status' or 'show findings' anytime."
6. On COMPLETED → `get_scan_findings` → present findings focused on changed code

No prior full scan needed — diff scans are standalone.

---

## Workflow: Threat Model Review (spec/design)

Use when the user is authoring or changing a spec — to verify whether the `requirements.md` / `design.md` introduce any breaking changes to the application's security posture. Analyzes the source code guided by the spec docs and returns threats (STRIDE) with severity and recommendations.

1. `setup_check` → verify ready
2. Collect the spec files to review — the `requirements.md` and `design.md` the user is working on (e.g. under `.kiro/specs/<feature>/`). Use their absolute paths.
3. `start_threat_model_review(path="<absolute-workspace-path>", specs=["<abs>/requirements.md", "<abs>/design.md"])`
   - **path MUST be the user's current workspace absolute path** (e.g., `/Users/foo/my-repo`), NOT `"."` — the MCP server runs as a subprocess and `"."` resolves to its own directory
   - **specs MUST be absolute paths**; at least one is required
   - Returns immediately with scan_id
4. Tell user: "Threat model review started. I'll check every 5 minutes and report when it's done — say 'stop polling' to opt out."
5. **Default polling pattern** (same as full scan): wait 5 full minutes between each `get_scan_status` call (`sleep 300` via Bash), first check at the 5-minute mark, and only respond when status CHANGES or the job finishes.
6. On COMPLETED → `get_scan_findings` → present the threats grouped by severity. Each threat has: `statement`, `severity`, `stride`, `threatImpact`, `recommendation`, `impactedAssets`. Call out any threat that represents a regression from the prior design as a security-posture breaking change.
7. Follow the **Findings Presentation** section below to write the full report to `.security-agent/findings-{scan_id}.md`.

No prior scan needed — threat model reviews are standalone.

---

## Workflow: Penetration Test (via call_api)

1. `setup_check` → `setup` (one-time)
2. `call_api("CreateTargetDomain", {agentSpaceId, targetDomainName, verificationMethod: "HTTP_ROUTE"})`
3. `call_api("VerifyTargetDomain", {agentSpaceId, targetDomainId})`
4. `call_api("CreatePentest", {agentSpaceId, title, assets: {endpoints: [{uri: "..."}]}, serviceRole: "arn:..."})`
5. `call_api("StartPentestJob", {agentSpaceId, pentestId})`
6. Poll with `call_api("BatchGetPentestJobs", {agentSpaceId, pentestJobIds: [...]})` until COMPLETED
7. `call_api("ListFindings", {agentSpaceId, pentestJobId})` → results

Pentests run for an extended duration depending on scope.

---

## Workflow: Any Other Operation (via call_api)

1. `get_api_guide` → see all available operations
2. `call_api(operation, params)` → execute

---

## Findings Presentation

After any scan completes, do BOTH of these:

### 1. Concise summary in chat

Group by severity, show file path + line number for each finding:

```
🟣 CRITICAL: {name}
   File: {filePath}:{lineStart}
   {description}

🔴 HIGH: {name}
   File: {filePath}:{lineStart}
   {description}

🟡 MEDIUM: {name}
   File: {filePath}:{lineStart}
   {description}

🟢 LOW: {name}
   File: {filePath}:{lineStart}
   {description}
```

### 2. Detailed report file

Write a full markdown report to `.security-agent/findings-{scan_id}.md` in the workspace root. The report MUST include EVERY field returned by the API for each finding (findingId, name, description, riskLevel, riskType, confidence, status, codeLocations with filePath/lineStart/lineEnd, remediationCode, and any other fields returned).

Also create `.security-agent/.gitignore` containing `*` so the directory is gitignored.

Tell the user: "Full details written to `.security-agent/findings-{scan_id}.md`"

### Report file format

```markdown
# Security Scan Report — {scan_id}

**Scan type**: FULL | DIFF | THREAT_MODEL
**Title**: {title}
**Started**: {started_at}
**Total findings**: {count}

## Summary
| Severity | Count |
|----------|-------|
| CRITICAL | N |
| HIGH | N |
| MEDIUM | N |
| LOW | N |

## Findings

### 🟣 CRITICAL: {name}
- **ID**: {findingId}
- **Risk type**: {riskType}
- **Confidence**: {confidence}
- **Status**: {status}
- **Location**: `{filePath}:{lineStart}-{lineEnd}`

**Description**: {description}

**Remediation**:
{remediationCode}

(repeat for every finding)
```

### After presentation — offer remediation immediately

After showing the findings summary and writing the report file, **proactively offer to start fixing**. Ask once, then proceed through all findings without further prompts.

Say (single line):
> "I'll start applying remediation fixes top-down by severity (CRITICAL → HIGH → MEDIUM → LOW). Proceed?"

If the user says yes / proceed / go ahead:
1. Work top-down by severity (CRITICAL → HIGH → MEDIUM → LOW). Do NOT pause between tiers.
2. For each finding: read `remediationCode` and `codeLocations` (filePath + lineStart/lineEnd), apply the fix via the editor, and tell the user one line per fix: "Fixed {name} in `{filePath}:{lineStart}`."
3. When all findings are fixed, run a verification diff scan automatically: `start_diff_scan(path="<absolute-workspace-path>", base_ref="HEAD")` and tell the user: "All fixes applied. Running a quick diff scan to verify."

If the user wants to focus on specific findings instead, switch to that subset and apply only those.

If the user declines or says "later", say: "OK — full report is in `.security-agent/findings-{scan_id}.md`. Say 'fix the findings' anytime to start." Do not ask again this session.

---

## Rules

- `start_security_scan` returns immediately — use `get_scan_status` to poll
- Always call `setup_check` before `start_security_scan`
- **Whenever `start_security_scan` or `start_diff_scan` is called — no matter who or what triggered it (user request, hook, follow-up workflow) — immediately begin the polling loop in the same turn.** Default intervals: 5 min for full scan, 2 min for diff scan. Use `sleep 300` / `sleep 120` via Bash between `get_scan_status` checks. Continue until the status reaches a terminal state (COMPLETED, FAILED, STOPPED) or the user says "stop polling" / "check later". On COMPLETED → call `get_scan_findings` and present results per Findings Presentation. Do not stop after starting the scan; the scan kickoff is not a complete unit of work on its own.
- When `setup_check` returns existing agent spaces, show them to the user and ask which to use — do not auto-select
- Use latest scan by default if user doesn't specify a scan_id
- Be concise — format findings with severity icons and file locations, don't dump raw JSON
- Use git branch name and workspace name in scan title for traceability (e.g., `myapp-feature-auth`)
- Title must not contain spaces (use hyphens)

---

## Troubleshooting

- **"Not configured. Run setup first."** → Call `setup_check` then `setup`
- **"S3 access validation failed"** → Bucket not registered on agent space. Re-run scan (auto-registers) or run `setup` again
- **"Agent space no longer exists"** → Run `setup` again to create/pick a new one
- **Scan taking too long** → Check `get_scan_status` for errors or step progress
- **Code too large** → Reduce scope with a subdirectory path
- **Path outside allowed workspace root** → Add `"WORKSPACE_ROOT": "/path/to/project"` to the `env` block in `~/.kiro/powers/installed/aws-security-agent-kiro-power/mcp.json`, then restart Kiro. This restricts scans to that directory. If unset, any absolute path is accepted.

---

## Supported Regions

See [AWS Security Agent availability](https://docs.aws.amazon.com/securityagent/latest/userguide/resilience.html).

---

## License

Apache-2.0 — See [LICENSE](./LICENSE)

- **Privacy Policy**: https://aws.amazon.com/privacy/
- **Support**: aws-security-agent-feedback@amazon.com
