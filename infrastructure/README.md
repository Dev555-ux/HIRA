# infrastructure/

**Purpose**: Everything that defines how and where HIRA runs — hosting, environments, secrets management, scaling, and CI/CD pipeline definitions.

**Will eventually contain**:
- Infrastructure-as-code (e.g., Terraform, Docker Compose files)
- Environment configuration (staging vs. production)
- CI/CD pipeline definitions
- Secrets/credentials management strategy (not actual secrets)
- Monitoring/alerting setup (uptime, error tracking)

**Why it exists**: As a multi-tenant SaaS handling live customer conversations and bookings, uptime and deployability matter early. Keeping infra config separate from application code makes environments reproducible and changes auditable.
