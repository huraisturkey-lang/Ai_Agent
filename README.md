# Data Architecture with Generative AI (Text-to-SQL)

Ask a question in plain English, get back an answer from your data. This service turns
natural-language questions into SQL using **LangChain** + **AWS Bedrock** (Amazon Nova),
runs the SQL safely (read-only), and returns the result. It ships as an HTTP API
(FastAPI) and a chat UI (Streamlit), and runs on AWS ECS Fargate.

Supported data sources: **Athena, Redshift, RDS (PostgreSQL/MySQL), Snowflake, Databricks.**

---

## New here? Read this first

There are **two completely separate ways** this project gets deployed. People confuse
them, so here is the plain-English version:

| Path | What it does | Needs Docker on your laptop? |
|------|--------------|------------------------------|
| **A. Local script** — `./deploy-changeset.sh --auto` | Does *everything* from your machine: creates AWS infra, builds the Docker image **locally**, pushes it, starts ECS. | **Yes** |
| **B. GitHub Actions** — `git push origin main` | GitHub's servers build the image and deploy. Triggered automatically on every push to `main`. | **No** |

Important: these two do **not** call each other. The local script does *not* trigger the
GitHub workflow. The GitHub workflow does *not* run the local script. Pick one path.

The one thing they share: before Path B can deploy, the AWS **infrastructure must already
exist** (ECR repo + ECS service), because the GitHub workflow only *builds and updates* —
it does not create the base stack. So a common first-time flow is "create infra once, then
let GitHub handle every deploy after that."

---

## Prerequisites

Install these before you start:

1. **Python 3.11** — check with `python3 --version`.
2. **AWS account + AWS CLI** — run `aws configure` and set region `eu-north-1`.
   Verify with `aws sts get-caller-identity`.
3. **Amazon Bedrock access** — enable the Amazon Nova models in the Bedrock console
   (region `eu-north-1`).
4. **Docker Desktop** — *only if you use Path A (local build)*. Skip it for Path B.
5. **(Optional) GitHub CLI `gh`** — handy for setting the deploy secret: `brew install gh`.

---

## Part 1 — Run it locally (no AWS deploy)

Do this first to confirm everything works on your machine.

### Step 1: Get the code and create a virtual environment
```bash
git clone https://github.com/huraisturkey-lang/Ai_Agent.git
cd Ai_Agent
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install dependencies
```bash
pip install -r requirements-dev.txt   # prod deps + Streamlit + test tools
```
> `requirements.txt` = production deps (used by Docker). `requirements-dev.txt` includes
> everything in it, plus `hypothesis` for testing. For local work, use the `-dev` one.

### Step 3: Run the quality gate (no AWS calls)
```bash
make prod-check
```
This runs three things in order:
- `make check` — compiles all Python (catches syntax errors)
- `make test` — unit tests
- `make smoke` — loads the sample data locally (`POC/run_smoke.py`)

If all three pass, your environment is good.

### Step 4: Launch the chat UI locally
Set the required variables, then start Streamlit:
```bash
export APP_USERNAME=your-username          # login for the UI
export APP_PASSWORD=your-password
export GLUE_DB_NAME=project_library_db
export GLUE_DB_NAMES=project_library_db,project_cars_db
export PROJECT_FILES_BUCKET=langchain-<your-account-id>-eu-north-1
export ATHENA_WORKGROUP=project-text-to-sql
export ATHENA_USE_MANAGED_RESULTS=true
make ui
```
Open **http://localhost:8501** and log in with the username/password you set.

> Querying real data needs the AWS infrastructure from Part 2. The UI runs locally either
> way, but answers come from AWS (Athena/Bedrock).

Tip: copy `.env.template` to `.env` and fill it in instead of exporting variables each time:
```bash
cp .env.template .env   # then edit .env
```

---

## Part 2 — Deploy to AWS

### Choose your path

- **Path A** if you have Docker and want one command to do everything.
- **Path B** if you don't want Docker locally and prefer deploys to happen on `git push`.

Both deploy into AWS account region `eu-north-1`.

---

### Path A — One command, builds locally (needs Docker)

Make sure Docker Desktop is **running**, then:
```bash
./deploy-changeset.sh --auto
```
This single command, in order:
1. Creates/updates the main CloudFormation stack (VPC, ECS, ALB, Glue, S3, Lambda).
2. Builds the Docker image **on your machine** (`linux/amd64`) and pushes it to ECR.
3. Scales up the ECS services (API + Streamlit).
4. Runs the Glue crawlers (registers the data tables).
5. Configures the S3 → Lambda notification.
6. Sets up the GitHub Actions OIDC role + secret (so Path B works later).

When it finishes it prints your **API URL** and **Streamlit URL**.

Add the optional databases (Aurora + Redshift) at the same time, or later:
```bash
./deploy-changeset.sh --auto --with-databases
```
> Note the flag is `--with-databases` (not `--autodatabases`). Running the script a second
> time is safe — the main stack updates in place, and the database stacks only deploy if
> they don't already exist.

---

### Path B — Deploy on push, builds on GitHub (no Docker)

This is a two-time setup, then it's automatic forever.

**B1. Create the AWS infrastructure once (no Docker needed).**
The GitHub workflow can only build+update; it can't create the base stack. Create it in
review mode (this only makes a change set — no image build):
```bash
./deploy-changeset.sh                 # prints an "execute-change-set" command
# run the execute command it printed, then:
aws cloudformation wait stack-create-complete \
  --stack-name cgs-ai-analyst-agent-project --region eu-north-1
```
After this, the ECR repo and ECS services exist (ECS starts at 0 tasks — no image yet,
which is expected).

**B2. Wire up GitHub → AWS auth (once).**
The deploy workflow logs into AWS using an OIDC role and a repo secret.
```bash
./scripts/setup-github-oidc.sh
```
This creates the IAM role and (if `gh` is installed and logged in) sets the repo secret
`AWS_DEPLOY_ROLE_ARN`. If `gh` isn't available, the script prints the role ARN — add it
manually at **Repo → Settings → Secrets and variables → Actions → New repository secret**:
- Name: `AWS_DEPLOY_ROLE_ARN`
- Value: the printed `arn:aws:iam::<account>:role/github-actions-deploy-role`

**B3. Deploy by pushing.**
```bash
git push origin main
```
On every push to `main`, GitHub Actions (`.github/workflows/deploy.yml`):
runs the test gate → builds the image on GitHub's servers → pushes to ECR → redeploys ECS →
prints the URLs. Watch it under the repo's **Actions** tab.

> First time only: your Git login must have **write access** to the repo. If `git push`
> returns `403 / permission denied`, you're authenticated as the wrong GitHub account —
> push from a plain terminal with a Personal Access Token for an account that owns the repo.

---

## Part 3 — Optional databases

The RDS Aurora and Redshift stacks are plain CloudFormation (no Docker). Deploy them
directly whenever you want:
```bash
aws cloudformation deploy --template-file cloudformation-rds-aurora.yml \
  --stack-name cgs-ai-rds-aurora --capabilities CAPABILITY_NAMED_IAM \
  --region eu-north-1 --no-fail-on-empty-changeset

aws cloudformation deploy --template-file cloudformation-redshift-serverless.yml \
  --stack-name cgs-ai-redshift-serverless --capabilities CAPABILITY_NAMED_IAM \
  --region eu-north-1 --no-fail-on-empty-changeset
```
Then load sample data into Aurora and point the connector at it:
```bash
PYTHONPATH=src python3 scripts/load_rds_data.py
# paste the printed connection details into config/connections/rds-mysql.yaml
```

Each connector is driven by a YAML file in `config/connections/`. Copy the matching
`*.yaml.template`, fill in the values, and the registry auto-discovers it on startup.
Database passwords are stored in AWS Secrets Manager, not in the YAML (see `.env.template`
for the expected secret names).

---

## Using the API

```bash
# health check
curl <API_URL>/health

# ask a question
curl -X POST <API_URL>/query \
  -H 'Content-Type: application/json' \
  -d '{"question": "How many books are there?"}'
```

CLI version (for automation):
```bash
PYTHONPATH=src python scripts/run_query.py --question "How many books?" --json-output
```

---

## Tear down

Remove all AWS resources when you're done:
```bash
make teardown
```

---

## Troubleshooting

- **`git push` → `403 denied to <account>`** — you're logged into GitHub as the wrong
  account. Push from macOS Terminal.app with a Personal Access Token for an account that
  owns the repo (editor terminals can inject a cached login).
- **`fatal: 'origin' does not appear to be a git repository`** — the remote is missing.
  Re-add it: `git remote add origin https://github.com/huraisturkey-lang/Ai_Agent.git`.
- **GitHub deploy fails at "Configure AWS credentials"** — the `AWS_DEPLOY_ROLE_ARN` secret
  is missing or the OIDC role doesn't exist. Do step **B2**.
- **GitHub deploy fails on `ecs update-service` / ECR not found** — the base stack isn't
  created yet. Do step **B1** first.
- **Stack stuck in `REVIEW_IN_PROGRESS`** — a change set was created but never executed.
  Delete the empty stack and recreate: `aws cloudformation delete-stack --stack-name
  cgs-ai-analyst-agent-project --region eu-north-1`, then redo Path A or B1.
- **`make smoke` import errors (`No module named boto3`)** — dependencies aren't installed
  in the active environment. Activate the venv and `pip install -r requirements-dev.txt`.
- **Docker build fails on Apple Silicon** — ECS needs `linux/amd64`. Use the provided
  scripts (`./scripts/push_ecr.sh`) which cross-build automatically.

---

## How it fits together

```
Internet -> ALB:80   -> FastAPI  (ECS private subnet) -> Bedrock / Athena via VPC endpoints
Internet -> ALB:8501 -> Streamlit (ECS private subnet) -> Bedrock / Athena via VPC endpoints
                                                        -> RDS Aurora       (private subnet, 3306)
                                                        -> Redshift Serverless (private subnet, 5439)
```

### CloudFormation stacks

| Stack | Template | Purpose |
|-------|----------|---------|
| `cgs-ai-analyst-agent-project` | `cloudformation-template-validated.yml` | VPC, ECS, ALB, Lambda, Glue, S3, VPC endpoints |
| `github-actions-oidc` | `cloudformation-github-oidc.yml` | GitHub Actions OIDC role for CI/CD |
| `cgs-ai-rds-aurora` | `cloudformation-rds-aurora.yml` | Aurora Serverless v2 (MySQL) + Secrets Manager creds |
| `cgs-ai-redshift-serverless` | `cloudformation-redshift-serverless.yml` | Redshift Serverless + Secrets Manager creds |

### GitHub Actions workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `.github/workflows/ci.yml` | every push / PR | compile + unit tests + smoke (quality gate) |
| `.github/workflows/deploy.yml` | push to `main` | tests → build image on GitHub → push to ECR → redeploy ECS |
| `.github/workflows/build-image.yml` | manual (`workflow_dispatch`) | build + deploy, skips tests |

### Key files

| Path | Purpose |
|------|---------|
| `src/llm_sql/` | application package (API, core text-to-SQL, config, connectors) |
| `scripts/serve.py` | FastAPI server (ECS entrypoint) |
| `scripts/streamlit_app.py` | Streamlit chat UI (`make ui`) |
| `scripts/run_query.py` | CLI query tool (`--json-output`) |
| `scripts/push_ecr.sh` | local build + push image + redeploy ECS |
| `scripts/setup-github-oidc.sh` | set up GitHub Actions CI/CD auth |
| `scripts/load_rds_data.py` | load sample data into Aurora |
| `deploy-changeset.sh` | one-command local deploy (`--auto`, `--with-databases`) |
| `config/connections/*.yaml` | one file per data source (copy from `*.template`) |
| `POC/` | sample data, smoke test, notebooks |
| `.env.template` | environment variable template |
| `DEPLOYMENT.md` | detailed deployment guide |

---

## Configuration reference

Set these as environment variables or in `.env` (copy from `.env.template`):

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `APP_USERNAME` / `APP_PASSWORD` | Yes (UI) | — | Streamlit login; UI blocks without them |
| `GLUE_DB_NAME` / `GLUE_DB_NAMES` | Yes | `project_library_db` | single, or comma-separated list |
| `PROJECT_FILES_BUCKET` | Yes | — | `langchain-<account-id>-eu-north-1` |
| `ATHENA_WORKGROUP` | — | `primary` | use `project-text-to-sql` when deployed |
| `ATHENA_USE_MANAGED_RESULTS` | — | — | `true` if workgroup uses managed results |
| `AWS_REGION` | — | `eu-north-1` | |
| `BEDROCK_MODEL` | — | `eu.amazon.nova-micro-v1:0` | |
| `BEDROCK_MAX_RETRIES` | — | `4` | |
| `BEDROCK_RETRY_BASE_DELAY` | — | `1.0` | seconds |
| `MAX_RESULT_ROWS` | — | `200` | automatic `LIMIT` cap |
| `MAX_QUESTION_CHARS` | — | `1000` | question length guard |
| `PORT` | — | `8080` | HTTP API port |
| `API_KEY` | — | — | optional HTTP API auth |
| `LOG_LEVEL` | — | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` |
| `API_URL` | — | — | route Streamlit through the deployed API |
| `SECRETS_MANAGER_SECRET` | — | — | optional Secrets Manager integration |

Safety defaults built in: read-only + allowlist SQL validation, automatic `LIMIT`
enforcement, max question length, non-root container user.

---

## Not yet implemented (production hardening gaps)

HTTPS/TLS (ALB is HTTP-only), AWS WAF, structured JSON logging, request tracing,
CloudWatch alarms, auto-scaling (fixed at 1 task), response caching, rate limiting,
query audit logging, dev/staging separation, ECR vulnerability scanning.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the detailed deployment reference.
