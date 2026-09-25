# --- AWS Account & EKS Integration REST Router ---
from fastapi import APIRouter, Request, HTTPException, status, Query, Depends
from typing import Optional, List, Dict, Any
from app.schemas.responses import BaseResponse
from app.dependencies.auth import get_current_user
from app.aws.models import (
    AWSAccount, 
    AWSAccountRegistrationRequest, 
    AWSConnectionTestResult, 
    EKSCluster
)
from app.aws.account_registry import aws_account_registry
from app.core.logging import logger

router = APIRouter(
    prefix="/api/v1/aws",
    dependencies=[Depends(get_current_user)]
)

@router.post("/accounts", response_model=BaseResponse)
async def register_aws_account(request: Request, body: AWSAccountRegistrationRequest):
    """Registers a new AWS account with a cross-account IAM role ARN for STS AssumeRole."""
    request_id = getattr(request.state, "request_id", None)
    user_dict = get_current_user(request)
    username = user_dict.get("username", "admin")

    try:
        account = aws_account_registry.register_account(body, username=username)
        return BaseResponse(success=True, data=account.model_dump(), request_id=request_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to register AWS account: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/accounts", response_model=BaseResponse)
async def list_aws_accounts(request: Request):
    """Lists all registered AWS accounts with safe connection metadata."""
    request_id = getattr(request.state, "request_id", None)
    accounts = aws_account_registry.list_accounts()
    return BaseResponse(success=True, data=[acc.model_dump() for acc in accounts], request_id=request_id)

@router.get("/accounts/{account_id}", response_model=BaseResponse)
async def get_aws_account(request: Request, account_id: str):
    """Fetches registration metadata for a specific AWS account."""
    request_id = getattr(request.state, "request_id", None)
    account = aws_account_registry.get_account(account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AWS Account '{account_id}' not found.")
    return BaseResponse(success=True, data=account.model_dump(), request_id=request_id)

@router.delete("/accounts/{account_id}", response_model=BaseResponse)
async def delete_aws_account(request: Request, account_id: str):
    """Deletes an AWS account registration and clears cached credentials."""
    request_id = getattr(request.state, "request_id", None)
    user_dict = get_current_user(request)
    username = user_dict.get("username", "admin")

    deleted = aws_account_registry.delete_account(account_id, username=username)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AWS Account '{account_id}' not found.")
    return BaseResponse(success=True, data={"deleted": True, "account_id": account_id}, request_id=request_id)

@router.post("/accounts/{account_id}/test", response_model=BaseResponse)
async def test_aws_account_connection(request: Request, account_id: str):
    """Performs STS AssumeRole validation and confirms caller identity against the registered account ID."""
    request_id = getattr(request.state, "request_id", None)
    user_dict = get_current_user(request)
    username = user_dict.get("username", "admin")

    try:
        test_res = aws_account_registry.test_connection(account_id, username=username)
        return BaseResponse(success=True, data=test_res.model_dump(), request_id=request_id)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"AWS connection test error for '{account_id}': {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/accounts/{account_id}/clusters", response_model=BaseResponse)
async def discover_eks_clusters(
    request: Request,
    account_id: str,
    region: Optional[str] = Query(None, description="Optional AWS region override.")
):
    """Discovers Amazon EKS clusters available in the target AWS account."""
    request_id = getattr(request.state, "request_id", None)
    try:
        clusters = aws_account_registry.discover_clusters(account_id, region=region)
        return BaseResponse(success=True, data=[c.model_dump() for c in clusters], request_id=request_id)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"EKS discovery error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/accounts/{account_id}/clusters/{cluster_name}/register", response_model=BaseResponse)
async def register_eks_cluster_target(
    request: Request,
    account_id: str,
    cluster_name: str,
    region: Optional[str] = Query(None)
):
    """Registers a discovered Amazon EKS cluster into the Multi-Cluster Registry as an execution target."""
    request_id = getattr(request.state, "request_id", None)
    try:
        registered = aws_account_registry.register_eks_cluster_as_target(
            account_identifier=account_id,
            cluster_name=cluster_name,
            region=region
        )
        return BaseResponse(success=True, data=registered, request_id=request_id)
    except Exception as e:
        logger.error(f"Failed to register EKS cluster '{cluster_name}' as target: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
