"""Setup Portfolio DD Knowledge Base — uploads PDFs to S3, creates/syncs Bedrock KB.

Prerequisites:
  - CDK stack deployed (creates DDSourceDocsBucket)
  - PDFs generated in packages/portfolio_dd/source_docs/ (run: python scripts/generate_source_docs.py)

Usage:
  python scripts/setup-dd-knowledge-base.py [--bucket BUCKET_NAME] [--stack STACK_NAME]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import boto3

REGION = os.environ.get("AWS_REGION", "us-west-2")
ACCOUNT = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]

SCRIPT_DIR = Path(__file__).parent
SOURCE_DOCS_DIR = SCRIPT_DIR.parent / "packages" / "portfolio_dd" / "source_docs"

PORTFOLIO_DOC_METADATA = {
    "pf_amp001_pds.pdf": {"portfolio_id": "pf_amp001", "doc_type": "pds"},
    "pf_amp001_quarterly.pdf": {"portfolio_id": "pf_amp001", "doc_type": "quarterly_report"},
    "pf_amp001_ddq.pdf": {"portfolio_id": "pf_amp001", "doc_type": "ddq"},
    "pf_pendal001_pds.pdf": {"portfolio_id": "pf_pendal001", "doc_type": "pds"},
    "pf_pendal001_quarterly.pdf": {"portfolio_id": "pf_pendal001", "doc_type": "quarterly_report"},
    "pf_pendal001_ddq.pdf": {"portfolio_id": "pf_pendal001", "doc_type": "ddq"},
    "pf_macq001_pds.pdf": {"portfolio_id": "pf_macq001", "doc_type": "pds"},
    "pf_macq001_quarterly.pdf": {"portfolio_id": "pf_macq001", "doc_type": "quarterly_report"},
    "pf_aef001_pds.pdf": {"portfolio_id": "pf_aef001", "doc_type": "pds"},
    "pf_aef001_esg.pdf": {"portfolio_id": "pf_aef001", "doc_type": "esg_report"},
    "pf_aef001_ddq.pdf": {"portfolio_id": "pf_aef001", "doc_type": "ddq"},
    "pf_hyperion001_pds.pdf": {"portfolio_id": "pf_hyperion001", "doc_type": "pds"},
    "pf_hyperion001_quarterly.pdf": {"portfolio_id": "pf_hyperion001", "doc_type": "quarterly_report"},
    "pf_hyperion001_ddq.pdf": {"portfolio_id": "pf_hyperion001", "doc_type": "ddq"},
}


def discover_bucket_name(stack_name: str) -> str:
    """Discover DDSourceDocsBucket name from CloudFormation stack outputs."""
    cfn = boto3.client("cloudformation", region_name=REGION)
    try:
        resp = cfn.describe_stacks(StackName=stack_name)
        outputs = resp["Stacks"][0].get("Outputs", [])
        for output in outputs:
            if output["OutputKey"] == "DDSourceDocsBucketName":
                return output["OutputValue"]
    except Exception:
        pass
    raise RuntimeError(
        f"Could not find DDSourceDocsBucketName output in stack '{stack_name}'. "
        "Ensure the CDK stack has been deployed first."
    )


def upload_documents(bucket_name: str):
    """Upload pre-generated PDFs and metadata sidecars to S3."""
    s3 = boto3.client("s3", region_name=REGION)

    if not SOURCE_DOCS_DIR.exists():
        print(f"ERROR: Source docs directory not found: {SOURCE_DOCS_DIR}")
        print("Run 'python scripts/generate_source_docs.py' first.")
        raise SystemExit(1)

    pdf_files = sorted(SOURCE_DOCS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"ERROR: No PDF files found in {SOURCE_DOCS_DIR}")
        raise SystemExit(1)

    print(f"   Uploading {len(pdf_files)} PDFs to s3://{bucket_name}/source_docs/...")
    for pdf_path in pdf_files:
        filename = pdf_path.name
        s3_key = f"source_docs/{filename}"

        s3.upload_file(
            str(pdf_path),
            bucket_name,
            s3_key,
            ExtraArgs={"ContentType": "application/pdf"},
        )

        meta = PORTFOLIO_DOC_METADATA.get(filename)
        if meta:
            doc_id = filename.replace(".pdf", "")
            metadata_obj = {
                "metadataAttributes": {
                    "portfolio_id": meta["portfolio_id"],
                    "doc_id": doc_id,
                    "doc_type": meta["doc_type"],
                }
            }
            metadata_key = f"{s3_key}.metadata.json"
            s3.put_object(
                Bucket=bucket_name,
                Key=metadata_key,
                Body=json.dumps(metadata_obj),
                ContentType="application/json",
            )

        print(f"   Uploaded: {s3_key}")


def ensure_kb_role(bucket_name: str) -> str:
    """Create or reuse the IAM role for the Knowledge Base."""
    role_name = "AmazonBedrockExecutionRoleForKnowledgeBase_dd"
    role_arn = f"arn:aws:iam::{ACCOUNT}:role/{role_name}"

    iam = boto3.client("iam", region_name=REGION)
    try:
        iam.get_role(RoleName=role_name)
        print("   KB role exists")
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="BedrockKBPolicy",
            PolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:GetObject", "s3:ListBucket"],
                        "Resource": [
                            f"arn:aws:s3:::{bucket_name}",
                            f"arn:aws:s3:::{bucket_name}/*",
                        ],
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["bedrock:InvokeModel"],
                        "Resource": ["arn:aws:bedrock:*::foundation-model/*"],
                    },
                ],
            }),
        )
        return role_arn
    except iam.exceptions.NoSuchEntityException:
        pass

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {"StringEquals": {"aws:SourceAccount": ACCOUNT}},
        }],
    }
    iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="Role for Portfolio DD Knowledge Base",
    )
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="BedrockKBPolicy",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:ListBucket"],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{bucket_name}/*",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["bedrock:InvokeModel"],
                    "Resource": ["arn:aws:bedrock:*::foundation-model/*"],
                },
            ],
        }),
    )
    print("   Created KB role")
    time.sleep(10)
    return role_arn


def create_or_get_opensearch_collection(role_arn: str) -> str:
    """Create OpenSearch Serverless collection for the KB vector store."""
    aoss = boto3.client("opensearchserverless", region_name=REGION)
    collection_name = "dd-kb-collection"

    # Check if collection already exists
    try:
        cols = aoss.batch_get_collection(names=[collection_name])
        if cols.get("collectionDetails"):
            col = cols["collectionDetails"][0]
            col_id = col["id"]
            print(f"   Collection exists: {col_id} (status: {col['status']})")
            return f"arn:aws:aoss:{REGION}:{ACCOUNT}:collection/{col_id}"
    except Exception:
        pass

    # Create encryption policy
    try:
        aoss.create_security_policy(
            name="dd-kb-encryption",
            type="encryption",
            policy=json.dumps({
                "Rules": [{"ResourceType": "collection", "Resource": [f"collection/{collection_name}"]}],
                "AWSOwnedKey": True,
            }),
        )
        print("   Created encryption policy")
    except aoss.exceptions.ConflictException:
        print("   Encryption policy exists")

    # Create network policy (public access for demo)
    try:
        aoss.create_security_policy(
            name="dd-kb-network",
            type="network",
            policy=json.dumps([{
                "Rules": [
                    {"ResourceType": "collection", "Resource": [f"collection/{collection_name}"]},
                    {"ResourceType": "dashboard", "Resource": [f"collection/{collection_name}"]},
                ],
                "AllowFromPublic": True,
            }]),
        )
        print("   Created network policy")
    except aoss.exceptions.ConflictException:
        print("   Network policy exists")

    # Create data access policy
    try:
        aoss.create_access_policy(
            name="dd-kb-access",
            type="data",
            policy=json.dumps([{
                "Rules": [
                    {"ResourceType": "index", "Resource": [f"index/{collection_name}/*"], "Permission": ["aoss:CreateIndex", "aoss:UpdateIndex", "aoss:DescribeIndex", "aoss:ReadDocument", "aoss:WriteDocument"]},
                    {"ResourceType": "collection", "Resource": [f"collection/{collection_name}"], "Permission": ["aoss:CreateCollectionItems", "aoss:DescribeCollectionItems", "aoss:UpdateCollectionItems"]},
                ],
                "Principal": [role_arn, f"arn:aws:iam::{ACCOUNT}:role/Admin"],
            }]),
        )
        print("   Created data access policy")
    except aoss.exceptions.ConflictException:
        print("   Data access policy exists")

    # Create collection
    try:
        col_resp = aoss.create_collection(name=collection_name, type="VECTORSEARCH")
        col_id = col_resp["createCollectionDetail"]["id"]
        print(f"   Created collection: {col_id}")
    except aoss.exceptions.ConflictException:
        cols = aoss.batch_get_collection(names=[collection_name])
        col_id = cols["collectionDetails"][0]["id"]
        print(f"   Collection already exists: {col_id}")

    # Wait for collection to become ACTIVE
    print("   Waiting for collection to become ACTIVE (this may take 3-5 minutes)...")
    for i in range(40):
        cols = aoss.batch_get_collection(names=[collection_name])
        status = cols["collectionDetails"][0]["status"]
        if status == "ACTIVE":
            print(f"   Collection ACTIVE after {(i+1)*10}s")
            break
        time.sleep(10)
    else:
        raise RuntimeError("Collection did not become ACTIVE within timeout")

    collection_arn = f"arn:aws:aoss:{REGION}:{ACCOUNT}:collection/{col_id}"

    # Create vector index
    _create_vector_index(cols["collectionDetails"][0]["collectionEndpoint"])

    return collection_arn


def _create_vector_index(endpoint: str):
    """Create the vector index in OpenSearch Serverless."""
    try:
        from opensearchpy import OpenSearch, RequestsHttpConnection
        from requests_aws4auth import AWS4Auth
    except ImportError:
        print("   WARNING: opensearch-py/requests-aws4auth not installed, skipping index creation")
        print("   Install with: pip install opensearch-py requests-aws4auth")
        return

    host = endpoint.replace("https://", "")
    credentials = boto3.Session(region_name=REGION).get_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        REGION,
        "aoss",
        session_token=credentials.token,
    )
    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )
    index_name = "bedrock-knowledge-base-default-index"
    if client.indices.exists(index=index_name):
        print(f"   Vector index '{index_name}' already exists")
        return

    index_body = {
        "settings": {"index": {"knn": True, "knn.algo_param.ef_search": 512}},
        "mappings": {
            "properties": {
                "bedrock-knowledge-base-default-vector": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {"engine": "faiss", "name": "hnsw", "parameters": {"ef_construction": 512, "m": 16}},
                },
                "AMAZON_BEDROCK_TEXT_CHUNK": {"type": "text"},
                "AMAZON_BEDROCK_METADATA": {"type": "text", "index": False},
            }
        },
    }
    client.indices.create(index=index_name, body=index_body)
    print(f"   Created vector index: {index_name}")


def create_or_get_kb(role_arn: str, collection_arn: str) -> str:
    """Create or reuse the Bedrock Knowledge Base."""
    bedrock = boto3.client("bedrock-agent", region_name=REGION)

    existing_kbs = bedrock.list_knowledge_bases()["knowledgeBaseSummaries"]
    dd_kb = next((kb for kb in existing_kbs if kb["name"] == "PortfolioDDKnowledgeBase"), None)

    if dd_kb:
        kb_id = dd_kb["knowledgeBaseId"]
        print(f"   KB already exists: {kb_id}")
        return kb_id

    kb_response = bedrock.create_knowledge_base(
        name="PortfolioDDKnowledgeBase",
        description="Fund documents for Portfolio Due Diligence analysis",
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0",
            },
        },
        storageConfiguration={
            "type": "OPENSEARCH_SERVERLESS",
            "opensearchServerlessConfiguration": {
                "collectionArn": collection_arn,
                "vectorIndexName": "bedrock-knowledge-base-default-index",
                "fieldMapping": {
                    "vectorField": "bedrock-knowledge-base-default-vector",
                    "textField": "AMAZON_BEDROCK_TEXT_CHUNK",
                    "metadataField": "AMAZON_BEDROCK_METADATA",
                },
            },
        },
    )
    kb_id = kb_response["knowledgeBase"]["knowledgeBaseId"]
    print(f"   Created KB: {kb_id}")

    # Wait for KB to become ACTIVE
    for _ in range(20):
        resp = bedrock.get_knowledge_base(knowledgeBaseId=kb_id)
        if resp["knowledgeBase"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    return kb_id


def setup_data_source_and_sync(kb_id: str, bucket_name: str):
    """Create/reuse the S3 data source and start ingestion."""
    bedrock = boto3.client("bedrock-agent", region_name=REGION)

    ds_list = bedrock.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"]
    if ds_list:
        ds_id = ds_list[0]["dataSourceId"]
        print(f"   Data source exists: {ds_id}")
    else:
        ds_response = bedrock.create_data_source(
            knowledgeBaseId=kb_id,
            name="FundDocuments",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {
                    "bucketArn": f"arn:aws:s3:::{bucket_name}",
                    "inclusionPrefixes": ["source_docs/"],
                },
            },
        )
        ds_id = ds_response["dataSource"]["dataSourceId"]
        print(f"   Created data source: {ds_id}")

    print("   Starting ingestion sync...")
    bedrock.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
    print("   Sync started (will complete in 2-5 minutes)")


def save_kb_id_to_ssm(kb_id: str):
    """Persist the KB ID to SSM for CDK to pick up on next deploy."""
    ssm = boto3.client("ssm", region_name=REGION)
    ssm.put_parameter(
        Name="/wealth-management-portal/dd-knowledge-base-id",
        Value=kb_id,
        Type="String",
        Overwrite=True,
    )
    print(f"   Saved to SSM: /wealth-management-portal/dd-knowledge-base-id = {kb_id}")


def main():
    parser = argparse.ArgumentParser(description="Setup Portfolio DD Knowledge Base")
    parser.add_argument("--bucket", help="S3 bucket name (overrides CloudFormation lookup)")
    parser.add_argument("--stack", default="wealth-management-portal-infra-uswest2-Application", help="CloudFormation stack name")
    args = parser.parse_args()

    print("=" * 60)
    print("Portfolio DD Knowledge Base Setup")
    print("=" * 60)

    # 1. Discover bucket
    print("\n1. Discovering S3 bucket...")
    if args.bucket:
        bucket_name = args.bucket
        print(f"   Using provided bucket: {bucket_name}")
    else:
        bucket_name = discover_bucket_name(args.stack)
        print(f"   Found bucket from stack: {bucket_name}")

    # 2. Upload documents
    print("\n2. Uploading source documents...")
    upload_documents(bucket_name)

    # 3. Setup IAM role
    print("\n3. Setting up KB IAM role...")
    role_arn = ensure_kb_role(bucket_name)

    # 4. Create OpenSearch Serverless collection
    print("\n4. Creating/verifying OpenSearch Serverless collection...")
    collection_arn = create_or_get_opensearch_collection(role_arn)

    # Add AOSS permissions to the KB role
    iam = boto3.client("iam", region_name=REGION)
    iam.put_role_policy(
        RoleName="AmazonBedrockExecutionRoleForKnowledgeBase_dd",
        PolicyName="BedrockKBPolicyAOSS",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Action": ["aoss:APIAccessAll"], "Resource": [collection_arn]}],
        }),
    )
    print("   Updated role with AOSS permissions")
    time.sleep(5)

    # 5. Create Knowledge Base
    print("\n5. Creating/verifying Knowledge Base...")
    kb_id = create_or_get_kb(role_arn, collection_arn)

    # 6. Data source and sync
    print("\n6. Setting up data source and starting sync...")
    setup_data_source_and_sync(kb_id, bucket_name)

    # 7. Save to SSM
    print("\n7. Saving KB ID to SSM...")
    save_kb_id_to_ssm(kb_id)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Knowledge Base ID: {kb_id}")
    print(f"S3 Bucket: {bucket_name}")
    print(f"{'=' * 60}")
    print(f"\nNext steps:")
    print(f"1. Wait for sync to complete (~2-5 minutes)")
    print(f"2. Set DD_KNOWLEDGE_BASE_ID={kb_id} in .env")
    print(f"3. Redeploy CDK: cd packages/infra && npx cdk deploy")
    print(f"   This will set BEDROCK_KB_ID on the DDEvidenceGatherer runtime.")


if __name__ == "__main__":
    main()
