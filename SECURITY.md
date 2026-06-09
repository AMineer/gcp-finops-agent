# Security Policy

## Supported Versions

gcp-finops-agent is currently in active development. Security updates will be applied to the `main` branch.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in gcp-finops-agent, please report it responsibly.

### Where to Report

Use GitHub's **[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)**
feature on this repository. This keeps the report confidential until a fix is released.

**DO NOT** open a public GitHub issue for security vulnerabilities.

### What to Include

When reporting a vulnerability, please include:

1. **Description** - A clear description of the vulnerability
2. **Impact** - What an attacker could achieve by exploiting it
3. **Reproduction Steps** - Detailed steps to reproduce the issue
4. **Proof of Concept** - Code, screenshots, or examples demonstrating the vulnerability
5. **Suggested Fix** - (Optional) If you have ideas for how to fix it

### What to Expect

- **Acknowledgment:** We will acknowledge receipt of your report within **48 hours**
- **Initial Assessment:** We will provide an initial assessment of the report within **5 business days**
- **Updates:** We will keep you informed of our progress as we investigate and address the issue
- **Fix Timeline:** We aim to resolve critical vulnerabilities within **30 days**
- **Credit:** We will credit you in the fix announcement unless you prefer to remain anonymous

## Security Features

gcp-finops-agent includes defenses against:

- **Prompt Injection via GCP Resource Metadata** - See [THREAT_MODEL.md](docs/THREAT_MODEL.md) for details
  - Sanitization of untrusted strings (control char stripping, length limits)
  - Structural fencing in prose contexts
  - Prompt-level instructions about data trust boundaries

## Out of Scope

The following are **not** considered vulnerabilities:

- **User-initiated jailbreaks** - Attempts to manipulate the agent via user prompts (handled by Claude's built-in safeguards)
- **Cosmetic issues** - Display quirks, markdown formatting oddities without security impact
- **Theoretical attacks** - Vulnerabilities that require compromising the user's machine, codebase, or GCP credentials
- **Dependency vulnerabilities** - Issues in third-party libraries (report those upstream, but let us know if it affects gcp-finops-agent)

## Security Best Practices for Users

### Access Control
- **Limit GCP Permissions:** Grant the agent's service account only necessary read permissions
  - `roles/bigquery.user` for billing export access
  - `roles/recommender.viewer` for recommendations
  - `roles/storage.objectViewer` for GCS inspection
- **Do NOT grant** write, admin, or IAM-modifying roles

### Monitoring
- **Audit Logs:** Enable Cloud Audit Logs to track agent queries
- **Billing Alerts:** Set up budget alerts to detect unexpected query volume
- **Review Recommendations:** Human review before acting on cost optimization suggestions

### Data Sensitivity
- **Billing Data:** GCP billing exports may contain sensitive cost information
  - Ensure agent output is shared only with authorized users
  - Consider project-level filtering if multi-tenant
- **Resource Names:** If your resource names contain sensitive information, review before exposing to the agent

### Deployment Security
- **Secret Manager:** Store sensitive config (API keys, project IDs) in GCP Secret Manager
- **Least Privilege:** Run the agent with minimal IAM permissions
- **Network Isolation:** Deploy in VPC with appropriate firewall rules if self-hosting

## Secure Development

### For Contributors

- **Never commit secrets** - Use Secret Manager, environment variables, or `.env` (gitignored)
- **Code review required** - All PRs require approval before merge
- **Dependency updates** - Keep dependencies current (Dependabot enabled)
- **Testing** - Security-relevant changes must include tests (see `tests/evals/scenarios/test_injection_resilience.py`)

### Security Testing

Run security-focused tests:

```bash
# Injection resilience evals
pytest tests/evals/scenarios/test_injection_resilience.py -v

# Sanitization unit tests
pytest tests/test_sanitize.py -v
```

## References

- [Threat Model Documentation](docs/THREAT_MODEL.md) - Detailed security architecture
- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [Anthropic Safety Best Practices](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails)

---

**Last Updated:** 2026-06-09
