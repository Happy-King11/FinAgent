"""S3-compatible object storage factory and bucket probe."""

from app.core.config import get_settings
from app.infrastructure.object_storage.s3 import S3ObjectStorage


def create_object_storage() -> S3ObjectStorage:
    import boto3

    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        region_name="us-east-1",
    )
    return S3ObjectStorage(client, settings.object_storage_bucket)


def check_object_storage() -> bool:
    try:
        storage = create_object_storage()
        storage.client.head_bucket(Bucket=storage.bucket)
        return True
    except Exception:  # noqa: BLE001 - readiness should report dependency failure.
        return False
