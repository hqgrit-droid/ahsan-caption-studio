"""Optional durable object storage for the free, ephemeral web deployment."""
import os
from pathlib import Path


class CloudStore:
    def __init__(self, root, client=None, bucket=None):
        self.root = Path(root).resolve()
        self.bucket = bucket or os.environ['HF_S3_BUCKET']
        if client is None:
            import boto3
            from botocore.config import Config
            namespace = os.environ['HF_S3_NAMESPACE']
            client = boto3.client(
                's3', endpoint_url=f'https://s3.hf.co/{namespace}',
                aws_access_key_id=os.environ['HF_S3_ACCESS_KEY'],
                aws_secret_access_key=os.environ['HF_S3_SECRET_KEY'],
                config=Config(region_name='us-east-1', s3={'addressing_style': 'path'},
                              request_checksum_calculation='when_required',
                              response_checksum_validation='when_required'))
        self.client = client
        if client.__class__.__module__.startswith('botocore'):
            from boto3.s3.transfer import TransferConfig
            self.transfer = TransferConfig(multipart_threshold=2 * 1024 ** 3,
                                           multipart_chunksize=64 * 1024 ** 2,
                                           max_concurrency=2)
        else:
            self.transfer = None

    def key(self, path):
        relative = Path(path).resolve().relative_to(self.root)
        if not relative.parts or any(part in ('.', '..') for part in relative.parts):
            raise ValueError('Invalid cloud storage path')
        return relative.as_posix()

    def upload(self, path, key=None):
        args = (str(path), self.bucket, key or self.key(path))
        if self.transfer: self.client.upload_file(*args, Config=self.transfer)
        else: self.client.upload_file(*args)

    def download(self, path):
        path = Path(path)
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.download')
        try:
            args = (self.bucket, self.key(path), str(temp))
            if self.transfer: self.client.download_file(*args, Config=self.transfer)
            else: self.client.download_file(*args)
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
        return path

    def head(self, path):
        return self.client.head_object(Bucket=self.bucket, Key=self.key(path))

    def open_range(self, path, start, end):
        return self.client.get_object(Bucket=self.bucket, Key=self.key(path),
                                      Range=f'bytes={start}-{end}')['Body']

    def restore_metadata(self):
        """Restore small records at boot; large videos are fetched only on demand."""
        keys = ('presets.json', 'roman-spellings.json')
        for key in keys:
            path = self.root / key
            try:
                self.download(path)
            except Exception as exc:
                if _missing(exc):
                    continue
                raise
        paginator = self.client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=self.bucket, Prefix='projects/'):
            for item in page.get('Contents', []):
                key = item['Key']
                if key.startswith('projects/') and key.endswith('.json') and '/' not in key[9:]:
                    self.download(self.root / key)


def _missing(exc):
    return getattr(exc, 'response', {}).get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound')


def configured():
    names = ('HF_S3_NAMESPACE', 'HF_S3_BUCKET', 'HF_S3_ACCESS_KEY', 'HF_S3_SECRET_KEY')
    present = [bool(os.environ.get(name)) for name in names]
    if any(present) and not all(present):
        raise ValueError('Set all four HF_S3_* storage variables together')
    return all(present)
