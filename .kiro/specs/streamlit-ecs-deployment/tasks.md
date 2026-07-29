# Implementation Plan: Streamlit ECS Deployment

## Overview

Add a Streamlit ECS Fargate service to the existing CloudFormation stack (`cgs-ai-analyst-agent-project`). This involves modifying the CloudFormation template to add 5 new resources (task definition, service, target group, listener, log group), updating 2 security groups, adding 3 parameters and 1 output, and making a one-line Dockerfile change. All changes are declarative IaC with existing deployment scripts handling rollout.

## Tasks

- [x] 1. Add Streamlit parameters and conditions to CloudFormation template
  - [x] 1.1 Add StreamlitDesiredCount, StreamlitUsername, and StreamlitPassword parameters to `cloudformation-template-validated.yml`
    - Add `StreamlitDesiredCount` parameter (Type: Number, Default: 1, MinValue: 0, MaxValue: 10)
    - Add `StreamlitUsername` parameter (Type: String, NoEcho: false, no default)
    - Add `StreamlitPassword` parameter (Type: String, NoEcho: true, no default)
    - _Requirements: 2.5, 5.1_

- [x] 2. Update security groups for Streamlit port access
  - [x] 2.1 Add port 8501 ingress rule to AlbSecurityGroup
    - Add a SecurityGroupIngress entry allowing TCP port 8501 from `AlbIngressCidr`
    - Place it after the existing port 80 rule in `AlbSecurityGroup`
    - _Requirements: 3.4_

  - [x] 2.2 Add port 8501 ingress rule to ServiceSecurityGroup
    - Add a SecurityGroupIngress entry allowing TCP port 8501 from `AlbSecurityGroup`
    - Place it after the existing port 8080 rule in `ServiceSecurityGroup`
    - _Requirements: 3.5_

- [x] 3. Add Streamlit ALB target group and listener
  - [x] 3.1 Create StreamlitTargetGroup resource in the CloudFormation template
    - Type: `AWS::ElasticLoadBalancingV2::TargetGroup`
    - Port 8501, Protocol HTTP, TargetType ip, VpcId from existing Vpc ref
    - HealthCheckPath: `/_stcore/health`, Interval 30s, Healthy 2, Unhealthy 3
    - _Requirements: 3.1, 3.2_

  - [x] 3.2 Create StreamlitListener resource in the CloudFormation template
    - Type: `AWS::ElasticLoadBalancingV2::Listener`
    - LoadBalancerArn referencing existing `ApplicationLoadBalancer`
    - Port 8501, Protocol HTTP, DefaultAction forward to `StreamlitTargetGroup`
    - _Requirements: 3.3_

- [x] 4. Add Streamlit CloudWatch log group, task definition, and ECS service
  - [x] 4.1 Create StreamlitLogGroup resource in the CloudFormation template
    - Type: `AWS::Logs::LogGroup`
    - LogGroupName: `/ecs/data-architecture-ai-streamlit`
    - RetentionInDays: 30
    - _Requirements: 7.1_

  - [x] 4.2 Create StreamlitTaskDefinition resource in the CloudFormation template
    - Type: `AWS::ECS::TaskDefinition`
    - Family: `data-architecture-ai-streamlit`
    - Cpu: "512", Memory: "1024", NetworkMode: awsvpc, RequiresCompatibilities: FARGATE
    - ExecutionRoleArn: existing `EcsTaskExecutionRole`, TaskRoleArn: existing `EcsTaskRole`
    - Container named "streamlit" with image from ECR (same as backend, use same `!If UseCustomImage` logic)
    - Command override: `["streamlit", "run", "/app/scripts/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]`
    - ContainerPort: 8501
    - Environment variables: API_URL (http://ALB DNS:80), APP_USERNAME, APP_PASSWORD, and conditional API_KEY
    - LogConfiguration: awslogs driver, group from StreamlitLogGroup, stream prefix "streamlit"
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 4.1, 4.2, 7.2, 7.3_

  - [x] 4.3 Create StreamlitService resource in the CloudFormation template
    - Type: `AWS::ECS::Service`
    - DependsOn: StreamlitListener
    - Cluster: existing EcsCluster, TaskDefinition: StreamlitTaskDefinition
    - DesiredCount: `!Ref StreamlitDesiredCount`, LaunchType: FARGATE
    - HealthCheckGracePeriodSeconds: 120
    - NetworkConfiguration: PrivateSubnet1/PrivateSubnet2, AssignPublicIp DISABLED, ServiceSecurityGroup
    - LoadBalancers: container "streamlit" on port 8501 to StreamlitTargetGroup
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 5. Add StreamlitUrl output and update Dockerfile
  - [x] 5.1 Add StreamlitUrl output to the CloudFormation template Outputs section
    - Value: `!Sub "http://${ApplicationLoadBalancer.DNSName}:8501"`
    - Description: Streamlit Chat UI URL
    - _Requirements: 8.1, 8.2_

  - [x] 5.2 Add `COPY .streamlit /app/.streamlit` to the Dockerfile
    - Place after the existing `COPY config /app/config` line
    - This makes the Streamlit theme and server config available in the container
    - _Requirements: 6.4_

- [x] 6. Checkpoint - Validate template and verify changes
  - Ensure `aws cloudformation validate-template --template-body file://cloudformation-template-validated.yml --region eu-north-1` passes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Update deploy script to pass Streamlit parameters
  - [x] 7.1 Update `deploy-changeset.sh` to include Streamlit parameters in the CFN_PARAMETERS JSON
    - Add `StreamlitDesiredCount` parameter (from env var `STREAMLIT_DESIRED_COUNT`, default "1")
    - Add `StreamlitUsername` parameter (from env var `STREAMLIT_USERNAME`, default empty)
    - Add `StreamlitPassword` parameter (from env var `STREAMLIT_PASSWORD`, default empty)
    - Display StreamlitUrl in the deployment complete output alongside the existing API URL
    - _Requirements: 2.5, 5.1, 5.2, 8.1_

- [x] 8. Final checkpoint - Full validation
  - Ensure CloudFormation template validates successfully
  - Ensure Dockerfile builds without errors (syntax check)
  - Ensure deploy script is valid bash (shellcheck or bash -n)
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- No property-based tests apply - all changes are declarative CloudFormation YAML and Dockerfile instructions, not executable application code
- The Streamlit app code (`scripts/streamlit_app.py`) already handles remote mode, authentication, and API connectivity - no app code changes needed
- Deploy with `StreamlitDesiredCount=1` (default) which starts the Streamlit container immediately after the stack update. The Docker image must be pushed to ECR before the stack update for the service to start successfully.
- The `deploy-changeset.sh --auto` flow handles the correct ordering: deploy stack changes first, then push image, then scale up
- Security groups are modified in-place (not replaced) so existing backend connectivity is preserved during update

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "2.2", "4.1"] },
    { "id": 2, "tasks": ["3.1", "4.2"] },
    { "id": 3, "tasks": ["3.2", "4.3", "5.2"] },
    { "id": 4, "tasks": ["5.1", "7.1"] }
  ]
}
```
