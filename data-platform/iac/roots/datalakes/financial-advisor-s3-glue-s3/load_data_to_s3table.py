# Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import sys
import logging
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.conf import SparkConf
from pyspark.sql.types import BooleanType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'SOURCE_PATH', 'TABLE_NAME', 'NAMESPACE', 'TABLE_BUCKET_ARN'])

SOURCE_PATH = args.get('SOURCE_PATH')
TABLE_NAME = args.get('TABLE_NAME')
NAMESPACE = args.get("NAMESPACE")
TABLE_BUCKET_ARN = args.get("TABLE_BUCKET_ARN")

conf = SparkConf()
conf.set("spark.sql.defaultCatalog", "s3tablescatalog")
conf.set("spark.sql.catalog.s3tablescatalog", "org.apache.iceberg.spark.SparkCatalog")
conf.set("spark.sql.catalog.s3tablescatalog.catalog-impl", "software.amazon.s3tables.iceberg.S3TablesCatalog")
conf.set("spark.sql.catalog.s3tablescatalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
conf.set("spark.sql.catalog.s3tablescatalog.warehouse", TABLE_BUCKET_ARN)
conf.set("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")

sc = SparkContext(conf=conf)
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

logger.info(f"Loading data from: {SOURCE_PATH} to table: {TABLE_NAME}")

try:
    target_table = f"s3tablescatalog.{NAMESPACE}.{TABLE_NAME}"
    target_schema = spark.table(target_table).schema

    # Read CSV as all strings
    source_df = spark.read.csv(SOURCE_PATH, header=True, inferSchema=False)
    source_df.createOrReplaceTempView("csv_source")

    # Build per-column SQL cast expressions
    cast_exprs = []
    for field in target_schema:
        col = field.name
        type_str = field.dataType.simpleString()

        if isinstance(field.dataType, BooleanType):
            cast_exprs.append(
                f"CASE WHEN lower(`{col}`) IN ('true','t','1','yes') THEN true "
                f"WHEN lower(`{col}`) IN ('false','f','0','no') THEN false "
                f"ELSE null END AS `{col}`"
            )
        else:
            cast_exprs.append(f"CAST(`{col}` AS {type_str}) AS `{col}`")

    select_sql = ", ".join(cast_exprs)

    # Set timestamp type to NTZ so CAST produces TIMESTAMP_NTZ
    spark.conf.set("spark.sql.timestampType", "TIMESTAMP_NTZ")

    casted_df = spark.sql(f"SELECT {select_sql} FROM csv_source")

    # Drop rows with nulls in required (non-nullable) fields
    required_cols = [f.name for f in target_schema if not f.nullable]
    if required_cols:
        casted_df = casted_df.dropna(subset=required_cols)
        logger.info(f"Filtering nulls on required columns: {required_cols}")

    # Log schema for debugging
    for f in casted_df.schema:
        logger.info(f"  Column {f.name}: {f.dataType}")

    row_count = casted_df.count()
    logger.info(f"Loaded {row_count} rows from source file")

    logger.info(f"Deleting existing data from {target_table}")
    spark.sql(f"DELETE FROM {target_table}")

    logger.info(f"Inserting into {target_table}")
    casted_df.createOrReplaceTempView("staged_data")
    spark.sql(f"INSERT INTO {target_table} SELECT * FROM staged_data")
    logger.info(f"Successfully loaded {row_count} rows into {target_table}")

except Exception as e:
    logger.error(f"Error processing data: {str(e)}")
    raise e
finally:
    job.commit()
    logger.info("Job completed")
