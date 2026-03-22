# Security Rules

- NEVER hardcode API keys, tokens, passwords, or secrets in any file
- NEVER commit .env files to git
- Always use environment variables for sensitive configuration
- Redact any secrets from log output or error messages
- Review output before sharing - remove sensitive data
- Flag any route that accepts user input without validation
- This project has had API key leaks before - extra vigilance required
