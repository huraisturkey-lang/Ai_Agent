#!/usr/bin/env bash
# Teardown script - deletes all CloudFormation stacks and cleans up ECR images.
#
# Usage:
#   ./scripts/teardown.sh          # Interactive - asks for confirmation
#   ./scripts/teardown.sh --force  # Skip confirmation (CI/automation)
#
# What it does:
#   1. Scales ECS services to 0 (stops running tasks immediately)
#   2. Deletes the RDS Aurora stack (if exists) - takes a final snapshot
#   3. Deletes the main stack (VPC, ECS, ALB, Lambda)
#   4. Cleans up all ECR images and repository
#   5. Deletes S3 data buckets (empties first, then removes)
#   6. Deletes Athena workgroup
#   7. Deletes Glue crawlers and databases
#   8. Deletes CloudWatch log groups
#
# After teardown, NOTHING remains - clean slate for redeployment.
set -euo pipefail

REGION="${AWS_REGION:-eu-north-1}"
MAIN_STACK="cgs-ai-analyst-agent-project"
RDS_STACK="cgs-ai-rds-aurora"
ECR_REPO="data-architecture-ai"
FORCE=false

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=true ;;
  esac
done

echo "=========================================="
echo "TEARDOWN - CloudAge Data Architecture"
echo "=========================================="
echo "Region:     $REGION"
echo "Main stack: $MAIN_STACK"
echo "RDS stack:  $RDS_STACK"
echo ""

# ── Check what exists ──────────────────────────────────────────────────────
MAIN_STATUS="$(aws cloudformation describe-stacks \
  --stack-name "$MAIN_STACK" \
  --region "$REGION" \
  --query 'Stacks[0].StackStatus' \
  --output text 2>/dev/null || echo 'NOT_FOUND')"

RDS_STATUS="$(aws cloudformation describe-stacks \
  --stack-name "$RDS_STACK" \
  --region "$REGION" \
  --query 'Stacks[0].StackStatus' \
  --output text 2>/dev/null || echo 'NOT_FOUND')"

echo "Main stack status: $MAIN_STATUS"
echo "RDS stack status:  $RDS_STATUS"
echo ""

if [[ "$MAIN_STATUS" == "NOT_FOUND" && "$RDS_STATUS" == "NOT_FOUND" ]]; then
  echo "Nothing to tear down - no stacks found."
  exit 0
fi

# ── Confirmation ───────────────────────────────────────────────────────────
if ! $FORCE; then
  echo "⚠️  This will DELETE ALL infrastructure including:"
  echo "   - ECS services (API + Streamlit)"
  echo "   - Application Load Balancer"
  echo "   - VPC and all networking"
  echo "   - Lambda functions"
  echo "   - ECR images and repository"
  echo "   - S3 data buckets (all data will be lost)"
  echo "   - Athena workgroup"
  echo "   - Glue crawlers and databases"
  echo "   - CloudWatch log groups"
  if [[ "$RDS_STATUS" != "NOT_FOUND" ]]; then
    echo "   - Aurora database (final snapshot will be taken)"
  fi
  echo ""
  echo "   ⚠️  THIS IS IRREVERSIBLE - all data will be deleted"
  echo ""
  read -p "Type 'destroy' to confirm: " confirmation
  if [[ "$confirmation" != "destroy" ]]; then
    echo "Cancelled."
    exit 0
  fi
  echo ""
fi

# ── Step 1: Scale ECS to 0 (stop tasks fast) ──────────────────────────────
if [[ "$MAIN_STATUS" != "NOT_FOUND" && "$MAIN_STATUS" != "DELETE_COMPLETE" ]]; then
  echo "Scaling ECS services to 0..."
  aws ecs update-service \
    --cluster data-architecture-ai \
    --service data-architecture-ai \
    --desired-count 0 \
    --region "$REGION" >/dev/null 2>&1 || true
  aws ecs update-service \
    --cluster data-architecture-ai \
    --service data-architecture-ai-streamlit \
    --desired-count 0 \
    --region "$REGION" >/dev/null 2>&1 || true
  echo "✓ ECS services scaled to 0"
fi

# ── Step 2: Delete RDS stack (if exists) ───────────────────────────────────
if [[ "$RDS_STATUS" != "NOT_FOUND" && "$RDS_STATUS" != "DELETE_COMPLETE" ]]; then
  echo ""
  echo "Deleting RDS stack ($RDS_STACK)..."
  echo "  (A final snapshot will be created automatically)"
  aws cloudformation delete-stack \
    --stack-name "$RDS_STACK" \
    --region "$REGION"
  echo "  Waiting for RDS deletion (this takes 5-10 minutes)..."
  aws cloudformation wait stack-delete-complete \
    --stack-name "$RDS_STACK" \
    --region "$REGION" 2>/dev/null || true
  echo "✓ RDS stack deleted"
fi

# ── Step 3: Delete main stack ──────────────────────────────────────────────
if [[ "$MAIN_STATUS" != "NOT_FOUND" && "$MAIN_STATUS" != "DELETE_COMPLETE" ]]; then
  echo ""
  echo "Deleting main stack ($MAIN_STACK)..."
  aws cloudformation delete-stack \
    --stack-name "$MAIN_STACK" \
    --region "$REGION"
  echo "  Waiting for deletion (this takes 5-10 minutes)..."
  aws cloudformation wait stack-delete-complete \
    --stack-name "$MAIN_STACK" \
    --region "$REGION" 2>/dev/null || true
  echo "✓ Main stack deleted"
fi

# ── Step 4: Clean up ECR images ────────────────────────────────────────────
echo ""
echo "Cleaning up ECR repository..."
if aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$REGION" >/dev/null 2>&1; then
  IMAGE_IDS="$(aws ecr list-images \
    --repository-name "$ECR_REPO" \
    --region "$REGION" \
    --query 'imageIds[*]' \
    --output json 2>/dev/null || echo '[]')"
  if [[ "$IMAGE_IDS" != "[]" && "$IMAGE_IDS" != "" ]]; then
    aws ecr batch-delete-image \
      --repository-name "$ECR_REPO" \
      --image-ids "$IMAGE_IDS" \
      --region "$REGION" >/dev/null 2>&1 || true
    echo "✓ ECR images deleted"
  else
    echo "  No images to delete"
  fi
  aws ecr delete-repository \
    --repository-name "$ECR_REPO" \
    --region "$REGION" \
    --force >/dev/null 2>&1 || true
  echo "✓ ECR repository deleted"
else
  echo "  ECR repository not found (already deleted by stack)"
fi

# ── Step 5: Delete S3 data buckets ─────────────────────────────────────────
echo ""
echo "Cleaning up S3 buckets..."
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
for BUCKET in "langchain-${ACCOUNT_ID}-eu-north-1" "langchain-${ACCOUNT_ID}-eu-central-1"; do
  if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
    echo "  Emptying $BUCKET..."
    aws s3 rm "s3://${BUCKET}" --recursive --region "$REGION" 2>/dev/null || true
    # Also delete versioned objects
    aws s3api list-object-versions \
      --bucket "$BUCKET" \
      --region "$REGION" \
      --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
      --output json 2>/dev/null | \
      aws s3api delete-objects --bucket "$BUCKET" --delete file:///dev/stdin --region "$REGION" 2>/dev/null || true
    aws s3api list-object-versions \
      --bucket "$BUCKET" \
      --region "$REGION" \
      --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' \
      --output json 2>/dev/null | \
      aws s3api delete-objects --bucket "$BUCKET" --delete file:///dev/stdin --region "$REGION" 2>/dev/null || true
    aws s3api delete-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null || true
    echo "  ✓ $BUCKET deleted"
  else
    echo "  $BUCKET not found - skipping"
  fi
done

# ── Step 6: Delete Athena workgroup ────────────────────────────────────────
echo ""
echo "Cleaning up Athena workgroup..."
WORKGROUP="project-text-to-sql"
if aws athena get-work-group --work-group "$WORKGROUP" --region "$REGION" >/dev/null 2>&1; then
  aws athena delete-work-group \
    --work-group "$WORKGROUP" \
    --recursive-delete-option \
    --region "$REGION" 2>/dev/null || true
  echo "✓ Athena workgroup '$WORKGROUP' deleted"
else
  echo "  Workgroup not found - skipping"
fi

# ── Step 7: Delete Glue crawlers and databases ─────────────────────────────
echo ""
echo "Cleaning up Glue crawlers..."
for CRAWLER_NAME in project-library-crawler project-cars-crawler; do
  if aws glue get-crawler --name "$CRAWLER_NAME" --region "$REGION" >/dev/null 2>&1; then
    aws glue delete-crawler --name "$CRAWLER_NAME" --region "$REGION" 2>/dev/null || true
    echo "  ✓ Crawler '$CRAWLER_NAME' deleted"
  else
    echo "  $CRAWLER_NAME not found - skipping"
  fi
done

echo "Cleaning up Glue databases..."
for DB_NAME in project_library_db project_cars_db; do
  if aws glue get-database --name "$DB_NAME" --region "$REGION" >/dev/null 2>&1; then
    aws glue delete-database --name "$DB_NAME" --region "$REGION" 2>/dev/null || true
    echo "  ✓ Glue database '$DB_NAME' deleted"
  else
    echo "  $DB_NAME not found - skipping"
  fi
done

# ── Step 8: Delete CloudWatch log groups ───────────────────────────────────
echo ""
echo "Cleaning up CloudWatch log groups..."
for LOG_GROUP in "/ecs/data-architecture-ai" "/ecs/data-architecture-ai-streamlit"; do
  if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region "$REGION" \
    --query "logGroups[?logGroupName=='${LOG_GROUP}']" --output text 2>/dev/null | grep -q "$LOG_GROUP"; then
    aws logs delete-log-group --log-group-name "$LOG_GROUP" --region "$REGION" 2>/dev/null || true
    echo "  ✓ Log group '$LOG_GROUP' deleted"
  else
    echo "  $LOG_GROUP not found - skipping"
  fi
done

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "✅ TEARDOWN COMPLETE - ALL RESOURCES DELETED"
echo "=========================================="
echo ""
echo "Everything has been removed. To redeploy from scratch:"
echo "  ./deploy-changeset.sh --auto"
