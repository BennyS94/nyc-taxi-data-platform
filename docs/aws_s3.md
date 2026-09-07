# AWS S3 durable source storage

S3 is an optional durable backing store for immutable TLC source artifacts. PostgreSQL
remains the operational metadata store and warehouse; local `data/landing/` remains the
validated materialization/cache used by PyArrow and COPY.

## Bucket safeguards

Use one globally unique private bucket. Configure the bucket outside the application with
versioning, all four S3 Block Public Access settings, and default SSE-S3 encryption. For
example, after creating the bucket in the intended region:

```bash
aws s3api put-public-access-block --bucket "$TLC_S3_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket "$TLC_S3_BUCKET" \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$TLC_S3_BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

The normal application principal needs only object access for this bucket and prefix. It
does not need delete or administrative permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::BUCKET_NAME/landing/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::BUCKET_NAME",
      "Condition": {"StringLike": {"s3:prefix": "landing/*"}}
    }
  ]
}
```

Credential resolution uses boto3's normal chain (for example AWS CLI profile/SSO,
externally supplied environment credentials, or a future workload role). Credentials do
not belong in `.env.example`, source code, or Git.

## Immutable layout

Objects are addressed by the application's SHA-256 version identity:

```text
landing/yellow/YYYY/MM/<sha256>.parquet
landing/green/YYYY/MM/<sha256>.parquet
landing/reference/taxi_zones/<sha256>.csv
```

Revised files receive distinct objects but remain subject to the existing registry's
revision-blocking decision. S3 Version IDs are recorded only as infrastructure metadata.
ETags are never used as application checksums.

## Configuration and commands

Local mode remains the default:

```text
LANDING_BACKEND=local
```

S3 mode requires:

```text
LANDING_BACKEND=s3
AWS_REGION=<bucket-region>
TLC_S3_BUCKET=<private-project-bucket>
```

After `alembic upgrade head`, sync registered sources and verify safeguards:

```bash
python -m taxi_pipeline storage check-bucket
python -m taxi_pipeline storage sync --service zones
python -m taxi_pipeline storage sync --service yellow --year 2025 --month 1
python -m taxi_pipeline storage sync --service green --year 2025 --month 1
python -m taxi_pipeline storage verify --source-file-id <id>
```

Uploads reuse a matching checksum-addressed object and fail on metadata or size conflict.
S3 object metadata contains only SHA-256, partition key, dataset name, and service type
when applicable.

## Recovery smoke procedure

For a source whose `ops.source_files` row records an S3 URI:

1. Copy its local landing file somewhere outside the repository as a temporary safety
   backup, then remove only that exact local landing file.
2. Run `python -m taxi_pipeline storage materialize --source-file-id <id>`.
3. Run the normal source inspection or ingestion command.

Materialization writes a `.part` file, validates byte count and SHA-256, and only then
atomically exposes the final landing path. A mismatch removes the partial file and leaves
the final path absent.

## Cost and cleanup

The design has no replication, acceleration, lifecycle experiments, or AWS calls in CI.
To retire the bucket, inspect the `landing/` objects first. Because versioning is enabled,
emptying the visible current objects is insufficient: historical versions and delete
markers must also be removed before deleting the bucket. Cleanup remains an explicit AWS
administrative action and is intentionally absent from the application.
