# Requirements Document

## Introduction

Deploy the Streamlit chat UI as a second ECS Fargate service alongside the existing FastAPI backend within the same CloudFormation stack. The Streamlit service runs in "remote mode" - forwarding user queries to the FastAPI backend via HTTP - and is accessible through the existing Application Load Balancer using a dedicated listener on port 8501. Authentication is handled by the Streamlit app itself using environment-variable-based credentials (APP_USERNAME/APP_PASSWORD).

## Glossary

- **CloudFormation_Stack**: The existing `cgs-ai-analyst-agent-project` CloudFormation stack in eu-north-1 that manages VPC, ALB, ECS cluster, ECR, and related infrastructure
- **ALB**: The existing Application Load Balancer (`data-arch-ai-alb`) in the stack's public subnets
- **ECS_Cluster**: The existing ECS Fargate cluster (`data-architecture-ai`) running the FastAPI backend
- **Streamlit_Service**: The new ECS Fargate service running the Streamlit chat UI container on port 8501
- **Backend_Service**: The existing ECS Fargate service running the FastAPI API container on port 8080
- **Streamlit_Task_Definition**: The ECS task definition for the Streamlit container
- **Streamlit_Target_Group**: The ALB target group routing traffic to Streamlit tasks on port 8501
- **Streamlit_Listener**: The ALB listener on port 8501 forwarding to the Streamlit target group
- **ECR_Repository**: The existing ECR repository (`data-architecture-ai`) storing container images
- **Service_Security_Group**: The existing security group allowing ALB-to-ECS traffic
- **VPC_Endpoints**: The existing VPC interface endpoints enabling private access to AWS services

## Requirements

### Requirement 1: Streamlit ECS Task Definition

**User Story:** As a platform engineer, I want a Fargate task definition for the Streamlit container, so that the chat UI can run as a managed container in the same cluster as the backend.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL define a Streamlit_Task_Definition with NetworkMode set to awsvpc and RequiresCompatibilities set to FARGATE
2. THE Streamlit_Task_Definition SHALL specify a container named "streamlit" with ContainerPort 8501
3. THE Streamlit_Task_Definition SHALL use the same ECR_Repository image as the Backend_Service with a different entrypoint command that runs `streamlit run /app/scripts/streamlit_app.py --server.port=8501 --server.address=0.0.0.0`
4. THE Streamlit_Task_Definition SHALL set the API_URL environment variable to the ALB DNS name (http protocol, port 80) so the Streamlit container routes queries to the Backend_Service through the ALB
5. THE Streamlit_Task_Definition SHALL set the APP_USERNAME and APP_PASSWORD environment variables from stack parameters for login authentication
6. THE Streamlit_Task_Definition SHALL allocate 512 CPU units and 1024 MiB of memory
7. THE Streamlit_Task_Definition SHALL use the existing EcsTaskExecutionRole and a task role with CloudWatch Logs write permissions
8. THE Streamlit_Task_Definition SHALL configure awslogs log driver writing to a `/ecs/data-architecture-ai-streamlit` log group with stream prefix "streamlit"

### Requirement 2: Streamlit ECS Service

**User Story:** As a platform engineer, I want an ECS Fargate service for Streamlit, so that the container is kept running and registered with the load balancer.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL define a Streamlit_Service in the ECS_Cluster using FARGATE launch type
2. THE Streamlit_Service SHALL run in the same private subnets (PrivateSubnet1, PrivateSubnet2) as the Backend_Service with AssignPublicIp set to DISABLED
3. THE Streamlit_Service SHALL use the existing Service_Security_Group for network access
4. THE Streamlit_Service SHALL register with the Streamlit_Target_Group on container port 8501
5. THE Streamlit_Service SHALL have a DesiredCount controlled by a new stack parameter (StreamlitDesiredCount) defaulting to 1
6. THE Streamlit_Service SHALL set HealthCheckGracePeriodSeconds to 120 to allow container startup
7. WHEN StreamlitDesiredCount is set to 0, THE CloudFormation_Stack SHALL still validate all service configuration including container port, target group registration, and security group rules

### Requirement 3: ALB Listener and Target Group for Streamlit

**User Story:** As a user, I want to access the Streamlit chat UI through the ALB on a dedicated port, so that I can reach the UI from a browser without conflicting with the backend API on port 80.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL define a Streamlit_Target_Group with port 8501, protocol HTTP, target type ip, and health check path `/_stcore/health`
2. THE Streamlit_Target_Group SHALL use a health check interval of 30 seconds with healthy threshold 2 and unhealthy threshold 3
3. THE CloudFormation_Stack SHALL define a Streamlit_Listener on the ALB listening on port 8501 with protocol HTTP and default action forwarding to the Streamlit_Target_Group
4. THE AlbSecurityGroup SHALL allow inbound TCP traffic on port 8501 from the AlbIngressCidr parameter
5. THE Service_Security_Group SHALL allow inbound TCP traffic on port 8501 from the AlbSecurityGroup
6. THE CloudFormation template SHALL validate that the Streamlit_Listener port, Streamlit_Target_Group port, and security group ingress rules all reference the same port number (8501) to prevent misconfiguration at deployment time

### Requirement 4: Backend Connectivity from Streamlit

**User Story:** As a platform engineer, I want the Streamlit container to reach the FastAPI backend, so that user queries submitted in the chat UI are processed by the backend API.

#### Acceptance Criteria

1. THE Streamlit_Task_Definition SHALL set API_URL to the ALB HTTP endpoint (port 80) so requests traverse the ALB to the Backend_Service
2. WHEN the Backend_Service requires an API key (ApiKey parameter is non-empty), THE Streamlit_Task_Definition SHALL set the API_KEY environment variable to the same ApiKey parameter value
3. THE Streamlit container SHALL be able to reach the ALB DNS name over HTTP because the ALB resides in public subnets and the private subnet route table allows intra-VPC traffic

### Requirement 5: Authentication for Streamlit UI

**User Story:** As a security-conscious operator, I want the Streamlit UI to require username and password login, so that unauthorized users cannot access the data analyst interface.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL define two new parameters: StreamlitUsername (no default, NoEcho false) and StreamlitPassword (no default, NoEcho true)
2. THE Streamlit_Task_Definition SHALL pass StreamlitUsername as APP_USERNAME and StreamlitPassword as APP_PASSWORD environment variables to the container
3. WHEN APP_USERNAME or APP_PASSWORD is empty, THE Streamlit app SHALL display an error message and refuse access
4. WHEN a user submits valid credentials, THE Streamlit app SHALL grant session access, track session continuity via Streamlit session_state, and terminate the session when the user clicks Logout or the session expires

### Requirement 6: Container Image Strategy

**User Story:** As a developer, I want to use the same Docker image for both the backend and Streamlit services, so that the CI/CD pipeline builds only one image and both services stay in sync.

#### Acceptance Criteria

1. THE Streamlit_Task_Definition SHALL use the same container image URI as the Backend_Service (from the ECR_Repository)
2. THE Streamlit_Task_Definition SHALL override the default entrypoint with a command that runs Streamlit instead of the FastAPI server
3. THE Dockerfile SHALL include all Streamlit dependencies (already present in requirements.txt) and the scripts/streamlit_app.py file (already copied via `COPY scripts /app/scripts`)
4. THE Dockerfile SHALL include the .streamlit/config.toml configuration file by adding a `COPY .streamlit /app/.streamlit` instruction

### Requirement 7: CloudWatch Logging for Streamlit

**User Story:** As an operator, I want Streamlit container logs in CloudWatch, so that I can troubleshoot UI issues independently from backend logs.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL create a CloudWatch Log Group named `/ecs/data-architecture-ai-streamlit` with 30-day retention
2. THE Streamlit_Task_Definition SHALL configure the awslogs log driver to write to the Streamlit log group
3. THE log stream prefix SHALL be "streamlit" to distinguish from backend "api" streams

### Requirement 8: Stack Outputs for Streamlit URL

**User Story:** As a developer, I want the CloudFormation stack to output the Streamlit URL, so that I can find the access URL after deployment without manual lookup.

#### Acceptance Criteria

1. THE CloudFormation_Stack SHALL output a value named "StreamlitUrl" containing the ALB DNS name with port 8501 (format: `http://<alb-dns>:8501`)
2. THE output description SHALL indicate it is the Streamlit Chat UI URL
