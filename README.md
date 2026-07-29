Project: Data Architecture with Generative AI

Overview
- A Text-to-SQL service that converts natural language questions into SQL queries using LangChain and AWS Bedrock (Amazon Nova models).
- Multi-connector framework supporting Athena, Redshift, RDS (PostgreSQL/MySQL), Snowflake, and Databricks.
- Notebook `mda_text_to_sql_langchain_bedrock.ipynb` demonstrates using LangChain + Bedrock to convert text to SQL and query data.
- Datasets: `s3_library_data.json` (NDJSON), `s3_cars_data.csv` (CSV).

Quick setup
1. Create a Python virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # includes Streamlit, hypothesis, and all prod deps
```

> **Note:** `requirements.txt` contains production dependencies including Streamlit (shipped in Docker).
> `requirements-dev.txt` pulls in `requirements.txt` plus hypothesis for property-based testing.

2. Configure AWS credentials (environment or AWS CLI).
3. Set authentication credentials for the Streamlit UI:
   ```bash
   export APP_USERNAME=your-username
   export APP_PASSWORD=your-password
   ```
4. Run `setup.sh` to perform optional staging actions (uploads are commented out).
5. Run production checks:
   - `make check` (syntax/compile gate)
   - `make test` (unit tests)
   - `make smoke` (local data smoke test)
   - `make prod-check` (all of the above)

Docker Desktop
- **Not required** for: running the Streamlit UI (`make ui`), tests, scripts, querying the deployed API, or CloudFormation operations.
- **Not required for CI/CD**: The `build-and-push-image` GitHub Actions workflow builds and pushes images remotely. Trigger with: `gh workflow run build-and-push-image`
- **Required only** for local image builds (`./scripts/push_ecr.sh`, `make deploy-all`, `./deploy-changeset.sh --auto`).
- Once the image is in ECR and ECS is running, Docker Desktop can be closed.

Architecture

```
Internet -> ALB:80   -> FastAPI (ECS private subnet) -> Bedrock/Athena via VPC endpoints
Internet -> ALB:8501 -> Streamlit (ECS private subnet) -> Bedrock/Athena via VPC endpoints
                                                       -> RDS Aurora (private subnet, port 3306)
                                                       -> Redshift Serverless (private subnet, port 5439)
```

Files
- `requirements.txt` — production dependencies (used by Docker, includes Streamlit)
- `requirements-dev.txt` — dev/test extras (hypothesis) plus all of `requirements.txt`
- `scripts/streamlit_app.py` — Streamlit chat UI (`make ui`)
- `scripts/sidebar_helpers.py` — pure functions for connector UI (testable without Streamlit)
- `scripts/serve.py` — FastAPI HTTP server (ECS entrypoint)
- `scripts/run_query.py` — CLI query tool (supports `--json-output`)
- `scripts/push_ecr.sh` — build + push Docker image + redeploy ECS services
- `scripts/teardown.sh` — destroy all AWS resources
- `scripts/setup-github-oidc.sh` — setup GitHub Actions CI/CD
- `scripts/setup.sh` — dependency installation helper
- `scripts/deploy-rds.sh` — deploy Aurora Serverless v2
- `scripts/load_rds_data.py` — load sample data into Aurora
- `scripts/configure_s3_notification.sh` — wire S3 event notifications to Lambda
- `scripts/detect_existing_resources.sh` — detect pre-existing AWS resources for reuse
- `scripts/get_vpc_params.sh` — query VPC parameters from CloudFormation
- `cloudformation-template-validated.yml` — main IaC template (VPC, S3, Glue, ECS, Lambda)
- `cloudformation-rds-aurora.yml` — Aurora Serverless v2 template
- `cloudformation-redshift-serverless.yml` — Redshift Serverless template
- `cloudformation-github-oidc.yml` — GitHub Actions OIDC role
- `config/connections/*.yaml.template` — data source connection templates
- `src/llm_sql/connectors/` — multi-connector framework (Athena, Redshift, RDS, Snowflake, Databricks)
- `POC/` — staging/dev files (sample data, smoke test, notebooks, old scripts)
- `.env.template` — environment variable template
- `deploy-changeset.sh` — one-command deployment script
- `DEPLOYMENT.md` — detailed deployment guide

S3 Buckets
The CloudFormation template creates an S3 data bucket with a globally unique name:
- `langchain-<account-id>-eu-north-1` — primary bucket (eu-north-1)

The bucket has versioning, AES-256 encryption, public access blocked, and a 30-day
lifecycle rule to expire Athena query results.

Deployment
- See [DEPLOYMENT.md](DEPLOYMENT.md) for CloudFormation stack creation and change set workflow.
- Deploy all: `./deploy-changeset.sh --auto`
- Deploy with databases: `./deploy-changeset.sh --auto --with-databases`
- Build image via GitHub (no Docker Desktop): `gh workflow run build-and-push-image`
- Tear down: `make teardown`
- CI/CD: Push to `main` triggers GitHub Actions (build + deploy)

CloudFormation Stacks

| Stack | Template | Purpose |
|-------|----------|---------|
| `cgs-ai-analyst-agent-project` | `cloudformation-template-validated.yml` | VPC, ECS, ALB, Lambda, Glue, S3, VPC endpoints |
| `github-actions-oidc` | `cloudformation-github-oidc.yml` | GitHub Actions OIDC role for CI/CD |
| `cgs-ai-rds-aurora` | `cloudformation-rds-aurora.yml` | Aurora Serverless v2 (MySQL), Secrets Manager credentials |
| `cgs-ai-redshift-serverless` | `cloudformation-redshift-serverless.yml` | Redshift Serverless, Secrets Manager credentials |

CloudFormation Outputs (consumed by the notebook)
| Output Key | Description |
|---|---|
| `VpcId` | Stack-managed VPC |
| `PrivateSubnetIds` | Private subnets (ECS tasks, RDS, Redshift) |
| `ServiceSecurityGroupId` | ECS security group (used by databases for ingress) |
| `ProjectfilesBucketName` | Primary S3 bucket |
| `LibraryDatabaseName` | Glue database for library data |
| `CarsDatabaseName` | Glue database for cars data |
| `LibraryCrawlerName` | Glue crawler for library data |
| `CarsCrawlerName` | Glue crawler for cars data |
| `AthenaWorkgroupName` | Athena workgroup for queries |
| `LoadBalancerUrl` | Public HTTP URL for the Text-to-SQL API |
| `StreamlitUrl` | Streamlit Chat UI URL |
| `EcrRepositoryUri` | ECR URI for container images |
| `EcsClusterName` | ECS cluster name |
| `EcsServiceName` | ECS service name |
| `CrawlerTriggerLambdaArn` | Lambda that auto-triggers Glue Crawlers |

Data & Testing
- Run `python run_smoke.py` to smoke-test data loading and normalization locally (no AWS calls).
- Normalized cars CSV: `s3_cars_data_normalized.csv` (produced by normalization).
- Unit tests: `PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v`

Production baseline
- Safer query execution defaults:
  - read-only and allowlist SQL validation
  - automatic `LIMIT` enforcement when missing
  - max question length guard
- Config hardening via typed settings:
  - `MAX_RESULT_ROWS`, `MAX_QUESTION_CHARS`, `LOG_LEVEL`
- Operational CLI behavior:
  - explicit non-zero exit codes on setup/catalog/query failures
  - optional JSON output (`--json-output`) for automation
- Container hardening:
  - non-root runtime user
  - writable config directory for runtime connector management
  - Python runtime safety defaults
  - reduced Docker build context via `.dockerignore`
- CI quality gate:
  - compile checks, unit tests, and smoke test on push/PR
- CI/CD pipelines:
  - `deploy.yml` — full pipeline (tests + build + deploy) on push to main
  - `build-image.yml` — manual-trigger build + deploy (skips tests, no Docker Desktop needed)

Production readiness gaps (not yet implemented)
- HTTPS/TLS (ALB is HTTP-only; need ACM certificate + HTTPS listener)
- WAF (no AWS WAF in front of ALB)
- Structured JSON logging (for CloudWatch Insights)
- Request tracing (X-Ray or correlation IDs)
- CloudWatch alarms (5xx rate, task health, Bedrock throttling)
- Auto-scaling policies (currently fixed at 1 task)
- Response caching (every question makes 3 LLM calls)
- Rate limiting (no per-user throttle)
- Query audit logging (no record of questions asked or SQL generated)
- Multi-environment (no dev/staging separation)
- Container vulnerability scanning (ECR scan not enabled)

Production-grade setup
1. Set required runtime variables:
   - `GLUE_DB_NAME` (single database) or `GLUE_DB_NAMES` (comma-separated list for multi-database)
   - `PROJECT_FILES_BUCKET`
   - `APP_USERNAME` and `APP_PASSWORD` (required for Streamlit UI authentication)
   - Optional hardening controls:
     - `MAX_RESULT_ROWS` (default `200`)
     - `MAX_QUESTION_CHARS` (default `1000`)
     - `LOG_LEVEL` (`DEBUG|INFO|WARNING|ERROR|CRITICAL`)
     - `ATHENA_WORKGROUP` (default `primary`; use `project-text-to-sql` when deployed via CloudFormation)
     - `ATHENA_USE_MANAGED_RESULTS` (`true` if workgroup uses managed query results)
     - `API_KEY` (optional HTTP API auth)
   - Bedrock tuning:
     - `BEDROCK_MODEL` (default `eu.amazon.nova-micro-v1:0`)
     - `BEDROCK_MAX_RETRIES` (default `4`)
     - `BEDROCK_RETRY_BASE_DELAY` (default `1.0` seconds)
2. Run the full production gate locally before deployment:
   - `make prod-check`
3. Run the query CLI in automation-friendly mode when needed:
   - `PYTHONPATH=src python scripts/run_query.py --question "..." --json-output`
4. Build and run with Docker for consistent execution (ECS needs `linux/amd64`; use `scripts/push_ecr.sh` on Apple Silicon):
   - `DESIRED_COUNT=1 ./scripts/push_ecr.sh`
   - Local run: `docker build --platform linux/amd64 -t data-architecture-ai .`
   - API: `GET /health`, `POST /query` with `{"question": "..."}`
5. Deploy to ECS Fargate (recommended production path):
   - `./deploy-changeset.sh --auto` (deploys stack + builds image + starts service)
   - Or step by step: `./deploy-changeset.sh` → execute change set → `DESIRED_COUNT=1 ./scripts/push_ecr.sh`
   - See [DEPLOYMENT.md](DEPLOYMENT.md) for full ECS workflow
6. Deploy Aurora Serverless v2 (optional, for RDS MySQL connector):
   - `./scripts/deploy-rds.sh --auto`
   - Paste the printed connection config into `config/connections/rds-mysql.yaml`
   - Load sample data: `PYTHONPATH=src python3 scripts/load_rds_data.py`
7. Keep CI required on pull requests:
   - Workflow: `.github/workflows/ci.yml`
   - Gates: compile, unit tests, smoke test

Notebook environment variable
Set `CFN_STACK_NAME` before launching Jupyter to avoid editing the placeholder in cell 4:
```bash
export CFN_STACK_NAME=cgs-ai-analyst-agent-project
```

Streamlit UI

Streamlit is included in `requirements.txt` (production deps). Use `make ui` (which installs dev deps into `.venv` automatically) or install manually first:

```bash
export GLUE_DB_NAME=project_library_db
export GLUE_DB_NAMES=project_library_db,project_cars_db
export PROJECT_FILES_BUCKET=langchain-<account-id>-eu-north-1
export ATHENA_WORKGROUP=project-text-to-sql
export ATHENA_USE_MANAGED_RESULTS=true
export APP_USERNAME=your-username
export APP_PASSWORD=your-password
make ui
```

Opens http://localhost:8501 — or set `API_URL` to use the deployed ECS API. See [DEPLOYMENT.md](DEPLOYMENT.md).

Authentication: The Streamlit UI requires `APP_USERNAME` and `APP_PASSWORD` environment variables. Without these, the login screen shows an error and blocks access.

Next steps
- Review `mda_text_to_sql_langchain_bedrock.ipynb` and set `CFN_STACK_NAME`.
- Run `deploy-changeset.sh` to create a change set and review before deploying to AWS.
