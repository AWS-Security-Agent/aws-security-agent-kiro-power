# AWS Security Agent — Kiro Power

AI-powered security scanning and penetration testing via Kiro.

> ⚠️ **Billing:** This Power invokes AWS Security Agent, which incurs charges on your AWS account per scan and penetration test. See [AWS Security Agent pricing](https://aws.amazon.com/security-agent/pricing/) before running.

## What it does

- Run full security code scans on your workspace to help find vulnerabilities
- Orchestrate penetration tests against live applications
- Retrieve findings with code locations, severity, and remediation guidance
- Access all AWS Security Agent API operations

## Prerequisites

- AWS account 
- AWS credentials configured (`aws configure` or environment variables)
- [uv](https://docs.astral.sh/uv/) installed (`brew install uv` or `pip install uv`)

## Installation

Add the power to Kiro from this repository URL.

## Supported Regions

See [AWS Security Agent availability](https://docs.aws.amazon.com/securityagent/latest/userguide/resilience.html).

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.
