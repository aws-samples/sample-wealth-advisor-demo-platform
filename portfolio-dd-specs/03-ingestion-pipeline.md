Continuing the generator script from the cut point, then completing the remaining spec sections.

---

### Generator script — remainder of `upload_to_s3` and `main`

```python
            key = f"{prefix}/{portfolio_id}/extracted/{doc_type}.json"
            body = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
            s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
            print(f"  s3://{bucket}/{key}")
            total += 1
    print(f"\nUploaded {total} files to s3://{bucket}/{prefix}/")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic due diligence demo data")
    parser.add_argument("--bucket", help="S3 bucket name")
    parser.add_argument("--prefix", default="portfolios", help="S3 key prefix (default: portfolios)")
    parser.add_argument("--local-only", action="store_true", help="Write files locally only, skip S3")
    parser.add_argument("--output-dir", default="./demo_data", help="Local output directory")
    args = parser.parse_args()

    print("Generating synthetic extracted JSON for all 5 portfolios...")
    data = generate_all()

    total_docs = sum(len(docs) for docs in data.values())
    total_pages = sum(
        len(doc["pages"])
        for docs in data.values()
        for doc in docs.values()
    )
    print(f"Generated {total_docs} documents across {len(data)} portfolios ({total_pages} pages total)\n")

    print(f"Writing local files to {args.output_dir}/")
    write_local(data, args.output_dir)

    if not args.local_only:
        if not args.bucket:
            parser.error("--bucket is required unless --local-only is set")
        print(f"\nUploading to S3...")
        upload_to_s3(data, args.bucket, args.prefix)

    print("\nDone.")


if __name__ == "__main__":
    main()
```

**Run command:**
```bash
# Local only (no AWS credentials needed):
python generate_demo_data.py --local-only --output-dir ./demo_data

# With S3 upload:
python generate_demo_data.py --bucket my-demo-bucket --prefix portfolios
```

---

## 7. Demo Mode: KB Indexer

This script reads the extracted JSON files from S3, chunks them, assigns metadata (including `criterion_category` tags), and uploads chunk + sidecar metadata files to the Bedrock KB data source prefix.

```python
#!/usr/bin/env python3
"""
kb_indexer.py

Reads extracted JSON from S3, produces chunked text + metadata sidecar files,
and uploads them to the Bedrock Knowledge Base data source prefix.

After running, trigger a KB sync:
    aws bedrock-agent start-ingestion-job \
        --knowledge-base-id $KB_ID \
        --data-source-id $DS_ID

Usage:
    python kb_indexer.py \
        --bucket my-demo-bucket \
        --extracted-prefix portfolios \
        --kb-prefix kb-data-source \
        --region ap-southeast-2

Requirements:
    pip install boto3 tiktoken
"""

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Optional

import boto3
import tiktoken

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHUNK_TARGET_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64
CHUNK_MIN_TOKENS = 100
MAX_CHUNKS_PER_DOC = 50

PORTFOLIOS = ["AMP_GROWTH", "PENDAL_AEQ", "MACQ_INCOME", "AEF_BALANCED", "HYPERION_AGF"]
DOC_TYPES = ["fund_factsheet", "pds", "im_submission", "performance_data", "meeting_transcript"]

# Section title keywords → criterion_category mapping (evaluated in order)
CRITERION_RULES = [
    ("fees_costs", [
        "fee", "cost", "icr", "mer", "management cost", "performance fee",
        "buy/sell", "spread", "total cost", "management charge",
    ]),
    ("esg_integration", [
        "esg", "responsible", "ethical", "sustainable", "climate", "engagement",
        "exclusion", "unpri", "impact", "stewardship", "carbon", "green bond",
    ]),
    ("risk_management", [
        "risk", "drawdown", "liquidity", "stress", "volatility", "tracking error",
        "var ", "maximum drawdown", "limit", "breach", "compliance",
    ]),
    ("operational_strength", [
        "operation", "custody", "valuation", "bcp", "isae", "audit", "soc 2",
        "administrator", "reconcil", "business continuity", "governance",
    ]),
    ("investment_process", [
        "investment process", "philosophy", "stock selection", "portfolio construction",
        "research", "conviction", "idea generation", "thesis", "team", "analyst",
    ]),
]

# Default category mapping by doc_type for pages that don't match keyword rules
DOC_TYPE_DEFAULT_CATEGORIES = {
    "fund_factsheet":    ["investment_process", "fees_costs"],
    "pds":               ["risk_management", "operational_strength"],
    "im_submission":     ["investment_process", "esg_integration"],
    "performance_data":  ["risk_management", "investment_process"],
    "meeting_transcript":["investment_process", "risk_management"],
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    portfolio_id: str
    fund_name: str
    doc_type: str
    source_document: str
    page_number: int
    section_title: str
    chunk_index: int
    chunk_total: int        # filled in after all chunks for this page are known
    document_date: str
    criterion_categories: list
    has_tables: bool
    table_ids: list
    extraction_mode: str
    asset_class: str
    text: str               # the actual chunk content


# ---------------------------------------------------------------------------
# Tokeniser (cl100k_base matches Titan Embeddings v2 tokenisation closely)
# ---------------------------------------------------------------------------

_enc = tiktoken.get_encoding("cl100k_base")


def token_count(text: str) -> int:
    return len(_enc.encode(text))


def token_split(text: str, max_tokens: int, overlap: int) -> list:
    """Split text into overlapping token windows, respecting sentence boundaries."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current_tokens = []
    current_sentences = []

    for sentence in sentences:
        s_tokens = _enc.encode(sentence)
        if len(current_tokens) + len(s_tokens) > max_tokens and current_sentences:
            chunk_text = " ".join(current_sentences)
            if token_count(chunk_text) >= CHUNK_MIN_TOKENS:
                chunks.append(chunk_text)
            # retain overlap: keep last N tokens worth of sentences
            overlap_sentences = []
            overlap_token_count = 0
            for s in reversed(current_sentences):
                s_toks = len(_enc.encode(s))
                if overlap_token_count + s_toks <= overlap:
                    overlap_sentences.insert(0, s)
                    overlap_token_count += s_toks
                else:
                    break
            current_sentences = overlap_sentences + [sentence]
            current_tokens = _enc.encode(" ".join(current_sentences))
        else:
            current_sentences.append(sentence)
            current_tokens.extend(s_tokens)

    if current_sentences:
        remainder = " ".join(current_sentences)
        if token_count(remainder) >= CHUNK_MIN_TOKENS:
            chunks.append(remainder)

    return chunks if chunks else [text]


# ---------------------------------------------------------------------------
# Table serialiser
# ---------------------------------------------------------------------------

def serialise_table(t: dict) -> str:
    title = t.get("table_title", t.get("table_id", "Table"))
    headers = t.get("headers", [])
    rows = t.get("rows", [])
    lines = [f"[TABLE: {title}]"]
    if headers:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    lines.append("[END TABLE]")
    return "\n".join(lines)


def serialise_kvs(kvs: list) -> str:
    if not kvs:
        return ""
    parts = [f'{kv["key"]}: {kv["value"]}' for kv in kvs]
    return "KEY FACTS: " + "; ".join(parts)


# ---------------------------------------------------------------------------
# Criterion category assignment
# ---------------------------------------------------------------------------

def assign_criterion_categories(section_title: str, content: str, doc_type: str) -> list:
    haystack = (section_title + " " + content[:500]).lower()
    matched = []
    for category, keywords in CRITERION_RULES:
        if any(kw in haystack for kw in keywords):
            matched.append(category)
    if not matched:
        matched = DOC_TYPE_DEFAULT_CATEGORIES.get(doc_type, ["investment_process"])
    # deduplicate while preserving order
    seen = set()
    result = []
    for c in matched:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


# ---------------------------------------------------------------------------
# Core chunker
# ---------------------------------------------------------------------------

def chunk_document(doc: dict) -> list:
    portfolio_id = doc["portfolio_id"]
    doc_type = doc["doc_type"]
    source_document = doc["source_document"]
    extraction_mode = doc["extraction_mode"]
    doc_meta = doc.get("doc_metadata", {})
    fund_name = doc_meta.get("fund_name", portfolio_id)
    document_date = doc_meta.get("document_date", "")
    asset_class = doc_meta.get("asset_class", "")

    all_chunks = []

    for pg in doc.get("pages", []):
        page_number = pg.get("page_number", 0)
        section_title = pg.get("section_title", "")
        content = pg.get("content", "")
        tables = pg.get("tables", [])
        kvs = pg.get("key_value_pairs", [])

        # Build full page text
        table_text = "\n\n".join(serialise_table(t) for t in tables)
        kv_text = serialise_kvs(kvs)
        section_header = f"[{section_title}]\n" if section_title else ""
        full_text = section_header + content
        if table_text:
            full_text += "\n\n" + table_text
        if kv_text:
            full_text += "\n\n" + kv_text

        # Assign criterion categories
        criterion_categories = assign_criterion_categories(section_title, content, doc_type)
        has_tables = len(tables) > 0
        table_ids = [t.get("table_id", "") for t in tables]

        # Split into chunks if needed
        if token_count(full_text) <= CHUNK_TARGET_TOKENS:
            text_chunks = [full_text]
        else:
            text_chunks = token_split(full_text, CHUNK_TARGET_TOKENS, CHUNK_OVERLAP_TOKENS)

        # Enforce max chunks per document across all pages
        remaining_capacity = MAX_CHUNKS_PER_DOC - len(all_chunks)
        text_chunks = text_chunks[:remaining_capacity]

        page_chunks = []
        for i, text in enumerate(text_chunks):
            page_chunks.append(Chunk(
                portfolio_id=portfolio_id,
                fund_name=fund_name,
                doc_type=doc_type,
                source_document=source_document,
                page_number=page_number,
                section_title=section_title,
                chunk_index=i + 1,
                chunk_total=0,          # backfill below
                document_date=document_date,
                criterion_categories=criterion_categories,
                has_tables=has_tables,
                table_ids=table_ids,
                extraction_mode=extraction_mode,
                asset_class=asset_class,
                text=text,
            ))

        # Backfill chunk_total for this page
        for c in page_chunks:
            c.chunk_total = len(page_chunks)

        all_chunks.extend(page_chunks)
        if len(all_chunks) >= MAX_CHUNKS_PER_DOC:
            break

    return all_chunks


# ---------------------------------------------------------------------------
# S3 upload helpers
# ---------------------------------------------------------------------------

def chunk_s3_key(prefix: str, portfolio_id: str, doc_type: str,
                 page_number: int, chunk_index: int) -> str:
    """Returns the S3 key for a chunk's text file."""
    filename = f"{doc_type}_p{page_number:03d}_c{chunk_index:03d}.txt"
    return f"{prefix}/{portfolio_id}/chunks/{filename}"


def metadata_s3_key(text_key: str) -> str:
    """Bedrock KB expects sidecar metadata at <key>.metadata.json"""
    return text_key + ".metadata.json"


def upload_chunks(s3_client, bucket: str, kb_prefix: str, chunks: list):
    """Upload chunk text + metadata sidecar to S3."""
    for chunk in chunks:
        text_key = chunk_s3_key(
            kb_prefix, chunk.portfolio_id, chunk.doc_type,
            chunk.page_number, chunk.chunk_index
        )
        meta_key = metadata_s3_key(text_key)

        # Text file
        s3_client.put_object(
            Bucket=bucket,
            Key=text_key,
            Body=chunk.text.encode("utf-8"),
            ContentType="text/plain",
        )

        # Metadata sidecar (Bedrock KB custom metadata format)
        metadata = {
            "metadataAttributes": {
                "portfolio_id":         {"value": {"stringValue": chunk.portfolio_id}},
                "fund_name":            {"value": {"stringValue": chunk.fund_name}},
                "doc_type":             {"value": {"stringValue": chunk.doc_type}},
                "source_document":      {"value": {"stringValue": chunk.source_document}},
                "page_number":          {"value": {"numberValue": chunk.page_number}},
                "section_title":        {"value": {"stringValue": chunk.section_title}},
                "chunk_index":          {"value": {"numberValue": chunk.chunk_index}},
                "chunk_total":          {"value": {"numberValue": chunk.chunk_total}},
                "document_date":        {"value": {"stringValue": chunk.document_date}},
                "criterion_category":   {"value": {"stringValue": chunk.criterion_categories[0]}},
                "criterion_categories": {"value": {"stringValue": ",".join(chunk.criterion_categories)}},
                "has_tables":           {"value": {"booleanValue": chunk.has_tables}},
                "asset_class":          {"value": {"stringValue": chunk.asset_class}},
                "extraction_mode":      {"value": {"stringValue": chunk.extraction_mode}},
            }
        }
        s3_client.put_object(
            Bucket=bucket,
            Key=meta_key,
            Body=json.dumps(metadata, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

    return len(chunks)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Index extracted JSON into Bedrock KB data source")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--extracted-prefix", default="portfolios")
    parser.add_argument("--kb-prefix", default="kb-data-source")
    parser.add_argument("--region", default="ap-southeast-2")
    parser.add_argument("--portfolio", help="Index a single portfolio ID (default: all)")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=args.region)
    portfolios = [args.portfolio] if args.portfolio else PORTFOLIOS

    total_chunks = 0
    for portfolio_id in portfolios:
        for doc_type in DOC_TYPES:
            key = f"{args.extracted_prefix}/{portfolio_id}/extracted/{doc_type}.json"
            try:
                resp = s3.get_object(Bucket=args.bucket, Key=key)
                doc = json.loads(resp["Body"].read())
            except s3.exceptions.NoSuchKey:
                print(f"  SKIP (not found): s3://{args.bucket}/{key}")
                continue

            chunks = chunk_document(doc)
            uploaded = upload_chunks(s3, args.bucket, args.kb_prefix, chunks)
            total_chunks += uploaded
            print(f"  {portfolio_id}/{doc_type}: {len(doc['pages'])} pages → {uploaded} chunks")

    print(f"\nTotal chunks uploaded: {total_chunks}")
    print(f"\nNext step — trigger KB ingestion:")
    print(f"  aws bedrock-agent start-ingestion-job \\")
    print(f"      --knowledge-base-id $KB_ID \\")
    print(f"      --data-source-id $DS_ID \\")
    print(f"      --region {args.region}")


if __name__ == "__main__":
    main()
```

---

## 8. Production Mode: Pipeline Architecture

This section describes the full pipeline for when real documents are uploaded. No implementation is required for the demo.

### 8.1 Trigger Flow

```
┌──────────────┐     S3 PutObject      ┌─────────────────────────┐
│  Analyst UI  │ ──────────────────→   │  s3://bucket/portfolios/ │
│  (upload)    │                       │  {id}/raw/{doc}          │
└──────────────┘                       └────────────┬────────────┘
                                                    │ S3 Event Notification
                                                    ▼
                                       ┌─────────────────────────┐
                                       │  Lambda: dispatch_extract│
                                       │  - reads object key      │
                                       │  - determines doc_type   │
                                       │  - routes to extractor   │
                                       └────────────┬────────────┘
                              ┌─────────────────────┼──────────────────────┐
                              │                     │                      │
                              ▼                     ▼                      ▼
                  ┌───────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
                  │ BDA Job (PDF/DOCX)│  │ AWS Glue (Excel) │  │ Direct parse (.txt)  │
                  │ Bedrock Data Auto │  │ PySpark job      │  │ Lambda inline        │
                  └─────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘
                            │                     │                       │
                            └─────────────────────┼───────────────────────┘
                                                  │
                                                  ▼
                                     ┌────────────────────────┐
                                     │  Lambda: normalise_json │
                                     │  - maps BDA/Glue output │
                                     │    to ExtractedDocument │
                                     │    schema v1.0          │
                                     │  - writes to extracted/ │
                                     └────────────┬───────────┘
                                                  │
                                                  ▼
                                     ┌────────────────────────┐
                                     │  Lambda: trigger_kb_sync│
                                     │  - calls               │
                                     │  start-ingestion-job   │
                                     └────────────────────────┘
```

### 8.2 Component Specifications

| Component | AWS Service | Configuration Notes |
|---|---|---|
| Raw doc storage | S3 Standard | Versioning enabled; lifecycle rule moves to S3-IA after 90 days |
| PDF/DOCX extraction | Bedrock Data Automation | Modality: DOCUMENT; output: structured JSON with tables and key-value pairs |
| Excel extraction | AWS Glue 4.0 | PySpark job using `openpyxl`; reads all sheets; serialises each sheet as a page |
| Dispatch Lambda | Lambda (Python 3.12) | Triggered by S3 EventBridge; 512 MB, 5 min timeout |
| Normalise Lambda | Lambda (Python 3.12) | Maps BDA output fields to ExtractedDocument schema; 512 MB, 5 min timeout |
| KB sync Lambda | Lambda (Python 3.12) | Calls `bedrock-agent:StartIngestionJob`; idempotent (checks for in-progress job first) |
| Dead-letter queue | SQS FIFO | All failed Lambda invocations land here for manual review |
| Extraction audit log | DynamoDB | Records `{portfolio_id, doc_type, extraction_timestamp, status, page_count, error}` |

### 8.3 BDA Configuration for PDF Extraction

```json
{
  "dataAutomationProjectArn": "arn:aws:bedrock:ap-southeast-2::foundation-model/amazon.nova-pro-v1:0",
  "outputConfig": {
    "s3Uri": "s3://{bucket}/portfolios/{portfolio_id}/bda-output/",
    "documentOutputConfiguration": {
      "extractionConfiguration": {
        "granularity": {
          "types": ["PAGE", "ELEMENT"]
        },
        "boundingBox": { "state": "DISABLED" }
      },
      "generativeConfiguration": {
        "state": "DISABLED"
      },
      "outputFormat": {
        "types": ["MARKDOWN", "STRUCTURED_JSON"]
      }
    }
  }
}
```

### 8.4 Excel Glue Job (outline)

The Glue job reads `performance_data.xlsx`, iterates sheets, and produces the `ExtractedDocument` page structure. Key logic:

```python
# Pseudocode for Glue PySpark job
import openpyxl
for sheet in workbook.worksheets:
    headers = [cell.value for cell in sheet[1]]
    rows = [[str(cell.value) for cell in row] for row in sheet.iter_rows(min_row=2)]
    page = {
        "page_number": sheet_index + 1,
        "section_title": sheet.title,
        "content": f"Data from sheet: {sheet.title}",
        "tables": [{"table_id": f"sheet_{sheet_index}", "headers": headers, "rows": rows}],
        "key_value_pairs": []
    }
```

---

## 9. KB Configuration JSON

This is the Bedrock Knowledge Base configuration used in both demo and production. Save as `kb_config.json` and reference in CDK/CloudFormation.

```json
{
  "knowledgeBase": {
    "name": "due-diligence-portfolio-kb",
    "description": "Portfolio due diligence documents for investment analysis demo",
    "roleArn": "arn:aws:iam::{account}:role/BedrockKBRole",
    "knowledgeBaseConfiguration": {
      "type": "VECTOR",
      "vectorKnowledgeBaseConfiguration": {
        "embeddingModelArn": "arn:aws:bedrock:ap-southeast-2::foundation-model/amazon.titan-embed-text-v2:0",
        "embeddingModelConfiguration": {
          "bedrockEmbeddingModelConfiguration": {
            "dimensions": 1024,
            "embeddingDataType": "FLOAT32"
          }
        }
      }
    },
    "storageConfiguration": {
      "type": "OPENSEARCH_SERVERLESS",
      "opensearchServerlessConfiguration": {
        "collectionArn": "arn:aws:aoss:ap-southeast-2:{account}:collection/{collection-id}",
        "vectorIndexName": "due-diligence-index",
        "fieldMapping": {
          "vectorField": "embedding",
          "textField": "text",
          "metadataField": "metadata"
        }
      }
    }
  },
  "dataSource": {
    "name": "portfolio-chunks-s3",
    "description": "Pre-chunked portfolio documents with metadata sidecars",
    "dataSourceConfiguration": {
      "type": "S3",
      "s3Configuration": {
        "bucketArn": "arn:aws:s3:::{bucket}",
        "inclusionPrefixes": ["kb-data-source/"],
        "bucketOwnerAccountId": "{account}"
      }
    },
    "vectorIngestionConfiguration": {
      "chunkingConfiguration": {
        "chunkingStrategy": "NONE"
      },
      "customTransformationConfiguration": null,
      "parsingConfiguration": {
        "parsingStrategy": "BEDROCK_FOUNDATION_MODEL",
        "bedrockFoundationModelConfiguration": {
          "modelArn": "arn:aws:bedrock:ap-southeast-2::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
        }
      }
    }
  },
  "retrievalConfiguration": {
    "vectorSearchConfiguration": {
      "numberOfResults": 10,
      "overrideSearchType": "HYBRID",
      "filter": null
    }
  }
}
```

**Notes on key settings:**

- `chunkingStrategy: NONE` — because the KB indexer pre-chunks. Bedrock treats each `.txt` file as one chunk.
- `overrideSearchType: HYBRID` — combines semantic vector search with BM25 keyword search. Critical for queries containing fund names, specific fee percentages, and ticker symbols.
- `dimensions: 1024` — Titan Embed v2 supports 256/512/1024; 1024 gives best recall at modest cost increase.
- The `parsingConfiguration` using Claude Haiku applies only if raw files were uploaded directly; in demo mode it is effectively unused since we upload pre-chunked `.txt` files.

### 9.1 OpenSearch Serverless Index Mapping

```json
{
  "settings": {
    "index.knn": true,
    "index.knn.space_type": "cosinesimil"
  },
  "mappings": {
    "properties": {
      "embedding": {
        "type": "knn_vector",
        "dimension": 1024,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "faiss",
          "parameters": { "ef_construction": 512, "m": 16 }
        }
      },
      "text":     { "type": "text" },
      "metadata": { "type": "object" }
    }
  }
}
```

---

## 10. Operational Runbook

### 10.1 Demo Setup Steps

```bash
# 1. Install dependencies
pip install boto3 tiktoken

# 2. Generate all synthetic extracted JSON locally
python generate_demo_data.py --local-only --output-dir ./demo_data

# 3. Inspect output (25 files expected)
find ./demo_data -name "*.json" | wc -l   # should print 25

# 4. Upload extracted JSON to S3
python generate_demo_data.py \
    --bucket $DEMO_BUCKET \
    --prefix portfolios

# 5. Run KB indexer to create chunks + metadata sidecars
python kb_indexer.py \
    --bucket $DEMO_BUCKET \
    --extracted-prefix portfolios \
    --kb-prefix kb-data-source \
    --region ap-southeast-2

# 6. Trigger Bedrock KB ingestion sync
aws bedrock-agent start-ingestion-job \
    --knowledge-base-id $KB_ID \
    --data-source-id $DS_ID \
    --region ap-southeast-2

# 7. Poll until ingestion complete
aws bedrock-agent get-ingestion-job \
    --knowledge-base-id $KB_ID \
    --data-source-id $DS_ID \
    --ingestion-job-id $JOB_ID \
    --query 'ingestionJob.status' \
    --output text
```

### 10.2 Expected Chunk Counts

| Portfolio | fund_factsheet | pds | im_submission | performance_data | meeting_transcript | Total |
|---|---|---|---|---|---|---|
| AMP_GROWTH | 3 | 5 | 3 | 2 | 2 | 15 |
| PENDAL_AEQ | 3 | 4 | 3 | 2 | 2 | 14 |
| MACQ_INCOME | 3 | 4 | 2 | 2 | 2 | 13 |
| AEF_BALANCED | 3 | 3 | 3 | 2 | 2 | 13 |
| HYPERION_AGF | 3 | 4 | 3 | 2 | 2 | 14 |
| **Total** | **15** | **20** | **14** | **10** | **10** | **69** |

Approximate total chunk count: **65–75 chunks** depending on tokeniser splits. Well within Bedrock KB limits.

### 10.3 Validation Query

After ingestion completes, validate retrieval with a direct KB query:

```python
import boto3, json

br = boto3.client("bedrock-agent-runtime", region_name="ap-southeast-2")

resp = br.retrieve(
    knowledgeBaseId=KB_ID,
    retrievalQuery={"text": "What are the fees for AMP Growth Fund?"},
    retrievalConfiguration={
        "vectorSearchConfiguration": {
            "numberOfResults": 5,
            "filter": {
                "andAll": [
                    {"equals": {"key": "portfolio_id", "value": "AMP_GROWTH"}},
                    {"equals": {"key": "criterion_category", "value": "fees_costs"}},
                ]
            },
        }
    },
)

for r in resp["retrievalResults"]:
    score = r["score"]
    meta = r["metadata"]
    text = r["content"]["text"][:200]
    print(f"Score: {score:.3f} | {meta.get('doc_type')} p{meta.get('page_number')} | {text}")
```

Expected: top result is AMP Growth fund factsheet page 3 (fees section) with score > 0.75.

### 10.4 Re-ingestion After Data Changes

If the synthetic generator is re-run (e.g., to fix content), re-run the full pipeline:

```bash
# Re-upload extracted JSON (overwrites existing)
python generate_demo_data.py --bucket $DEMO_BUCKET --prefix portfolios

# Re-run indexer — overwrites existing chunk files in place
python kb_indexer.py --bucket $DEMO_BUCKET ...

# Start a new ingestion job (Bedrock detects changed S3 objects via ETag)
aws bedrock-agent start-ingestion-job ...
```

There is no need to delete the KB or data source. Bedrock KB ingestion is incremental — only changed or new S3 objects are re-embedded.

---

## Summary: File Inventory

| File | Purpose |
|---|---|
| `generate_demo_data.py` | Generates all 25 synthetic extracted JSON files and uploads to S3 |
| `kb_indexer.py` | Reads extracted JSON, chunks content, writes `.txt` + `.metadata.json` sidecars to S3 |
| `kb_config.json` | Bedrock KB + data source configuration (reference for CDK/CloudFormation) |
| `s3://bucket/portfolios/{id}/extracted/{doc_type}.json` | 25 extracted JSON files (demo mode input) |
| `s3://bucket/kb-data-source/{id}/chunks/*.txt` | 65–75 chunk text files (KB ingestion input) |
| `s3://bucket/kb-data-source/{id}/chunks/*.txt.metadata.json` | Sidecar metadata files for each chunk |
