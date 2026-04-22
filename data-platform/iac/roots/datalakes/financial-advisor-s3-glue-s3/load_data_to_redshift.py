# Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import sys
import logging
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'SOURCE_PATH', 'TABLE_NAME', 'REDSHIFT_URL', 'REDSHIFT_DATABASE', 'REDSHIFT_TEMP_DIR', 'REDSHIFT_IAM_ROLE'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

SOURCE_PATH = args['SOURCE_PATH']
TABLE_NAME = args['TABLE_NAME']
REDSHIFT_URL = args['REDSHIFT_URL']
REDSHIFT_DATABASE = args['REDSHIFT_DATABASE']
REDSHIFT_TEMP_DIR = args['REDSHIFT_TEMP_DIR']
REDSHIFT_IAM_ROLE = args['REDSHIFT_IAM_ROLE']

logger.info(f"Loading data from: {SOURCE_PATH} to Redshift table: public.{TABLE_NAME}")

try:
    source_df = spark.read.csv(SOURCE_PATH, header=True, inferSchema=True)
    row_count = source_df.count()
    logger.info(f"Loaded {row_count} rows from source file")

    redshift_url = f"jdbc:redshift://{REDSHIFT_URL}:5439/{REDSHIFT_DATABASE}"

    source_df.write \
        .format("io.github.spark_redshift_community.spark.redshift") \
        .option("url", redshift_url) \
        .option("dbtable", f"public.{TABLE_NAME}") \
        .option("tempdir", REDSHIFT_TEMP_DIR) \
        .option("aws_iam_role", REDSHIFT_IAM_ROLE) \
        .mode("overwrite") \
        .save()

    logger.info(f"Successfully loaded {row_count} rows into public.{TABLE_NAME}")

except Exception as e:
    logger.error(f"Error processing data: {str(e)}")
    raise e
finally:
    job.commit()
    logger.info("Job completed")
