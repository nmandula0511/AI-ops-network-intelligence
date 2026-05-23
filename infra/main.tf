# infra/main.tf
# ==============
# Story 6 — Terraform for Deployment
#
# Deploys the Invincible WiFi Agent as an ECS Fargate service.
# Replaces the old Lambda + API Gateway deployment.
#
# Usage:
#   terraform init
#   terraform plan -var-file=environments/dev.tfvars
#   terraform apply -var-file=environments/dev.tfvars
#
# AI IDE NOTE:
#   - No Lambda resource here — Lambda is intentionally removed (Story 5)
#   - No API Gateway resource — also removed
#   - Agent runs as ECS Fargate container on port 8080
#   - ECS calls /health endpoint every 30 seconds
#   - Aurora/DynamoDB/Neptune are pre-existing — referenced via data sources

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "charter-aiops-terraform-state"
    key    = "invincible-wifi-agent/terraform.tfstate"
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

data "aws_vpc" "charter_aiops" {
  tags = { Name = "charter-aiops-vpc-${lower(var.environment)}" }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.charter_aiops.id]
  }
  tags = { Tier = "private" }
}

data "aws_rds_cluster" "aurora" {
  cluster_identifier = "aiops-aurora-${lower(var.environment)}"
}

data "aws_ecr_repository" "agent" {
  name = "aiops/invincible-wifi-agent"
}

# ─────────────────────────────────────────────────────────
# ECS Cluster
# ─────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "aiops" {
  name = "charter-aiops-${lower(var.environment)}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ─────────────────────────────────────────────────────────
# ECS Task Definition
# (replaces Lambda function definition)
# ─────────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "invincible_wifi_agent" {
  family                   = "invincible-wifi-agent-${lower(var.environment)}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"   # 1 vCPU
  memory                   = "2048"  # 2 GB RAM
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "invincible-wifi-agent"
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

    # Health check — ECS calls this to know if container is healthy
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
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
# (replaces API Gateway + Lambda trigger)
# ─────────────────────────────────────────────────────────

resource "aws_ecs_service" "invincible_wifi_agent" {
  name            = "invincible-wifi-agent-${lower(var.environment)}"
  cluster         = aws_ecs_cluster.aiops.id
  task_definition = aws_ecs_task_definition.invincible_wifi_agent.arn
  launch_type     = "FARGATE"

  # PROD gets 3 replicas for high availability; DEV/UAT get 1
  desired_count = var.environment == "PROD" ? 3 : 1

  network_configuration {
    subnets          = data.aws_subnets.private.ids
    security_groups  = [aws_security_group.agent.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.agent.arn
    container_name   = "invincible-wifi-agent"
    container_port   = 8080
  }

  depends_on = [aws_lb_listener.agent_https]
}

# ─────────────────────────────────────────────────────────
# CloudWatch Logs
# ─────────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "agent" {
  name              = "/ecs/invincible-wifi-agent-${lower(var.environment)}"
  retention_in_days = var.environment == "PROD" ? 90 : 14
}

# ─────────────────────────────────────────────────────────
# IAM Roles — Least Privilege
# ─────────────────────────────────────────────────────────

resource "aws_iam_role" "ecs_task" {
  name = "invincible-wifi-agent-task-${lower(var.environment)}"

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
        Resource = data.aws_rds_cluster.aurora.arn
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
  name = "invincible-wifi-agent-execution-${lower(var.environment)}"

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
