# Security Policy

## 🔐 Security Overview

This document outlines our security practices and incident response procedures for the openkeyword project.

## 🚨 Reporting Security Vulnerabilities

**DO NOT** open public GitHub issues for security vulnerabilities.

Instead, please email security concerns to: **federicodeponte@gmail.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested remediation (if any)

We will respond within 48 hours and provide updates every 72 hours until resolution.

## 🛡️ Security Measures Implemented

### Code Security
- ✅ **Input Validation**: Strict validation on all API endpoints
- ✅ **CORS Protection**: Specific domain allowlist instead of wildcards
- ✅ **API Security**: Rate limiting and authentication
- ✅ **Data Sanitization**: All external data properly validated

### Infrastructure Security
- ✅ **Secret Management**: All API keys in environment variables
- ✅ **HTTPS Only**: All production endpoints use TLS
- ✅ **Modal Security**: Secure serverless deployment

### Development Security
- ✅ **Pre-commit Hooks**: Automated security scanning before commits
- ✅ **GitHub Security**: Dependabot alerts, secret scanning, CodeQL analysis
- ✅ **Dependency Scanning**: Regular vulnerability checks with Safety
- ✅ **Code Analysis**: Semgrep and Bandit for static analysis

## 🔧 Security Tools & Automation

### Pre-commit Hooks (`.pre-commit-config.yaml`)
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

### Continuous Security Scanning
- **GitHub Actions**: Weekly automated security scans
- **Dependabot**: Automatic dependency vulnerability alerts
- **CodeQL**: Advanced semantic code analysis
- **Secret Scanning**: Detects exposed credentials in commits

### Manual Security Testing
```bash
# Run full security audit
semgrep --config=auto .
bandit -r . -x tests/
safety check
pip-audit
```

## 🚦 Security Incident Response

### Immediate Response (< 2 hours)
1. **Assess Impact**: Determine scope and severity
2. **Contain Threat**: Disable affected services if needed
3. **Notify Team**: Alert all stakeholders
4. **Document Timeline**: Start incident log

### Investigation (< 24 hours)
1. **Root Cause Analysis**: Identify vulnerability source
2. **Data Assessment**: Check for data exposure
3. **System Integrity**: Verify no unauthorized access

### Resolution (< 72 hours)
1. **Patch Deployment**: Fix vulnerability
2. **Security Testing**: Verify fix effectiveness
3. **Monitoring Setup**: Enhanced monitoring for recurrence

### Post-Incident (< 1 week)
1. **Lessons Learned**: Document improvements
2. **Process Updates**: Enhance security measures
3. **Team Training**: Share knowledge gained

## 🛠️ Secure Development Guidelines

### Code Review Checklist
- [ ] No hardcoded secrets or API keys
- [ ] All user input properly validated
- [ ] CORS policies restrict to necessary domains
- [ ] Authentication checks on protected endpoints
- [ ] Error messages don't leak sensitive information
- [ ] External API calls properly secured

### Environment Variables
```bash
# Required for production
GEMINI_API_KEY=your_key_here           # Never commit this!
DATAFORSEO_LOGIN=your_login            # Never commit this!
DATAFORSEO_PASSWORD=your_password      # Never commit this!
SERANKING_API_KEY=your_key             # Never commit this!

# Use .env.example for templates
# Use .env.local for development (gitignored)
# Use Modal secrets for deployment
```

### Dependency Management
```bash
# Regular security updates
pip install --upgrade pip
pip-review --local --auto

# Check for vulnerabilities
safety check
pip-audit

# Update pre-commit hooks
pre-commit autoupdate
```

## 📋 Security Monitoring

### Automated Alerts
- **GitHub Security Alerts**: Vulnerability notifications
- **Dependabot PRs**: Automatic security updates
- **Failed Security Scans**: CI/CD pipeline failures

### Regular Reviews
- **Weekly**: Dependency vulnerability scanning
- **Monthly**: Access permission audits
- **Quarterly**: Comprehensive security assessment

## 🔗 Additional Resources

- [OWASP API Security](https://owasp.org/API-Security/)
- [Python Security Documentation](https://docs.python.org/3/library/security.html)
- [Semgrep Rules](https://semgrep.dev/r)
- [GitHub Security Features](https://docs.github.com/en/code-security)

## 📞 Emergency Contacts

- **Primary**: Federico De Ponte - federicodeponte@gmail.com
- **GitHub**: @federicodeponte

---

**Last Updated**: December 2024
**Next Review**: March 2025