# DevOps Nexus — Enterprise Architecture Documentation

Welcome to the **DevOps Nexus Architecture Documentation**. This directory contains complete technical specifications for the DevOps Nexus Enterprise Internal Developer Platform (IDP), Terraform Amazon EKS Infrastructure Foundation, Multi-Account Cloud Integration, GitOps Control Plane, Observability Stack, and Autonomous AIOps Engine.

---

## 📚 Architecture Documentation Index

| Document | Description |
|---|---|
| 🏗️ [System Architecture](file:///Users/manikandansrinivasan/pro/Deployment-Management-Troubleshooting-Platform/architecture/system_architecture.md) | High-level system architecture, AWS account registration, STS cross-account assume-role, EKS discovery, and scope resolution specifications. |
| ☁️ [Terraform EKS Infrastructure](file:///Users/manikandansrinivasan/pro/Deployment-Management-Troubleshooting-Platform/architecture/terraform_architecture.md) | Multi-AZ VPC, subnets, NAT gateways, EKS cluster v1.30, node groups, IAM roles, EKS Access Entries, and add-ons. |
| 🧠 [AIOps Investigation & Remediation Engine](file:///Users/manikandansrinivasan/pro/Deployment-Management-Troubleshooting-Platform/architecture/ai_architecture.md) | Autonomous diagnostic engine architecture (`Planner`, `Scheduler`, `Evidence Graph`, `Correlation Engine`, `Remediation Planner`, `Verification Engine`). |
| 🔄 [GitOps Control Plane](file:///Users/manikandansrinivasan/pro/Deployment-Management-Troubleshooting-Platform/architecture/gitops_architecture.md) | 12-stage Git write-back pipeline, Helm values management, and ArgoCD synchronization specs. |
| 📊 [Observability & Telemetry](file:///Users/manikandansrinivasan/pro/Deployment-Management-Troubleshooting-Platform/architecture/observability_architecture.md) | Prometheus metrics, Loki log streams, K8s event collectors, and zero-degraded fail-safe architecture. |

---

## 🏛️ System Overview

```mermaid
graph TD
    User["👤 Operator"] --> Frontend["🎨 React Frontend"]
    Frontend --> Backend["⚙️ FastAPI Backend"]
    Backend --> ScopeEngine["🎯 Unified Operations Scope Engine (KUBERNETES & AWS_EKS)"]
    Backend --> AWS["☁️ AWS Credential Provider (STS AssumeRole)"]
    Backend --> GitOps["🐙 GitOps Control Plane"]
    Backend --> Telemetry["📊 Prometheus & Loki Stack"]
    Backend --> AIOps["🧠 Autonomous AIOps Engine"]
    
    AWS --> EKSDiscovery["🔍 EKS Discovery"]
    AWS --> K8sFactory["🏭 Dynamic Kubernetes Client Factory"]
    K8sFactory --> EKS["☸️ Amazon EKS Clusters (Terraform Provisioned)"]
    GitOps --> ArgoCD["🔄 ArgoCD"]
    ArgoCD --> K8s["☸️ On-Prem / Local Kubernetes"]
    Telemetry --> K8s
    Telemetry --> EKS
    AIOps --> LLM["🤖 LLM Provider"]
```
