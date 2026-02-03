"""Blob storage abstraction layer for S3 and compatible services."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, BinaryIO, Optional

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class BlobStorage(ABC):
    """
    Abstract interface for blob storage.
    
    Allows swapping S3 for other providers (GCS, Azure Blob, MinIO)
    by implementing this interface.
    """

    @abstractmethod
    def upload_json(self, key: str, data: dict[str, Any]) -> str:
        """
        Upload JSON data to storage.
        
        Args:
            key: Storage key/path
            data: Dictionary to serialize as JSON
            
        Returns:
            The storage key
        """
        pass

    @abstractmethod
    def download_json(self, key: str) -> dict[str, Any]:
        """
        Download and parse JSON from storage.
        
        Args:
            key: Storage key/path
            
        Returns:
            Parsed JSON as dictionary
        """
        pass

    @abstractmethod
    def upload_file(self, key: str, file_obj: BinaryIO, content_type: str) -> str:
        """
        Upload binary file to storage.
        
        Args:
            key: Storage key/path
            file_obj: File-like object to upload
            content_type: MIME type of the file
            
        Returns:
            The storage key
        """
        pass

    @abstractmethod
    def download_file(self, key: str) -> bytes:
        """
        Download file content from storage.
        
        Args:
            key: Storage key/path
            
        Returns:
            File content as bytes
        """
        pass

    @abstractmethod
    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generate a pre-signed URL for downloading.
        
        Args:
            key: Storage key/path
            expires_in: URL expiration time in seconds
            
        Returns:
            Pre-signed download URL
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete object from storage.
        
        Args:
            key: Storage key/path
            
        Returns:
            True if deleted successfully
        """
        pass

    @abstractmethod
    def get_object_size(self, key: str) -> Optional[int]:
        """
        Get object size in bytes.
        
        Args:
            key: Storage key/path
            
        Returns:
            Size in bytes, or None if object doesn't exist
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if object exists.
        
        Args:
            key: Storage key/path
            
        Returns:
            True if object exists
        """
        pass


class S3Storage(BlobStorage):
    """Amazon S3 (and compatible) storage implementation."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        public_endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        """
        Initialize S3 storage client.
        
        Args:
            bucket_name: S3 bucket name (defaults to settings)
            region: AWS region (defaults to settings)
            endpoint_url: Custom endpoint for S3-compatible services (internal)
            public_endpoint_url: Public endpoint for pre-signed URLs (external access)
            aws_access_key_id: AWS access key (defaults to settings or IAM role)
            aws_secret_access_key: AWS secret key (defaults to settings or IAM role)
        """
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME
        self.region = region or settings.S3_REGION
        
        # Build client configuration for internal operations
        client_kwargs = {"region_name": self.region}
        
        if endpoint_url or settings.S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = endpoint_url or settings.S3_ENDPOINT_URL
        
        if aws_access_key_id or settings.AWS_ACCESS_KEY_ID:
            client_kwargs["aws_access_key_id"] = aws_access_key_id or settings.AWS_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = (
                aws_secret_access_key or settings.AWS_SECRET_ACCESS_KEY
            )
        
        self.s3_client = boto3.client("s3", **client_kwargs)
        
        # Create a separate client for generating public pre-signed URLs
        # This uses the public endpoint URL that's accessible from outside Docker
        public_url = public_endpoint_url or settings.S3_PUBLIC_ENDPOINT_URL
        if public_url:
            public_client_kwargs = client_kwargs.copy()
            public_client_kwargs["endpoint_url"] = public_url
            self.s3_public_client = boto3.client("s3", **public_client_kwargs)
        else:
            self.s3_public_client = self.s3_client

    @staticmethod
    def build_simulation_key(user_id: str, job_id: str, filename: str) -> str:
        """Build S3 key for simulation files."""
        return f"simulations/{user_id}/{job_id}/{filename}"

    @staticmethod
    def build_report_key(user_id: str, report_id: str, filename: str) -> str:
        """Build S3 key for report files."""
        return f"reports/{user_id}/{report_id}/{filename}"

    def upload_json(self, key: str, data: dict[str, Any]) -> str:
        """Upload JSON data to S3."""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(data, default=str).encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"Uploaded JSON to s3://{self.bucket_name}/{key}")
            return key
        except ClientError as e:
            logger.error(f"Failed to upload JSON to S3: {e}")
            raise

    def download_json(self, key: str) -> dict[str, Any]:
        """Download and parse JSON from S3."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            content = response["Body"].read().decode("utf-8")
            return json.loads(content)
        except ClientError as e:
            logger.error(f"Failed to download JSON from S3: {e}")
            raise

    def upload_file(self, key: str, file_obj: BinaryIO, content_type: str) -> str:
        """Upload binary file to S3."""
        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            logger.info(f"Uploaded file to s3://{self.bucket_name}/{key}")
            return key
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise

    def download_file(self, key: str) -> bytes:
        """Download file content from S3."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed URL for downloading (uses public endpoint)."""
        try:
            # Use the public client so URLs are accessible from outside Docker
            url = self.s3_public_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    def delete(self, key: str) -> bool:
        """Delete object from S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted s3://{self.bucket_name}/{key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete from S3: {e}")
            return False

    def get_object_size(self, key: str) -> Optional[int]:
        """Get object size in bytes."""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return response["ContentLength"]
        except ClientError:
            return None

    def exists(self, key: str) -> bool:
        """Check if object exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False
