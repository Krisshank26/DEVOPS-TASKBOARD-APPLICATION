# TaskBoard — Full-Stack DevOps & DevSecOps Capstone

TaskBoard is a SaaS-style task-management application used to demonstrate how a full-stack application can move from local development to a containerized, tested, scanned, and Kubernetes-managed deployment on AWS.

The project combines a React frontend, a Python FastAPI backend, PostgreSQL, Docker, GitHub Container Registry (GHCR), GitHub Actions, Terraform, AWS EKS, Kubernetes, and Helm. The Helm chart is designed around a blue-green deployment model and includes Horizontal Pod Autoscaler (HPA) settings. Prometheus and Grafana are the planned observability layer.

> **Implementation-status note:** This README documents the architecture and the configuration shared for this project. The workflow currently includes automated tests/builds, Helm and Terraform validation, Trivy container-image scans, GHCR publishing, Terraform provisioning, EKS access, and Helm deployment. A successful live AWS deployment still depends on the Terraform resources, IAM/OIDC permissions, remote state, image access, and Kubernetes templates being correctly configured. Dedicated source-code SAST, standalone dependency/secret scanning, runtime threat detection, and a complete Prometheus/Grafana installation should not be considered active unless their additional tools and configuration are present. 

---

## Contents

1. [Project goals](#1-project-goals)
2. [Architecture at a glance](#2-architecture-at-a-glance)
3. [Technology stack](#3-technology-stack)
4. [Application components](#4-application-components)
5. [Repository structure](#5-repository-structure)
6. [Run TaskBoard locally](#6-run-taskboard-locally)
7. [Docker images](#7-docker-images)
8. [GitHub Container Registry](#8-github-container-registry)
9. [GitHub Actions CI/CD pipeline](#9-github-actions-cicd-pipeline)
10. [Terraform and AWS infrastructure](#10-terraform-and-aws-infrastructure)
11. [Kubernetes and EKS](#11-kubernetes-and-eks)
12. [Helm application management](#12-helm-application-management)
13. [Blue-green deployment strategy](#13-blue-green-deployment-strategy)
14. [PostgreSQL, migrations, and secrets](#14-postgresql-migrations-and-secrets)
15. [Horizontal Pod Autoscaler](#15-horizontal-pod-autoscaler-hpa)
16. [Ingress and external access](#16-ingress-and-external-access)
17. [Monitoring and observability](#17-monitoring-and-observability)
18. [DevSecOps and security controls](#18-devsecops-and-security-controls)
19. [GitHub and AWS configuration checklist](#19-github-and-aws-configuration-checklist)
20. [Operational commands](#20-operational-commands)
21. [Troubleshooting](#21-troubleshooting)
22. [Important production considerations](#22-important-production-considerations)
23. [Project demonstration checklist](#23-project-demonstration-checklist)
24. [DevSecOps concepts learned](#24-devsecops-concepts-learned)
25. [Official documentation](#25-official-documentation)

---

## 1. Project goals

The goal is not merely to run a frontend and backend. It is to demonstrate an engineering delivery path in which code is tested, packaged, scanned, versioned, published, and deployed through repeatable automation.

The project demonstrates how to:

- Build a full-stack web application with a persistent database.
- Run the application locally with Docker Compose.
- Package the frontend and backend as separate Docker images.
- Publish immutable, commit-tagged images to GHCR.
- Stop delivery when automated tests, builds, or configured container-security checks fail.
- Describe AWS infrastructure as code with Terraform.
- Run containerized workloads on Kubernetes through Amazon EKS.
- Manage Kubernetes manifests and application releases with Helm.
- stage a new application version in the inactive blue/green environment before changing traffic.
- Scale eligible Kubernetes workloads horizontally with HPA.
- Add metrics, dashboards, alerts, and application-level telemetry as the observability stack is completed.
- Apply security controls throughout the software delivery lifecycle rather than only after deployment.

## 2. Architecture at a glance

### 2.1 Delivery pipeline

```mermaid
flowchart TD
    DEV[Developer changes code] --> GIT[Git commit and push to GitHub]
    GIT --> TEST[GitHub Actions: tests and validation]
    TEST --> BUILD[Build frontend and backend images]
    BUILD --> SCAN[Trivy container-image scans]
    SCAN -->|Checks pass| GHCR[Push SHA-tagged images to GHCR]
    GHCR --> TF[Terraform plan and apply]
    TF --> AWS[AWS VPC, EKS, and worker infrastructure]
    AWS --> KCFG[Configure kubectl using Terraform cluster output]
    KCFG --> HELM[Helm blue-green release]
    HELM --> VERIFY[Wait for rollout and inspect resources]
```

The current GitHub Actions workflow has three main jobs:

1. **`test`** — backend tests, frontend dependency installation/build, Helm lint, and Terraform formatting/validation.
2. **`build-scan-push`** — build backend and frontend images, scan them with Trivy, then push the images to GHCR on a branch push.
3. **`deploy`** — on a push to `main`, authenticate to AWS through GitHub OIDC, run Terraform, obtain the EKS cluster name from Terraform output, configure Kubernetes access, and deploy with Helm.

Pull requests targeting `main` run the test/validation and image build/scan stages. They do not push images or deploy to production. A push to `main` can deploy only after the preceding jobs succeed.

### 2.2 Runtime architecture

```mermaid
flowchart TB
    USER[Browser / User] --> EDGE[Ingress Controller or Load Balancer]
    EDGE --> FE_SVC[Frontend Kubernetes Service]
    FE_SVC --> FE_PODS[Frontend Pods: Nginx serving React build]
    FE_PODS -->|/api requests| BE_SVC[Active backend Service]
    BE_SVC --> BE_PODS[FastAPI backend Pods]
    BE_PODS --> DB_SVC[PostgreSQL ClusterIP Service]
    DB_SVC --> DB_POD[PostgreSQL Pod]
    DB_POD --> PVC[PersistentVolumeClaim / persistent storage]
    BE_PODS -. metrics endpoint .-> PROM[Prometheus - when installed/configured]
    PROM --> GRAF[Grafana dashboards - when installed/configured]
    HPA[Horizontal Pod Autoscaler] -. replica count .-> FE_PODS
    HPA -. replica count .-> BE_PODS
```

This diagram expresses the intended design. The actual routes depend on the Kubernetes Services, Ingress, and Helm templates in the repository. HPA resources must exist for each workload that should scale; the HPA does not automatically scale the EC2 node group. Prometheus and Grafana must be installed and configured before the monitoring path becomes operational.

## 3. Technology stack

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | React, Vite, HTML/JSX, CSS | User interface and browser-side interactions |
| Frontend runtime | Nginx | Serves the compiled frontend assets and may proxy routes depending on configuration |
| Backend | Python, FastAPI | REST API, request validation, application logic, health endpoints |
| ORM / database access | SQLAlchemy | Connects backend code to PostgreSQL and maps tables to Python objects |
| Schema migration | Alembic | Tracks and applies database schema changes |
| Database | PostgreSQL | Persistent application data |
| Automated tests | pytest | Backend regression tests and CI quality gate |
| Containers | Docker / Docker Compose | Repeatable packaging and local multi-service development |
| Image registry | GitHub Container Registry (GHCR) | Stores versioned backend and frontend images |
| CI/CD | GitHub Actions | Automates validation, image build/scanning, publishing, and deployment |
| Image security | Trivy | Detects applicable vulnerabilities and other image findings based on scanner configuration |
| Infrastructure as Code | Terraform | Provisions and updates AWS resources described by the Terraform configuration |
| Cloud | AWS | Hosts the EKS infrastructure and supporting network/compute resources |
| Orchestration | Kubernetes on Amazon EKS | Runs Pods, Deployments, Services, Secrets, Jobs, and autoscaling resources |
| Release management | Helm | Templates and upgrades the TaskBoard Kubernetes resources |
| Autoscaling | Kubernetes HPA | Adjusts configured workload replica counts in response to supported metrics |
| Monitoring (planned/configuration-dependent) | Prometheus and Grafana | Collects metrics and presents dashboards/alerts when installed and integrated |

## 4. Application components

### 4.1 Frontend

The frontend is a React/Vite web interface with responsive UI elements for working with tasks. The frontend is built into static assets and served by Nginx in the container runtime image.

The browser should use an application route such as `/api/...` rather than depending on an internal Kubernetes DNS name. In Kubernetes, the Service/Ingress and any configured Nginx proxy rules provide the route to the backend.

### 4.2 Backend

The backend is a FastAPI service. The documented API surface for the TaskBoard application includes the following endpoints (confirm that all routes remain present in the current backend code):

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Basic application response |
| `GET` | `/health` | Liveness/health endpoint |
| `GET` | `/ready` | Readiness endpoint; should verify the app can serve traffic and, where intended, reach the database |
| `GET` | `/metrics` | Prometheus-compatible metrics endpoint, if instrumentation is enabled |
| `GET` | `/api/tasks` | List tasks |
| `GET` | `/api/tasks/{id}` | Retrieve a task |
| `POST` | `/api/tasks` | Create a task |
| `PUT` | `/api/tasks/{id}` | Update a task |
| `DELETE` | `/api/tasks/{id}` | Delete a task |
| `GET` | `/api/tasks/stats` | Return task statistics |

FastAPI's interactive API documentation is normally available at `/docs` when enabled.

#### Why health and readiness endpoints are different

- **Liveness** answers: “Is this process alive, or should Kubernetes restart it?” A liveness check should usually be quick and should not fail simply because a dependent service has a temporary outage.
- **Readiness** answers: “Should this Pod receive traffic now?” Readiness may include checking whether the backend has initialized and can reach required dependencies such as PostgreSQL.
- **Metrics** answers: “What measurable behavior is the application reporting?” Metrics need instrumentation; Prometheus cannot infer every business event automatically.

### 4.3 PostgreSQL

PostgreSQL stores TaskBoard's persistent records. SQLAlchemy handles application database access and Alembic manages schema versions.

In the current Helm values, the database connection settings include:

```yaml
postgres:
  host: taskboard-postgres
  database: taskboard
  username: taskboard
  # Do not commit the production password here.
```

The hostname `taskboard-postgres` must match the actual Kubernetes Service name for PostgreSQL. Kubernetes DNS makes Services discoverable by name within a namespace.

PostgreSQL inside Kubernetes is suitable for a learning environment when configured with persistent volumes, backups, and recovery procedures. It is operationally demanding for a production database. For a production AWS architecture, evaluate Amazon RDS for PostgreSQL or another managed database service.

## 5. Repository structure

The following is the intended/expected structure based on the project configuration. Adjust paths if your local repository differs.

```text
TaskBoard/
├── frontend/                     # React/Vite UI and frontend Dockerfile
├── backend/                      # FastAPI API and backend Dockerfile
│   ├── app/                      # API routes, schemas, models, DB setup
│   ├── tests/                    # pytest tests
│   ├── alembic/                  # database migration scripts (if in this location)
│   ├── alembic.ini
│   └── requirements.txt
├── docker-compose.yml            # local multi-container stack
├── helm/
│   └── taskboard/                # Helm chart and values
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/             # Deployments, Services, HPA, DB, etc.
├── terraform/                    # AWS infrastructure configuration
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── ...
├── k8s/                          # optional supporting Kubernetes manifests
├── monitoring/                   # optional Prometheus/Grafana configuration
├── troubleshooting/              # optional demo manifests for failure exercises
├── scripts/                      # optional load-test/automation scripts
└── .github/
    └── workflows/
        └── ci-cd.yml             # automated pipeline
```

Never commit passwords, access keys, Terraform state files, local `.env` files containing credentials, kubeconfig files, or generated Terraform plan files.

## 6. Run TaskBoard locally

### 6.1 Prerequisites

Install the following tools:

- Git
- Docker Engine or Docker Desktop
- Docker Compose plugin
- Python 3.12+ (for running the backend outside Docker)
- Node.js 22 and npm (for working on the frontend)
- Helm and Terraform (for validating the infrastructure/chart locally)
- AWS CLI and `kubectl` (for deployment operations)

### 6.2 Start the complete local stack

From the repository root, run:

```bash
docker compose up --build
```

The intended local services are the frontend, FastAPI backend, PostgreSQL, and database migration service. Actual host ports are defined in `docker-compose.yml`.

Common local URLs from the project setup are:

- Frontend: `http://localhost:3000`
- Backend API docs: `http://localhost:8000/docs`
- Backend health: `http://localhost:8000/health`
- Backend readiness: `http://localhost:8000/ready`
- Backend metrics: `http://localhost:8000/metrics` (when the metrics route is enabled)

Stop containers without deleting the database volume:

```bash
docker compose down
```

Delete the containers **and database volumes** only when you intentionally want to discard local data:

```bash
docker compose down -v
```

### 6.3 Run the backend directly

This requires a reachable PostgreSQL database and a valid database URL.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set the connection using your local development credentials. Do not reuse a production password here:

```bash
export DATABASE_URL='postgresql+psycopg://taskboard:YOUR_LOCAL_DEV_PASSWORD@localhost:5432/taskboard'
```

Apply database migrations and start FastAPI:

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Try a health check:

```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/ready
curl -i http://localhost:8000/api/tasks
```

### 6.4 Run backend tests

```bash
cd backend
python -m pytest -q
```

Tests should use an isolated test database or a correctly initialized SQLite test schema. They should not write to the production database. If a test reports `no such table`, check that the test fixture initializes the schema or applies the required migrations before running database assertions.

### 6.5 Build the frontend locally

```bash
cd frontend
npm ci
npm run build
```

`npm ci` installs dependencies from the lockfile, making CI installs more reproducible than a floating dependency install.

## 7. Docker images

Docker packages the frontend and backend with their required runtime dependencies. This reduces “works on my machine” differences and gives CI/CD a versioned artifact to promote.

### 7.1 Backend image

The backend image packages Python, application code, and backend dependencies. It listens on port `8000` in the current deployment configuration.

Build locally:

```bash
docker build -t taskboard-backend:local ./backend
```

A database must be reachable from the container. On Linux, `host.docker.internal` may require explicit host-gateway configuration; using Docker Compose networking is usually simpler for the full stack.

### 7.2 Frontend image

The frontend uses a build/runtime separation: Node/npm builds the static frontend assets, and Nginx serves the compiled output. A multi-stage image normally avoids including build tooling in the final runtime image.

Build locally:

```bash
docker build -t taskboard-frontend:local ./frontend
```

### 7.3 Why use separate images?

- The frontend and backend can be built, scanned, versioned, and scaled independently.
- The runtime image contains only the files needed for that component.
- A frontend-only change need not require a different backend source revision, although the current workflow tags both images with the same commit SHA for traceability.
- Kubernetes can update frontend and backend Deployments independently.

## 8. GitHub Container Registry (GHCR)

GHCR stores the published Docker images. The current workflow derives the owner from `GITHUB_REPOSITORY_OWNER` and lowercases it.

Expected image names:

```text
ghcr.io/krisshank26/taskboard-backend:<COMMIT_SHA>
ghcr.io/krisshank26/taskboard-frontend:<COMMIT_SHA>
```

The actual owner is computed from the repository at runtime. The tag is `${{ github.sha }}`, the commit SHA that triggered the workflow.

This creates a traceable mapping:

```text
Git commit ──> backend image tagged with that SHA
           └─> frontend image tagged with that SHA
```

Avoid relying on `latest` for production deployment. A commit-SHA tag makes it easier to identify precisely which build is running and to roll back to a previous version.

The workflow authenticates to GHCR using the GitHub Actions token and `packages: write` permission for pushes. The EKS nodes must also be able to pull the packages:

- Public packages can be pulled without a registry pull secret.
- Private packages require valid image pull credentials or another supported authentication approach. The workflow supports optional `GHCR_PULL_USERNAME` and `GHCR_PULL_TOKEN` secrets and creates an `imagePullSecret` when both are configured.

Do not print registry tokens or commit them to source control.

## 9. GitHub Actions CI/CD pipeline

The workflow file is `.github/workflows/ci-cd.yml`.

### 9.1 Trigger behavior

- A push to `main` runs CI and may proceed to deployment if all required jobs succeed.
- A pull request targeting `main` runs validation and image build/scan checks.
- Publishing images is restricted to push events.
- The deploy job runs only for a push to `main` and targets the `production` GitHub Environment.

### 9.2 Job 1 — `test`

The job performs these checks:

1. Checkout the repository.
2. Install Python 3.12 and backend requirements.
3. Run `pytest`.
4. Install Node.js and frontend dependencies using `npm ci`.
5. Build the frontend.
6. Lint the Helm chart with `helm lint ./helm/taskboard`.
7. Check Terraform formatting.
8. Initialize Terraform without configuring the remote backend for the validation job.
9. Run `terraform validate`.

The job prevents later stages from proceeding when one of its required steps fails.

### 9.3 Job 2 — `build-scan-push`

This job depends on `test` and:

1. Calculates backend and frontend image names.
2. Logs in to GHCR on push events.
3. Builds both Docker images.
4. Tags each image with the triggering commit SHA.
5. Scans both images with Trivy.
6. Pushes the images to GHCR only on a push event.

The current Trivy policy is configured to report HIGH and CRITICAL findings, ignore findings with no available fix, and return a non-zero exit code for findings that meet the policy. Such a result blocks image publishing and deployment. This is a policy gate, not a guarantee that an image contains no vulnerabilities.

### 9.4 Job 3 — `deploy`

The deployment job runs only after the image job succeeds on a push to `main`.

It:

1. Checks required configuration such as `AWS_REGION`, `AWS_ROLE_ARN`, and `POSTGRES_PASSWORD`.
2. Assumes an AWS IAM role through GitHub OIDC.
3. Verifies the AWS identity.
4. Initializes and validates Terraform.
5. Creates a Terraform plan and applies it.
6. Reads the `cluster_name` Terraform output.
7. Configures `kubectl` for the EKS cluster.
8. Verifies Kubernetes access.
9. Creates a namespace and optional GHCR image-pull Secret.
10. Detects whether the Prometheus Operator's `ServiceMonitor` CRD exists and disables ServiceMonitor creation if it does not.
11. Runs a Helm rollout that updates the inactive color, waits for readiness, and then switches `activeColor`.
12. Lists the deployed Kubernetes resources for verification.

The workflow expects Terraform code in `./terraform` and a root output called `cluster_name`. A corresponding output for a module named `eks` commonly looks like this, **if that matches the actual module interface**:

```hcl
output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}
```

The exact expression depends on the Terraform module and resource names in the repository.

### 9.5 Security scanning coverage — what is and is not configured

The current YAML explicitly configures **container image scanning with Trivy**. It does not, by itself, configure every possible security testing category.

| Control | Current position based on the shared workflow | What it checks / next step |
|---|---|---|
| Automated tests | Configured | Backend pytest and frontend build checks; add frontend/backend unit and integration coverage as needed |
| Container image scanning | Configured with Trivy | Image OS/package vulnerabilities meeting the configured policy; inspect findings before accepting or suppressing them |
| Dependency scanning | Partial / not a separate job | Add dedicated checks for Python and npm dependency files, e.g. a dependency review tool, `pip-audit`, or an appropriate npm audit policy |
| SAST (source-code static analysis) | Not separately configured in the shared workflow | Add GitHub CodeQL or another language-appropriate SAST job and resolve findings as part of review |
| Secret scanning | Not configured as a distinct repository-wide gate in this YAML | Enable GitHub secret scanning where available and/or run a dedicated repository scanner; scanning a container image is not a substitute for scanning source history |
| IaC / Kubernetes manifest scanning | Not separately configured | Add Trivy filesystem/config scanning or another policy tool over Terraform, Helm, and Kubernetes files |
| Runtime threat detection | Not configured | Requires a runtime security tool/policy (for example, Falco or an equivalent) and an operational response process |
| Monitoring/alerting | Partial/configuration-dependent | The workflow detects the `ServiceMonitor` CRD, but does not install Prometheus/Grafana itself |

Do not describe all of these controls as active until the corresponding tools, jobs, permissions, and policies have been added and verified.

## 10. Terraform and AWS infrastructure

Terraform is Infrastructure as Code (IaC). It describes the desired state of supported AWS resources and compares that description with Terraform state and the provider's view of existing resources.

### 10.1 Intended AWS components

Depending on the resources actually declared in `terraform/`, the infrastructure may include:

- A VPC and networking configuration.
- Public/private subnets and routing.
- NAT gateway or another egress design, if configured.
- An Amazon EKS cluster and its AWS-managed Kubernetes control plane.
- EC2 worker nodes, often through an EKS managed node group.
- IAM roles and policies for the cluster, nodes, and workloads.
- Security groups and related networking rules.
- KMS resources for encryption, if configured.
- Supporting resources such as a Terraform state bucket, if managed by a separate bootstrap setup.

The exact resource list is defined by the `.tf` files; listing a resource here does not mean it already exists in the AWS account.

### 10.2 Why Terraform is separate from Kubernetes

- **Terraform** creates and manages the cloud infrastructure required to run Kubernetes.
- **Amazon EKS** provides a managed Kubernetes control plane.
- **EC2 worker nodes** provide compute capacity for scheduled Pods when using EC2-backed nodes.
- **Kubernetes** manages the application workloads running on the cluster.
- **Helm** packages, configures, and upgrades those workloads.

Terraform can also manage a Helm release when the Terraform Helm provider is explicitly used. In the current workflow, Terraform provisions infrastructure first and the workflow then invokes Helm as a separate deployment step.

### 10.3 Local Terraform commands

From the repository root:

```bash
cd terraform
terraform fmt -check -recursive
terraform init
terraform validate
terraform plan
```

Review the plan carefully before running:

```bash
terraform apply
```

The GitHub Actions workflow currently performs `plan` and `apply -auto-approve` on pushes to `main`. Because infrastructure changes can create resources, incur charges, or destroy/replace infrastructure, use protected environment approvals and consider separating routine application releases from infrastructure changes.

### 10.4 Terraform state is essential

Terraform state tracks the association between configuration and real resources. A GitHub-hosted runner is temporary, so local-only state on the runner is not suitable for repeated deployments.

Use a secured remote backend, commonly an S3 bucket with versioning and state locking, and restrict access to state. State and saved plan files may contain sensitive information even when Terraform variables are marked `sensitive`.

If the infrastructure already exists from a previous manual or partial Terraform run, reconcile/import resources into the correct state rather than creating duplicate resources or deleting resources blindly. In particular, a KMS alias that already exists or a Terraform resource address conflict should be resolved by inspecting AWS and Terraform state.

### 10.5 Cluster output

The workflow expects Terraform to expose the provisioned cluster name:

```bash
terraform -chdir=./terraform output -raw cluster_name
```

The workflow uses that value to run the AWS CLI's `eks update-kubeconfig` command. If the output is missing, deployment stops; add the correct output to the root Terraform configuration.

### 10.6 AWS access and OIDC

GitHub Actions uses OpenID Connect (OIDC) to request temporary AWS credentials by assuming the IAM role specified in `AWS_ROLE_ARN`. This is preferable to storing long-lived AWS access keys in repository secrets.

The AWS IAM OIDC provider, role trust policy, role permissions, and GitHub environment configuration must exist and permit the required operations. An explicit AWS Organizations service control policy denial cannot be overridden just by adding an IAM allow statement; the organization administrator must resolve the policy restriction or the deployment must target an account where the required action is permitted.

### 10.7 Cost awareness

EKS, EC2 nodes, block storage, load balancers, NAT gateways, data transfer, and monitoring infrastructure can all incur costs. Select region and instance types based on workload needs and account eligibility. Do not assume that an EC2 instance being Free Tier-eligible makes the complete EKS architecture free.

## 11. Kubernetes and EKS

### 11.1 What EKS provides

Amazon EKS is AWS's managed Kubernetes service. AWS runs the control plane; the customer still configures and pays for worker compute and the supporting infrastructure used by the workload. In an EC2-backed EKS cluster, EC2 nodes host the Kubernetes Pods.

### 11.2 What Kubernetes manages

| Kubernetes object | Purpose in TaskBoard |
|---|---|
| Namespace | Separates TaskBoard resources under the `taskboard` namespace |
| Deployment | Declares desired replicas and Pod template for frontend/backend versions |
| Pod | Runs one or more containers; Pods can be recreated and should not be treated as permanent identities |
| Service | Supplies stable internal networking and selects matching Pods by labels |
| Secret | Supplies sensitive values such as a database password to authorized workloads |
| PersistentVolumeClaim | Requests storage for PostgreSQL data (if configured in the chart) |
| Job | Suitable for one-off work such as database migrations (depending on chart implementation) |
| HorizontalPodAutoscaler | Adjusts the replica count of configured scalable workloads |
| Ingress | Describes HTTP(S) routing when an Ingress controller is installed/configured |

### 11.3 Backend Service selectors

The shared `backend-service.yaml` creates separate Services for blue and green backends:

```text
<release-name>-backend-blue   -> Pods labelled color=blue
<release-name>-backend-green  -> Pods labelled color=green
```

Both Services expose port `8000` and target container port `8000`. A separate active Service or other routing logic must select which color receives live traffic.

A Kubernetes Service routes only to Pods whose labels match its selector. If labels do not match, the Service can have no endpoints even while Pods are running.

### 11.4 Connect to the cluster

After the Terraform deployment succeeds:

```bash
aws eks update-kubeconfig --region "$AWS_REGION" --name "$EKS_CLUSTER_NAME"
kubectl config current-context
kubectl get nodes
kubectl get pods -n taskboard
```

For a new cluster, the first application install creates the namespace and application resources through the workflow/Helm. The Terraform role must have appropriate AWS permissions, and the caller/role must be authorized by the EKS/Kubernetes access configuration.

## 12. Helm application management

Helm packages Kubernetes resources as a **chart**, uses `values.yaml` to configure them, and tracks deployed instances as **releases**. It prevents the need to manually edit many individual Kubernetes manifests for each environment or version.

The chart is located at `helm/taskboard`.

### 12.1 Important values

The supplied `values.yaml` contains settings similar to:

```yaml
activeColor: blue
replicaCount: 2
namespace: taskboard

frontend:
  image: ghcr.io/krisshank26/taskboard-frontend

backend:
  image: ghcr.io/krisshank26/taskboard-backend

blue:
  frontendTag: latest
  backendTag: latest

green:
  frontendTag: latest
  backendTag: latest

hpa:
  enabled: true
  minReplicas: 2
  maxReplicas: 6
  targetCPUUtilizationPercentage: 60

monitoring:
  serviceMonitor:
    enabled: true
```

The CI/CD workflow overrides image repositories and tags at deployment time. Production tags should be the commit SHA, not the `latest` placeholder.

### 12.2 Useful Helm commands

Lint the chart:

```bash
helm lint ./helm/taskboard
```

Render templates locally without installing them:

```bash
helm template taskboard ./helm/taskboard --namespace taskboard
```

Install or upgrade manually, if AWS/EKS access is already configured and all required values are provided:

```bash
helm upgrade --install taskboard ./helm/taskboard \
  --namespace taskboard \
  --create-namespace \
  --wait \
  --atomic \
  --timeout 10m
```

Inspect a release:

```bash
helm status taskboard -n taskboard
helm history taskboard -n taskboard
helm get values taskboard -n taskboard
```

The `--wait` option waits for supported resources to become ready, and `--atomic` requests rollback if the upgrade fails. These options improve failure behavior, but do not prove application-level correctness on their own.

## 13. Blue-green deployment strategy

Blue-green deployment keeps two versions/environments available so a candidate version can be prepared before changing the active traffic route.

- **Blue** is one color/version of the frontend and backend.
- **Green** is the other color/version.
- **`activeColor`** is the Helm value intended to indicate which color should receive live traffic.
- **Candidate/inactive color** is updated with the new image tags first.
- **Traffic switch** occurs after the candidate passes the configured readiness checks.

### 13.1 Rollout sequence used by the workflow

1. Inspect the current Helm release and read `activeColor` and the recorded image tags.
2. Determine the inactive color (if blue is active, target green; if green is active, target blue).
3. Use the new commit SHA as the candidate's frontend and backend tags.
4. Upgrade the Helm release with the existing color still active, allowing the candidate workload to update while traffic remains on the existing color.
5. Wait for Helm readiness with `--wait --atomic`.
6. Upgrade the release again with `activeColor` switched to the candidate color.
7. Inspect the resulting Deployments, Pods, Services, and Ingress.

For the first deployment, the workflow assigns the same current build tag to both colors so that the chart does not try to pull a nonexistent `latest` image before the first rollout completes.

### 13.2 Requirement for a genuine blue-green switch

The `activeColor` value only causes a traffic switch if the chart templates use it to select the active frontend/backend Service, or otherwise route traffic to the selected color. The backend Services shown in the project are color-specific. Verify the active Service and any Ingress/Nginx routing templates. A values flag alone does not redirect traffic.

For stronger safety, add a smoke test against the candidate color's internal Service before switching traffic. Readiness indicates that a Pod passes its readiness probe; it does not prove that creating tasks, reading the database, or all user flows work correctly.

### 13.3 Rollback

Helm's atomic behavior rolls back a failed Helm upgrade. For a post-switch application problem, a release rollback or a switch back to the previous healthy color may be needed, depending on the chart's routing logic and release history. Database schema changes must be designed to remain compatible with both application versions during the rollout; blue-green traffic routing cannot by itself reverse an incompatible migration.

## 14. PostgreSQL, migrations, and secrets

### 14.1 Database migrations

Alembic tracks schema changes. A migration workflow should:

1. Build the image containing the migration code.
2. Run migrations as a dedicated Kubernetes Job or an equivalent controlled step.
3. Verify the migration succeeds before allowing the new application version to serve traffic.
4. Ensure the application version is compatible with the schema during a blue-green transition.

The supplied Helm values include a `migrations.enabled` flag and a migration tag/revision setting. Confirm the chart actually defines the migration Job/hook and that the deployment waits for it to complete. A setting in `values.yaml` alone does not execute a migration unless a template consumes it.

### 14.2 Database password handling

The production database password must not be committed to `values.yaml` or source control. Store it in a GitHub Environment secret or, for a more mature design, AWS Secrets Manager. For an EKS-hosted PostgreSQL workload, the deployment can create a Kubernetes Secret and have both PostgreSQL and the backend read its value with `secretKeyRef`.

**Important current-workflow caveat:** The shared version of `ci-cd.yml` passes `POSTGRES_PASSWORD` using Helm's `--set postgres.password=...`. Helm can retain release values, so this is not the preferred production secret pattern. Before calling the password flow production-secure, switch the chart to reference an existing Kubernetes Secret (for example, `taskboard-postgres-secret`) and make the workflow create/update that Secret without passing the password through Helm values or printing it in logs.

Example of the intended chart values shape:

```yaml
postgres:
  host: taskboard-postgres
  database: taskboard
  username: taskboard
  existingSecret: taskboard-postgres-secret
  passwordKey: POSTGRES_PASSWORD
```

The PostgreSQL container and backend container templates both need to reference this Secret. The backend's `DATABASE_URL` must be built from the same database hostname, database name, username, and password. If using SQLAlchemy, use `sqlalchemy.engine.URL.create()` or an equivalent safe URL-building function if passwords may contain reserved URL characters.

Kubernetes Secrets still require proper RBAC and encryption-at-rest configuration. Base64 encoding is not encryption. Avoid allowing general workloads or users to list/read Secrets they do not need.

### 14.3 PostgreSQL persistence

PostgreSQL data should live on persistent storage, not only in the container writable layer. Validate that the PostgreSQL chart template requests and mounts a PersistentVolumeClaim and that the chosen StorageClass is available in the EKS region. Create backups and test restore procedures.

For production, assess whether AWS RDS provides a better reliability/backup/upgrade model than operating PostgreSQL inside the EKS cluster.

## 15. Horizontal Pod Autoscaler (HPA)

The supplied Helm values define:

```yaml
hpa:
  enabled: true
  minReplicas: 2
  maxReplicas: 6
  targetCPUUtilizationPercentage: 60

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

The intended configuration keeps at least two replicas and permits a workload's replica count to increase up to six when the HPA detects sustained CPU utilization above its configured target. Confirm the HPA template and target Deployment names to identify exactly which components scale.

### How HPA works

1. A workload declares CPU/memory requests and limits.
2. A metrics provider (commonly Metrics Server for resource metrics) exposes current Pod resource usage.
3. An HPA controller compares measured utilization with the configured target.
4. Kubernetes adjusts the scale of the targeted Deployment/ReplicaSet within the minimum and maximum bounds.
5. As demand falls, HPA may scale replicas down according to its stabilization and scaling policies.

HPA does **not** guarantee a scaling decision every second. The controller observes metrics and reconciles the desired replica count over time. A CPU target of 60% is relative to resource requests, not 60% of the EC2 instance's total CPU.

### Requirements and verification

- The chart must render a valid `autoscaling/v2` HPA for the intended workload(s).
- CPU requests must be defined; the provided values include them.
- Metrics Server or an equivalent compatible resource metrics provider must be working.
- The cluster needs enough available node capacity to schedule additional Pods.
- If EC2 nodes also need to scale, configure a separate node autoscaling mechanism such as an EKS node-group scaling policy, Cluster Autoscaler, or Karpenter. HPA scales Pods; it does not provision EC2 instances itself.

Check status:

```bash
kubectl get hpa -n taskboard
kubectl describe hpa -n taskboard
kubectl top pods -n taskboard
kubectl get pods -n taskboard -o wide
```

A controlled load test can demonstrate scaling. Use a test environment and observe CPU, replica counts, errors, and latency while generating load.

## 16. Ingress and external access

The current `values.yaml` has:

```yaml
ingress:
  enabled: false
  host: taskboard.local
```

That means Ingress is disabled by default. To expose the application, the Kubernetes Ingress resource must be enabled and an Ingress controller or equivalent load-balancing integration must exist. A public deployment also needs a real DNS name, appropriate AWS load-balancer/networking configuration, and TLS certificates if HTTPS is required.

`taskboard.local` is suitable for a local/demo setup and is not a public DNS hostname. Creating an Ingress resource without a controller does not, by itself, expose the application to the internet.

Before production exposure, verify:

- The frontend path routes to the frontend Service.
- `/api` routes to the backend Service on port `8000` (or the actual configured backend port).
- Any rewrite rules preserve the paths expected by FastAPI.
- TLS and DNS are correctly configured.
- Security groups and network rules expose only required ports.

## 17. Monitoring and observability

Prometheus and Grafana are the intended monitoring layer, but they require installation and application/cluster configuration before dashboards can display useful data.

### 17.1 Prometheus

Prometheus scrapes metrics endpoints and stores time-series samples. The documented backend exposes `/metrics` when the relevant instrumentation is enabled. Metrics may include request counts, request latency, errors, and process-level data depending on the instrumentation used.

The Helm values contain `monitoring.serviceMonitor.enabled`. A `ServiceMonitor` is a custom resource commonly consumed by the Prometheus Operator. It can only be created when the corresponding CRD is installed. The current workflow checks for the CRD and disables the chart's ServiceMonitor setting when the CRD is absent. **This check does not install Prometheus or Grafana.**

### 17.2 Grafana

Grafana queries Prometheus and displays dashboards. Useful panels can include:

- Request throughput and request rate.
- HTTP error rate.
- API latency (for example p50, p95, and p99, if recorded).
- Backend Pod restarts and readiness status.
- CPU and memory usage.
- HPA desired/current replicas.
- PostgreSQL connection health and resource metrics, if a suitable exporter and permissions are configured.

Dashboards need data sources, scrape configuration, and appropriate metric names/labels. Empty dashboards usually mean data collection or queries must be configured, not that Grafana creates metrics automatically.

### 17.3 Business metrics are different from infrastructure metrics

Prometheus can only report events the application exposes as metrics. It will not automatically know how many users logged in, how many tasks were created, or how many people are using the site.

For example, a login count requires an authentication/login event and instrumentation such as a counter metric. Task creation can be tracked by incrementing a counter after a task is successfully created. Avoid putting usernames, email addresses, task IDs, or other high-cardinality/sensitive identifiers into Prometheus labels.

The API surface listed above does not itself establish that authentication or user-login tracking is implemented. If the current TaskBoard app has no login flow, a “users logged in” dashboard requires adding that application feature and its metrics first.

### 17.4 Alerts and actionable observability

Useful alerts can include sustained high error rates, unavailable Pods, repeated restarts, elevated API latency, PostgreSQL connection failures, insufficient node capacity, and an HPA stuck at its maximum. Alerts should have owners, useful diagnostic context, and a response/runbook—not merely send noise.

## 18. DevSecOps and security controls

DevSecOps integrates security checks throughout code review, build, release, deployment, and runtime operations. No single scanner can establish that an application is secure.

### 18.1 Controls used or planned

| Stage | Goal | Project treatment |
|---|---|---|
| Secure source control | Review changes and protect the main branch | GitHub repository, pull requests, least-privilege workflow permissions; branch/environment protections should be enabled in repository settings |
| Automated tests | Detect regressions before release | pytest and frontend build in CI |
| SAST | Detect risky code patterns before runtime | Add CodeQL or another SAST tool; not a dedicated job in the shared workflow |
| Dependency scanning | Detect vulnerable direct/transitive packages | Add policy-controlled Python/npm dependency scans; not a separate job in the shared workflow |
| Secret scanning | Prevent credentials from entering commits/images | Keep credentials in secret stores; enable repository-wide scanning as available and add a dedicated scanner/job if needed |
| Container scanning | Identify vulnerable image OS and language packages | Trivy scans backend and frontend images and blocks configured HIGH/CRITICAL findings |
| IaC and Kubernetes scanning | Identify risky Terraform/Helm/Kubernetes configuration | Add dedicated filesystem/misconfiguration scanning; not explicitly configured in the shared workflow |
| Identity security | Avoid long-lived AWS access keys | GitHub Actions OIDC assumes an AWS IAM role |
| Least privilege | Limit the blast radius of credentials | Narrow role permissions, Kubernetes RBAC, and Secret access; review actual policies |
| Immutable artifacts | Trace deployed code to a commit | Use commit-SHA image tags and avoid mutable `latest` tags in production |
| Deployment gate | Avoid deploying an unready build | CI job dependencies and Helm wait/atomic settings |
| Runtime security | Detect or block suspicious activity after deployment | Add runtime detection/policies such as Falco or an equivalent; not configured in the shared workflow |
| Monitoring and response | Detect reliability/security problems | Prometheus/Grafana and alert rules need installation/configuration |

### 18.2 Trivy policy

The workflow uses Trivy against built images and configures:

- Severity levels: `HIGH,CRITICAL`.
- `ignore-unfixed: true`, so findings without a known available fix are ignored by this gate.
- `exit-code: "1"`, so qualifying findings can fail the job.

A passing scan means no finding matched this specific policy at scan time; it does not mean the image is vulnerability-free. Keep base images current, rebuild frequently, assess scan reports, and document justified exceptions. Do not suppress findings only to make CI green.

### 18.3 Secret safety

- Never commit real passwords, cloud credentials, registry tokens, or kubeconfig files.
- Use GitHub Secrets/Environments and AWS IAM OIDC where appropriate.
- Prefer Kubernetes `secretKeyRef` or a controlled external-secrets integration for application secrets.
- Restrict who can run production deployments and change environment secrets.
- Avoid printing secrets in logs or passing them through command-line options that can be retained in release metadata.
- Remember that Terraform state and plan files may contain sensitive data.

### 18.4 Runtime hardening

For a more complete production posture, review:

- Non-root container users and minimal runtime images.
- Read-only root filesystems where compatible, dropped Linux capabilities, and seccomp settings.
- CPU/memory requests and limits.
- Kubernetes RBAC and ServiceAccount permissions.
- NetworkPolicies where supported by the cluster networking setup.
- Image provenance/signing and admission policies if required.
- TLS, ingress rules, and database network access.
- Vulnerability remediation, patch cadence, backups, and incident response procedures.

## 19. GitHub and AWS configuration checklist

### 19.1 GitHub production Environment

Create a GitHub Environment named `production` and configure the following values.

**Environment variables used by the shared workflow:**

| Name | Description |
|---|---|
| `AWS_REGION` | AWS region where the Terraform/EKS resources are deployed |
| `AWS_ROLE_ARN` | IAM role ARN assumed by GitHub Actions through OIDC |

**Environment secrets used by the shared workflow:**

| Name | Required? | Description |
|---|---|---|
| `POSTGRES_PASSWORD` | Yes in the shared workflow | Database password; keep it secret and avoid committing it |
| `GHCR_PULL_USERNAME` | Only for private GHCR packages | Username used to pull private images |
| `GHCR_PULL_TOKEN` | Only for private GHCR packages | Token paired with the pull username |

The workflow requires both GHCR pull credentials or neither. When images are public, leave both pull credentials unset.

`POSTGRES_USER` can be a GitHub variable (for example `taskboard`), but the current shared workflow reads the username from Helm's `postgres.username` value. If you want GitHub to control it, explicitly add `POSTGRES_USER: ${{ vars.POSTGRES_USER }}` to the deploy job and pass `--set-string postgres.username="$POSTGRES_USER"` to the Helm command.

Use production Environment reviewers/approval rules for infrastructure-changing deployments where available.

### 19.2 AWS/IAM prerequisites

Before the first deployment:

- Configure the GitHub OIDC identity provider and IAM role trust relationship.
- Restrict the role's trust to the intended repository/branch or GitHub Environment subject.
- Grant the role only the AWS permissions Terraform needs, plus the permissions needed for EKS access setup and related deployment tasks.
- Confirm AWS Organizations service control policies allow the required actions.
- Ensure Terraform's remote state backend exists and is accessible.
- Confirm the Terraform configuration defines the cluster and worker nodes, and exposes `cluster_name`.
- Confirm the selected region and EC2 instance type are supported by the account and region.
- Resolve any pre-existing resource conflicts by checking state and AWS resources before importing or changing resources.

### 19.3 Terraform inputs

If Terraform variables do not have defaults, provide them through an appropriately secured variable file or GitHub Environment variables/secrets using `TF_VAR_<variable_name>`. Do not assume `prod.tfvars` exists; use the actual path if the repository has such a file.

Avoid storing sensitive inputs in committed `.tfvars` files. If a variable is sensitive, mark it `sensitive = true` where useful, while remembering that sensitive values can still be stored in state.

## 20. Operational commands

### 20.1 Kubernetes status

```bash
kubectl get nodes
kubectl get all -n taskboard
kubectl get deployments,pods,services,ingress -n taskboard
kubectl get events -n taskboard --sort-by=.lastTimestamp
```

### 20.2 Logs and Pod details

```bash
kubectl logs -n taskboard <pod-name>
kubectl logs -n taskboard <pod-name> --previous
kubectl describe pod -n taskboard <pod-name>
```

For a multi-container Pod, specify `-c <container-name>` when needed.

### 20.3 Services and traffic routing

```bash
kubectl get svc -n taskboard
kubectl get endpoints -n taskboard
kubectl get pods -n taskboard --show-labels
```

If a Service has no endpoints, verify its selector labels and Pod labels.

### 20.4 HPA

```bash
kubectl get hpa -n taskboard
kubectl describe hpa -n taskboard
kubectl top pods -n taskboard
```

If `kubectl top` or HPA metrics are unavailable, check Metrics Server and the metrics API before investigating HPA policy itself.

### 20.5 Helm

```bash
helm list -n taskboard
helm status taskboard -n taskboard
helm history taskboard -n taskboard
```

### 20.6 Terraform

Run in the Terraform root directory:

```bash
terraform fmt -check -recursive
terraform validate
terraform plan
terraform output
```

Treat plan output and state as potentially sensitive. Review any proposed destroy/replacement actions carefully.

## 21. Troubleshooting

### `ImagePullBackOff` or `ErrImagePull`

Possible causes:

- The image repository or tag is wrong.
- The image hasn't been pushed to GHCR.
- The package is private and the Kubernetes image-pull Secret is missing/invalid.
- The node cannot reach the registry.

Inspect:

```bash
kubectl describe pod -n taskboard <pod-name>
kubectl get secrets -n taskboard
```

Never print a pull token or dump a Secret's contents while troubleshooting.

### Pod is `CrashLoopBackOff`

Inspect logs and events. Common causes include missing environment variables, incompatible dependencies, database connection failures, migration failures, or the application failing during startup.

```bash
kubectl logs -n taskboard <pod-name> --previous
kubectl describe pod -n taskboard <pod-name>
```

### PostgreSQL connection fails

Verify:

- The PostgreSQL Pod is running and Ready.
- The Service name matches `postgres.host`.
- PostgreSQL listens on port `5432`.
- Database name and username match between the database and backend.
- The Kubernetes Secret exists in the same namespace and uses the expected key.
- Backend `DATABASE_URL` is correctly constructed.
- Migrations completed successfully.
- The PostgreSQL persistent data directory was not initialized previously with different credentials.

A Secret update does not automatically reset a password inside an already-initialized PostgreSQL data directory.

### Backend Service has no endpoints

```bash
kubectl get svc -n taskboard
kubectl get endpoints -n taskboard
kubectl get pods -n taskboard --show-labels
```

Compare the Service selector with the Pods' labels. The provided blue/green backend Services specifically select their matching color labels.

### Readiness probe fails

A readiness failure prevents a Pod from receiving Service traffic. Check application logs, the `/ready` handler, database access, port `8000`, and the configured probe path.

### HPA shows `<unknown>` metrics

Check whether Metrics Server is installed and healthy, that the metrics API is available, and that resource requests are present in the workload template. HPA cannot calculate CPU utilization without valid usage metrics.

### `ServiceMonitor` CRD not found

A `ServiceMonitor` is not a built-in Kubernetes resource. It is commonly installed by a Prometheus Operator distribution. Install/configure a compatible monitoring stack or keep `monitoring.serviceMonitor.enabled` false until the CRD exists. The current workflow disables the setting when the CRD is absent.

### Terraform fails to create an IAM/OIDC resource

Check the exact denied action, IAM policy, role trust configuration, and AWS Organizations service control policies. An explicit deny in an SCP takes precedence over an IAM allow. If the account is managed by an organization, an authorized organization administrator may need to change the SCP.

### Terraform reports an existing KMS alias/resource

Do not delete the alias or KMS key just to make an apply succeed. Verify ownership and current Terraform state. If the resource should be managed by this state, carefully import it using the correct Terraform resource address, then plan and review the result. Never import a resource into the wrong state.

### EKS node group creation fails

Read the actual AWS failure reason. Check the chosen EC2 type's availability and account/region eligibility, subnet capacity, IAM node role, and quota limits. “Free Tier eligible” is not the only condition required for an EKS node group to launch.

### GitHub Actions cannot connect to AWS

Verify `AWS_REGION`, `AWS_ROLE_ARN`, the GitHub Environment, OIDC trust conditions, provider configuration, IAM permissions, and any AWS Organizations SCPs. Do not work around this by committing long-lived AWS access keys to the repository.

## 22. Important production considerations

Before calling the project production-ready, verify the following items in the actual repository and AWS account:

- [ ] Remote Terraform state uses an appropriately secured backend, versioning, and locking.
- [ ] AWS OIDC trust and permissions work without long-lived keys.
- [ ] Terraform provisions all required networking, EKS, and worker resources and exposes the correct `cluster_name` output.
- [ ] The account/region can launch the selected node instance types and has sufficient quotas.
- [ ] Database credentials are injected through a Kubernetes Secret or external secret integration, not retained as ordinary Helm release values.
- [ ] PostgreSQL uses persistent storage and tested backups/restores, or a managed database is used.
- [ ] Database migrations are run in a controlled step and are compatible with blue-green versions.
- [ ] Active traffic truly switches according to `activeColor`; candidate smoke tests run before the switch.
- [ ] HPA targets the intended Deployments and Metrics Server/required metrics providers are available.
- [ ] The Ingress controller, DNS, TLS, routing, and network rules are configured if public access is required.
- [ ] GHCR packages are intentionally public or private and the cluster can pull them.
- [ ] SAST, dependency scanning, repository secret scanning, and IaC scanning are configured if they are required project acceptance criteria.
- [ ] Runtime security, Prometheus/Grafana, alerting, and runbooks are installed/configured if they are part of the target production design.
- [ ] Production deploys require suitable approvals and Terraform plans are reviewed.
- [ ] Resource costs are understood; unnecessary development resources are destroyed only after preserving state/data that must remain.

## 23. Project demonstration checklist

A good end-to-end demonstration follows the path of one change through the system:

1. Open TaskBoard locally and create/read/update/delete a task.
2. Show the frontend, FastAPI documentation, health endpoints, and database persistence.
3. Make a small code change and commit it to Git.
4. Open a pull request and show tests/build/validation and image scanning.
5. Merge/push to `main` and show the GitHub Actions jobs.
6. Show the backend and frontend images in GHCR with the commit SHA tag.
7. Show the Trivy scan output and explain the policy for HIGH/CRITICAL findings.
8. Show Terraform code, a reviewed plan, and the AWS resources it manages.
9. Show the EKS cluster and worker nodes once provisioning has succeeded.
10. Show the Helm release and frontend/backend Pods/Services.
11. Show the blue-green candidate rollout and explain how traffic switches to the new color.
12. Show HPA configuration and demonstrate scaling in a controlled test if metrics and capacity are available.
13. Show Prometheus/Grafana dashboards only after the monitoring stack and scrape targets are configured.
14. Simulate a safe failure (such as a bad image tag in a non-production namespace) and diagnose it with Pod details, logs, events, and Service endpoints.
15. Explain one security control and one improvement still planned.

## 24. DevSecOps concepts learned

Building TaskBoard brings together the following DevOps and DevSecOps concepts:

### Continuous Integration (CI)

Every proposed change can be checked automatically by running tests, compiling/building the frontend, linting Helm, and validating Terraform. This makes feedback faster and prevents known-broken code from reaching later stages.

### Continuous Delivery and Deployment (CD)

The pipeline publishes a traceable image and automates deployment. The project also demonstrates the difference between validating a change, publishing an artifact, and changing production traffic.

### Infrastructure as Code

Terraform describes cloud infrastructure in code, making it reviewable, repeatable, and reconcilable. Remote state, locking, resource imports, and plan review are part of operating IaC safely.

### Containerization and immutable artifacts

Docker packages components into portable images. GHCR stores those images. Commit-SHA tagging connects a deployed artifact to its source revision and helps prevent accidental drift from a mutable tag.

### Container orchestration

Kubernetes maintains desired replica counts, schedules Pods, restarts failed containers, provides stable Service networking, and coordinates rollout behavior. It does not remove the need to design health checks, resource requests, storage, and safe configuration.

### Release and configuration management

Helm templates Kubernetes resources using values and tracks releases. `helm upgrade`, readiness waits, and rollback behavior support repeatable releases. Blue-green deployment separates preparing a candidate from switching live traffic.

### Autoscaling and capacity planning

HPA scales configured workloads according to resource/custom metrics. Pod scaling is different from EC2/node scaling, and neither can exceed available cluster capacity without suitable node autoscaling and quotas.

### Database lifecycle management

SQLAlchemy, PostgreSQL, and Alembic introduce schema evolution, connection configuration, credentials, persistence, and migration ordering. Blue-green deploys require schema changes to remain compatible with the versions that may coexist during a rollout.

### Security gates in the software supply chain

Trivy container-image scanning demonstrates shifting vulnerability checks into CI. A broader DevSecOps practice adds SAST, dependency analysis, repository secret scanning, IaC policy checks, and runtime controls at the right stages.

### Secrets and identity management

GitHub Secrets/Environments, AWS OIDC, IAM least privilege, Kubernetes Secret references, and RBAC show why credentials should be short-lived where possible, scoped to need, and kept out of source code and logs.

### Observability

Metrics, logs, dashboards, alerts, and health endpoints provide different views of system behavior. Infrastructure metrics can show CPU pressure and Pod restarts; business metrics require explicit application instrumentation. Observability is useful when signals connect to a clear operational question and response procedure.

### Reliability and failure recovery

Readiness probes, persistent storage, blue-green releases, rollback behavior, backups, and troubleshooting practices reduce downtime risk. They do not eliminate failure, so the design must include verification and recovery paths.

### Shared responsibility and cost management

AWS manages parts of EKS's control plane, while the project owner remains responsible for application workloads, access policies, node capacity, secrets, backups, logging, and cost-aware infrastructure decisions.

Together, these practices demonstrate a delivery lifecycle in which application engineering, infrastructure automation, operational reliability, and security checks are designed to work as one system.

## 25. Official documentation

- [Docker documentation](https://docs.docker.com/)
- [Docker Compose documentation](https://docs.docker.com/compose/)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [GitHub Actions OIDC with AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Trivy documentation](https://trivy.dev/latest/docs/)
- [Terraform documentation](https://developer.hashicorp.com/terraform/docs)
- [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3)
- [Amazon EKS documentation](https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html)
- [Kubernetes documentation](https://kubernetes.io/docs/home/)
- [Kubernetes Horizontal Pod Autoscaler](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
- [Helm documentation](https://helm.sh/docs/)
- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy documentation](https://docs.sqlalchemy.org/)
- [Alembic documentation](https://alembic.sqlalchemy.org/)
- [Prometheus documentation](https://prometheus.io/docs/introduction/overview/)
- [Grafana documentation](https://grafana.com/docs/)

--- 
