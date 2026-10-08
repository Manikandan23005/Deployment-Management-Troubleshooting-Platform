#!/usr/bin/env python3
"""
Amazon ECR Image Build and Push Automation for DevOps Nexus Application Suite.
Builds linux/amd64 multi-stage images for microservices and pushes to ECR with immutable tags.
"""
import os
import subprocess
import sys
import json
from typing import List, Dict, Any

AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID", "605294565283")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
ECR_REGISTRY = f"{AWS_ACCOUNT_ID}.dkr.ecr.{AWS_REGION}.amazonaws.com"
RELEASE_TAG = os.getenv("RELEASE_TAG", "1.1.0")

APPLICATIONS = [
    {"name": "auth", "context": "applications/auth", "dockerfile": "applications/auth/Dockerfile"},
    {"name": "users", "context": "applications/users", "dockerfile": "applications/users/Dockerfile"},
    {"name": "products", "context": "applications/products", "dockerfile": "applications/products/Dockerfile"},
    {"name": "orders", "context": "applications/orders", "dockerfile": "applications/orders/Dockerfile"},
    {"name": "payment", "context": "applications/payment", "dockerfile": "applications/payment/Dockerfile"},
    {"name": "notification", "context": "applications/notification", "dockerfile": "applications/notification/Dockerfile"},
    {"name": "gateway", "context": "applications/gateway", "dockerfile": "applications/gateway/Dockerfile"},
    {"name": "frontend", "context": "applications/frontend", "dockerfile": "applications/frontend/Dockerfile"}
]

def run_cmd(cmd: List[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    print(f"🔧 [EXEC] {' '.join(cmd)}")
    res = subprocess.run(cmd, check=check, capture_output=capture, text=True)
    return res

def ecr_login():
    print(f"🔑 Authenticating Docker with Amazon ECR ({ECR_REGISTRY})...")
    login_pw_cmd = ["aws", "ecr", "get-login-password", "--region", AWS_REGION]
    pw_res = subprocess.run(login_pw_cmd, check=True, capture_output=True, text=True)
    password = pw_res.stdout.strip()
    
    login_cmd = [
        "docker", "login",
        "--username", "AWS",
        "--password-stdin",
        ECR_REGISTRY
    ]
    p = subprocess.Popen(login_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = p.communicate(input=password)
    if p.returncode != 0:
        print(f"❌ Docker ECR Login failed: {stderr}")
        sys.exit(1)
    print("✅ Docker successfully authenticated to Amazon ECR.")

def build_and_push_all(dry_run: bool = False):
    print("=================================================================")
    print("🚀 DevOps Nexus ECR Image Build & Push Pipeline")
    print(f"   Registry: {ECR_REGISTRY}")
    print(f"   Release Tag: {RELEASE_TAG}")
    print(f"   Region: {AWS_REGION}")
    print("=================================================================")

    if not dry_run:
        ecr_login()

    results = []
    for app in APPLICATIONS:
        app_name = app["name"]
        repo_name = f"devops-nexus/{app_name}"
        tagged_img = f"{ECR_REGISTRY}/{repo_name}:{RELEASE_TAG}"
        latest_img = f"{ECR_REGISTRY}/{repo_name}:latest"

        print(f"\n📦 Building [{app_name}] -> {tagged_img}")

        if dry_run:
            print(f"   [DRY-RUN] docker build --platform linux/amd64 -f {app['dockerfile']} -t {tagged_img} -t {latest_img} {app['context']}")
            print(f"   [DRY-RUN] docker push {tagged_img}")
            results.append({"app": app_name, "image": tagged_img, "status": "DRY_RUN_SUCCESS"})
            continue

        # 1. Build linux/amd64 image
        build_cmd = [
            "docker", "build",
            "--no-cache",
            "--platform", "linux/amd64",
            "-f", app["dockerfile"],
            "-t", tagged_img,
            "-t", latest_img,
            app["context"]
        ]
        run_cmd(build_cmd)

        # 2. Push immutable tag
        print(f"⬆️ Pushing [{app_name}:{RELEASE_TAG}]...")
        run_cmd(["docker", "push", tagged_img])
        
        # 3. Push latest tag
        run_cmd(["docker", "push", latest_img])

        results.append({
            "app": app_name,
            "image": tagged_img,
            "status": "PUSHED"
        })
        print(f"✅ Successfully built and pushed {repo_name}:{RELEASE_TAG}")

    print("\n=================================================================")
    print("🎉 All 8 DevOps Nexus microservices published to ECR:")
    for r in results:
        print(f"   - {r['app']}: {r['image']}")
    print("=================================================================")

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    build_and_push_all(dry_run=is_dry)
