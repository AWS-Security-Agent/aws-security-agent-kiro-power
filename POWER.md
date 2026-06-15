---
name: "aws-security-agent"
displayName: "AWS Security Agent"
description: "AI-powered security scanning and penetration testing. Run full repository code scans to help find vulnerabilities, or pentest live applications."
keywords: ["is my code secure", "code security", "security scan", "security vulnerabilities", "vulnerabilities", "pentest", "penetration test", "test my app", "attack surface", "code review", "sast", "owasp", "cve", "audit", "compliance", "production ready", "security review"]
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
- **Pentest scenarios** — testing live apps, attack surface
- **Ambiguous code-quality requests** ("review my code") — proactively offer a security check

---

## Tools Available

| Tool | Purpose |
|------|---------|
| `setup_check` | Verify prerequisites (AWS creds, agent space, service role) |
| `setup` | Provision or reuse: agent space, IAM role |
| `start_security_scan` | Zip code → upload → start scan. Returns immediately with scan_id |
| `get_scan_status` | Check scan progress (step, elapsed time) |
| `get_scan_findings` | Get findings (works during scan for partial results or after completion) |
| `list_scans` | List recent scans |
| `stop_scan` | Cancel a running scan |
| `call_api` | Call any SecurityAgent API operation directly |
| `get_api_guide` | List all available API operations |

---

## Intent Detection

### → Security Scan
**Trigger words**: scan, security, vulnerability, code review, check security, find vulnerabilities, security issues, code scan

**Action**: Run the Security Scan workflow below.

### → Penetration Test
**Trigger words**: pentest, penetration test, test my app, attack surface, dynamic scan

**Action**: Run the Pentest workflow below.

### → Check Status
**Trigger words**: scan status, how's the scan, progress, is it done, check scan

**Action**: Call `get_scan_status` and report.

### → View Findings
**Trigger words**: findings, vulnerabilities, results, what did it find, security issues, show findings

**Action**: Call `get_scan_findings` and present formatted results.

### → Direct API
**Trigger words**: API operations, advanced, target domain, integrations, available operations

**Action**: Call `get_api_guide` and present options. Once user selects an operation, call `call_api` with the operation and params.

---

## Workflow: First-Time Setup

1. Call `setup_check`
2. If not ready and `existing_agent_spaces` is returned:
   - Show the list to the user: "Found these agent spaces: [names and IDs]. Would you like to use one of these, or should I create a new one?"
   - Wait for the user's response
   - If user selects an existing space: call `setup(agent_space_id="as-xxxxx")` directly — the server will check and register the role automatically.
   - If user wants a new space: Ask "Do you have an existing IAM service role, or should I create one?" Then call `setup(name="my-scans")` or `setup(name="my-scans", service_role_arn="arn:...")`
4. Confirm: "Setup complete. You can now run security scans."

---

## Workflow: Security Code Scan

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

## Workflow: Penetration Test (via call_api)

1. `setup_check` → `setup` (one-time)
2. `call_api("CreateTargetDomain", {agentSpaceId, targetDomainName, verificationMethod: "HTTP_ROUTE"})`
3. `call_api("VerifyTargetDomain", {agentSpaceId, targetDomainId})`
4. `call_api("CreatePentest", {agentSpaceId, title, assets: {endpoints: [{uri: "..."}]}, serviceRole: "arn:..."})`
5. `call_api("StartPentestJob", {agentSpaceId, pentestId})`
6. Poll with `call_api("BatchGetPentestJobs", {agentSpaceId, pentestJobIds: [...]})` until COMPLETED
7. `call_api("ListFindings", {agentSpaceId, pentestJobId})` → results

Pentests run 1-24 hours depending on scope.

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

### After presentation

Ask:
- "Would you like to focus on the critical/high findings first?"
- "Should I explain any of these in more detail?"

---

## Rules

- `start_security_scan` returns immediately — use `get_scan_status` to poll
- Always call `setup_check` before `start_security_scan`
- After a code scan starts, default to polling automatically every 5 minutes. Stop polling if the user says "stop polling" or "check later".
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
- **Scan taking too long** → Full scans take 30-60 min. Check `get_scan_status` for errors
- **Code too large** → Reduce scope with a subdirectory path

---

## Supported Regions

See [AWS Security Agent availability](https://docs.aws.amazon.com/securityagent/latest/userguide/resilience.html).

---

## License

Apache-2.0 — See [LICENSE](./LICENSE)

- **Privacy Policy**: https://aws.amazon.com/privacy/
- **Support**: aws-security-agent-feedback@amazon.com
