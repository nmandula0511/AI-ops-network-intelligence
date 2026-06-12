# infra/main.tf
# ==============
# Story 6 — Terraform for Deployment & Gateway Provisioning
#
# Deploys the SmartEdge Gateway Agent as an ECS Fargate service and provisions
# the AWS Bedrock AgentCore MCP Gateway infrastructure.
#
# Usage:
#   terraform init
#   terraform plan -var-file=environments/dev.tfvars
#   terraform apply -var-file=environments/dev.tfvars
#

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "optima-aiops-terraform-state"
    key    = "smartedge-gateway-agent/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# ─────────────────────────────────────────────────────────
# Variables
# ─────────────────────────────────────────────────────────

variable "environment" {
  description = "Deployment environment: DEV, UAT, or PROD"
  type        = string
  validation {
    condition     = contains(["DEV", "UAT", "PROD"], var.environment)
    error_message = "environment must be DEV, UAT, or PROD"
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "container_image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

# ─────────────────────────────────────────────────────────
# Data Sources — Reference Existing Infrastructure
# ─────────────────────────────────────────────────────────

data "aws_vpc" "optima_aiops" {
  tags = { Name = "optima-aiops-vpc-${lower(var.environment)}" }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.optima_aiops.id]
  }
  tags = { Tier = "private" }
}

data "aws_rds_cluster" "telemetry_db" {
  cluster_identifier = "aiops-telemetry-${lower(var.environment)}"
}

data "aws_ecr_repository" "agent" {
  name = "aiops/smartedge-gateway-agent"
}

# ─────────────────────────────────────────────────────────
# ECS Cluster
# ─────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "aiops" {
  name = "optima-aiops-${lower(var.environment)}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ─────────────────────────────────────────────────────────
# ECS Task Definition
# ─────────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "smartedge_gateway_agent" {
  family                   = "smartedge-gateway-agent-${lower(var.environment)}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"   # 1 vCPU
  memory                   = "2048"  # 2 GB RAM
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "smartedge-gateway-agent"
    image = "${data.aws_ecr_repository.agent.repository_url}:${var.container_image_tag}"

    portMappings = [{
      containerPort = 8080
      protocol      = "tcp"
    }]

    environment = [
      { name = "ENV",        value = var.environment },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "LOG_LEVEL",  value = var.environment == "PROD" ? "INFO" : "DEBUG" }
    ]

    # Health check — ECS calls this to check if container is active
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8080/ping || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.agent.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# ─────────────────────────────────────────────────────────
# ECS Service
# ─────────────────────────────────────────────────────────

resource "aws_ecs_service" "smartedge_gateway_agent" {
  name            = "smartedge-gateway-agent-${lower(var.environment)}"
  cluster         = aws_ecs_cluster.aiops.id
  task_definition = aws_ecs_task_definition.smartedge_gateway_agent.arn
  launch_type     = "FARGATE"

  desired_count = var.environment == "PROD" ? 3 : 1

  network_configuration {
    subnets          = data.aws_subnets.private.ids
    security_groups  = [aws_security_group.agent.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.agent.arn
    container_name   = "smartedge-gateway-agent"
    container_port   = 8080
  }

  depends_on = [aws_lb_listener.agent_https]
}

# ─────────────────────────────────────────────────────────
# CloudWatch Logs
# ─────────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "agent" {
  name              = "/ecs/smartedge-gateway-agent-${lower(var.environment)}"
  retention_in_days = var.environment == "PROD" ? 90 : 14
}

# ─────────────────────────────────────────────────────────
# IAM Roles — Least Privilege
# ─────────────────────────────────────────────────────────

resource "aws_iam_role" "ecs_task" {
  name = "smartedge-gateway-agent-task-${lower(var.environment)}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "agent_permissions" {
  name = "agent-permissions"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.nova-pro-v1:0"
      },
      {
        Effect = "Allow"
        Action = [
          "rds-data:ExecuteStatement",
          "rds-data:BatchExecuteStatement"
        ]
        Resource = data.aws_rds_cluster.telemetry_db.arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"]
        Resource = "arn:aws:dynamodb:${var.aws_region}:*:table/aiops-*"
      }
    ]
  })
}

resource "aws_iam_role" "ecs_execution" {
  name = "smartedge-gateway-agent-execution-${lower(var.environment)}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# (Add placeholder security groups & load balancer listeners referenced in service to make Terraform valid)
resource "aws_security_group" "agent" {
  name        = "smartedge-agent-sg"
  vpc_id      = data.aws_vpc.optima_aiops.id
}
resource "aws_lb_target_group" "agent" {
  name        = "smartedge-agent-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.optima_aiops.id
  target_type = "ip"
}
resource "aws_lb_listener" "agent_https" {
  load_balancer_arn = "arn:aws:elasticloadbalancing:${var.aws_region}:123456789012:loadbalancer/app/dummy-lb/12345"
  port              = 443
  protocol          = "HTTPS"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.agent.arn
  }
}


# ─────────────────────────────────────────────────────────
# aws_bedrockagentcore_gateway Provisioning (Repository 3)
# ─────────────────────────────────────────────────────────

resource "aws_bedrockagentcore_gateway" "mcp" {
  name             = "central-mcp-gateway-${lower(var.environment)}"
  protocol         = "MCP"
  authorization    = "AWS_IAM"
  description      = "Secure Model Context Protocol gateway interface for AIOps reasoning models."

  tags = {
    Environment = var.environment
    Service     = "AIOps Gateway"
  }
}

# API Credentials Providers in Secrets Manager
resource "aws_secretsmanager_secret" "target_keys" {
  name        = "aiops/gateway/target-credentials-${lower(var.environment)}"
  description = "Secret API keys used to authorize gateway calls to target services."
}

resource "aws_secretsmanager_secret_version" "target_keys_value" {
  secret_id     = aws_secretsmanager_secret.target_keys.id
  secret_string = jsonencode({
    netsense_core_api_token = "net-token-secure-123",
    docs_rag_token          = "rag-token-secure-456",
    topology_graph_token    = "topo-token-secure-789"
  })
}

# Gateway Targets configurations (3 primary targets mapping OpenAPI specs)
resource "aws_bedrockagentcore_gateway_target" "netsense_core_api" {
  gateway_id = aws_bedrockagentcore_gateway.mcp.id
  name       = "netsense-core-api-target"
  endpoint   = "https://api.netsense.optima.internal/device-feed"
  
  # Inject target OpenAPI spec template config
  openapi_spec = templatefile("${path.module}/openapi/netsense_core_api.json.tftpl", {
    base_url = "https://api.netsense.optima.internal/device-feed"
  })
}

resource "aws_bedrockagentcore_gateway_target" "docs_rag" {
  gateway_id = aws_bedrockagentcore_gateway.mcp.id
  name       = "docs-rag-target"
  endpoint   = "https://rag.kb.optima.internal"
  
  openapi_spec = templatefile("${path.module}/openapi/docs_rag.json.tftpl", {
    base_url = "https://rag.kb.optima.internal"
  })
}

resource "aws_bedrockagentcore_gateway_target" "topology_graph" {
  gateway_id = aws_bedrockagentcore_gateway.mcp.id
  name       = "topology-graph-target"
  endpoint   = "https://topology.graph.optima.internal"
  
  openapi_spec = templatefile("${path.module}/openapi/topology_graph.json.tftpl", {
    base_url = "https://topology.graph.optima.internal"
  })
}
