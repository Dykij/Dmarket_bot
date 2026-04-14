# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Which versions are eligible for receiving such patches depends on the CVSS v3.0 Rating:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via GitHub Security Advisories:

1. Go to the [Security tab](https://github.com/Dykij/DMarket-Telegram-Bot/security/advisories)
2. Click "Report a vulnerability"
3. Fill out the form with as much detail as possible

### What to Include

Please include the following information in your report:

- Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity
  - Critical: Within 7 days
  - High: Within 30 days
  - Medium: Within 90 days
  - Low: Best effort

## Security Best Practices

### For Users

1. **API Keys**
   - Never commit API keys to the repository
   - Use environment variables or encrypted storage
   - Rotate keys regularly
   - Use separate keys for different environments

2. **Environment Configuration**
   - Use `.env` files (never commit them)
   - Set appropriate file permissions (chmod 600)
   - Use different credentials for production/staging/development

3. **Bot Token**
   - Keep your Telegram bot token secret
   - Regenerate token if compromised
   - Use webhook mode with HTTPS in production

4. **Dependencies**
   - Keep dependencies up to date
   - Review security advisories regularly
   - Use `pip audit` or similar tools

### For Developers

1. **Code Review**
   - All PRs must be reviewed
   - Security-sensitive changes require additional review
   - Use automated security scanning

2. **Testing**
   - Include security test cases
   - Test authentication and authorization
   - Validate all user inputs

3. **Secrets Management**
   - Use `detect-secrets` pre-commit hook
   - Never hardcode credentials
   - Use encryption for sensitive data

4. **Rate Limiting**
   - Implement rate limiting for all external APIs
   - Protect against DDoS attacks
   - Monitor unusual activity

## Security Features

This project includes:

- ✅ API key encryption
- ✅ Rate limiting (API and user-level)
- ✅ Input validation (Pydantic schemas)
- ✅ Audit logging
- ✅ Secrets detection (pre-commit hooks)
- ✅ DRY_RUN mode for testing
- ✅ Circuit breaker for API protection
- ✅ Sentry error monitoring

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine affected versions
2. Audit code to find similar problems
3. Prepare fixes for all supported versions
4. Release patches as soon as possible

## Comments on This Policy

If you have suggestions on how this process could be improved, please submit a pull request or open an issue.

## Hall of Fame

We'd like to thank the following people for responsibly disclosing security issues:

<!-- Add contributors here -->

---

**Last Updated**: December 28, 2025


---
🦅 *DMarket Quantitative engine | v7.0 | 2026*

----- 
🦅 *DMarket Quantitative Engine | v7.0 | 2026*