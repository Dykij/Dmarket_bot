---
name: security-audit
description: Comprehensive security audit for trading bots. Use before deployment, after major changes, or when reviewing code that handles API keys, funds, or user data. Covers secret detection, injection, auth, business logic flaws.
---

# Security Audit — Trading Bot Focus

## When to Use
- Before deploying to production (pre-deploy-audit complements this)
- After adding new API integrations
- When reviewing code that touches: API keys, database, trade execution, balance
- On a schedule (weekly heartbeat check)

## Audit Dimensions

### 1. Secret Exposure
- [ ] No hardcoded API keys, secrets, or passwords in source
- [ ] `.env` not committed (check git history)
- [ ] No secrets in logs (mask sensitive fields)
- [ ] No secrets in error messages returned to user
- [ ] Encryption key not hardcoded (uses env var)

### 2. Injection Vulnerabilities
- [ ] SQL queries use parameterized queries (no f-strings in SQL)
- [ ] User input sanitized before API calls
- [ ] No shell injection via `subprocess` with user input
- [ ] Path traversal prevented in file operations

### 3. Authentication & Authorization
- [ ] API signatures generated correctly (HMAC-SHA256)
- [ ] Timestamp replay protection (±300s window)
- [ ] Rate limiting respected (DMarket: 10 req/s)
- [ ] No credential reuse across environments

### 4. Financial Safety
- [ ] Balance check before EVERY trade execution
- [ ] Drawdown freeze enforced (balance < 85% peak → stop buying)
- [ ] Max position size enforced (no single trade > 10% effective balance)
- [ ] Negative profit prevention (net_margin > min_spread required)
- [ ] Double-spend prevention (idempotency keys on orders)

### 5. Data Protection
- [ ] SQLite database encrypted at rest (if containing sensitive data)
- [ ] No PII in logs
- [ ] API responses not cached to disk unencrypted
- [ ] Backup files not containing secrets

### 6. Network Security
- [ ] All API calls use HTTPS
- [ ] Certificate verification enabled (no `verify=False`)
- [ ] Timeouts on all network calls (no infinite waits)
- [ ] Connection pooling with bounds

### 7. Business Logic
- [ ] Race condition check: two tasks executing same trade simultaneously
- [ ] Idempotency: duplicate API calls don't create duplicate orders
- [ ] State machine integrity: can't skip validation steps
- [ ] Circuit breaker: consecutive failures halt trading

## Scoring
- **0-2 issues**: PASS — deploy with monitoring
- **3-5 issues**: WARN — fix critical before deploy
- **6+ issues**: BLOCK — do not deploy

## Output Format
```markdown
## Security Audit — {date}

### Critical (must fix)
- [finding]

### Warning (should fix)
- [finding]

### Info (nice to fix)
- [finding]

### Verdict: PASS / WARN / BLOCK
```

## Integration with Other Skills
- **pre-deploy-audit**: This checks CODE security; that checks DEPLOYMENT readiness
- **code-reviewer**: This focuses on vulnerabilities; that focuses on correctness/style
- **git-gate**: Run this as part of Phase 2 (FULL) validation
