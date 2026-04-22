# Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import json
import sys
import uuid

from datetime import datetime, timezone

def create_custom_asset_type(domain_id, project_id, asset_type_id, asset_type_desc):
    try:
        dz_client = boto3.client('datazone')
        
        # Create the asset type with RelationalTableFormType
        response = dz_client.create_asset_type(
            domainIdentifier=domain_id,
            name=asset_type_id,
            description=asset_type_desc,
            owningProjectIdentifier=project_id,
            formsInput={
                "CustomTableForm": {  
                    "typeIdentifier": "amazon.datazone.RelationalTableFormType",
                    "typeRevision": "1",
                    "required": True
                }
            }
        )
        
        return response
        
    except Exception as e:
        print(f"Error creating custom asset type: {str(e)}")
        raise


def create_asset_with_table_form(domain_id, project_id, asset_name, asset_type_id):
    try:
        dz_client = boto3.client('datazone')
        
        # Define the table content
        table_content = {
            "tableName": asset_name,
            "columns": [
                {
                    "columnName": "security",
                    "dataType": "varchar"
                },
                {
                    "columnName": "price",
                    "dataType": "varchar"
                },
                {
                    "columnName": "quantity",
                    "dataType": "varchar"
                }
            ]
        }
        
        # Create asset using the custom asset type
        response = dz_client.create_asset(
            domainIdentifier=domain_id,
            name=asset_name,
            description=asset_name,
            owningProjectIdentifier=project_id,
            typeIdentifier=asset_type_id,
            externalIdentifier= f"{domain_id}/{asset_name}",
            formsInput=[
                {
                    "formName": "CustomTableForm",
                    "typeIdentifier": "amazon.datazone.RelationalTableFormType",
                    "typeRevision": "1",
                    "content": json.dumps(table_content)
                }
            ]
        )
        
        return response
        
    except Exception as e:
        print(f"Error creating asset: {str(e)}")
        raise


def post_job_run_event(domain_id, source_table, target_table, event_type="START"):
    try:
        dz_client = boto3.client('datazone')
        run_id = str(uuid.uuid4())
        
        # Create OpenLineage JobRun event
        lineage_event = {
            "producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/spark",
            "schemaURL":"https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent",
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "eventType": event_type,
            "inputs": [
                {
                    "name": source_table,
                    "namespace": domain_id,
                    "facets": {
                        "schema": {
                            "_producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/spark",
                            "_schemaURL":"https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/InputFacet",
                            "fields": [
                                {
                                    "name": "security",
                                    "type": "string"
                                },
                                {
                                    "name": "price",
                                    "type": "string"
                                },
                                {
                                    "name": "quantity",
                                    "type": "string"
                                }
                            ]
                        }
                    }
                }
            ],
            "job": {
                "name": f"{source_table}_to_{target_table}",
                "namespace": "default",
                "facets":{
                     "jobType":{
                        "_producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/glue",
                        "_schemaURL":"https://openlineage.io/spec/facets/2-0-2/JobTypeJobFacet.json#/$defs/JobTypeJobFacet",
                        "processingType":"BATCH",
                        "integration":"glue",
                        "jobType":"JOB"
                     }
                  }
            },
            "outputs": [
                {
                    "name": target_table,
                    "namespace": domain_id,
                    "facets": {
                        "schema": {
                            "_producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/spark",
                            "_schemaURL":"https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/OutputFacet",
                            "fields": [
                                {
                                    "name": "security",
                                    "type": "string"
                                },
                                {
                                    "name": "price",
                                    "type": "string"
                                },
                                {
                                    "name": "quantity",
                                    "type": "string"
                                }
                            ]
                        },
                        "columnLineage": {
                            "_producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/spark",
                            "_schemaURL":"https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/OutputFacet",
                            "fields": {
                                "security": {
                                    "inputFields": [
                                        {
                                            "namespace": domain_id,
                                            "name": source_table,
                                            "field": "security"
                                        }
                                    ]
                                },
                                "price": {
                                    "inputFields": [
                                        {
                                            "namespace": domain_id,
                                            "name": source_table,
                                            "field": "price"
                                        }
                                    ]
                                },
                                "quantity": {
                                    "inputFields": [
                                        {
                                            "namespace": domain_id,
                                            "name": source_table,
                                            "field": "quantity"
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            ],
            "run": {
                "runId": run_id,
                "facets":{
                     "environment-properties":{
                        "_producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/spark",
                        "_schemaURL":"https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunFacet",
                         "environment-properties":{
                           "GLUE_VERSION":"3.0",
                           "GLUE_COMMAND_CRITERIA":"glueetl",
                           "GLUE_PYTHON_VERSION":"3"
                        }
                     }
                  }
            }
        }
        
        # Add metrics for COMPLETE event
        if event_type == "COMPLETE":
            lineage_event["run"]["facets"]["metrics"] = {
                "rowsProcessed": 1000,
                "bytesProcessed": 10240
            }
        
        # Post the lineage event
        response = dz_client.post_lineage_event(
            domainIdentifier=domain_id,
            clientToken=str(uuid.uuid4()),
            event=json.dumps(lineage_event)
        )
        
        print(f"Posted {event_type} lineage event: {response}")
        return response, run_id
        
    except Exception as e:
        print(f"Error posting {event_type} lineage event: {str(e)}")
        raise


def post_complete_job_run_event(domain_id, source_table, target_table, run_id):
    try:
        # Create OpenLineage COMPLETE event
        complete_event = {
            "producer": "custom-etl-job",
            "schemaURL":"https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent",
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "eventType": "COMPLETE",
            "inputs": [
                {
                    "name": source_table,
                    "namespace": domain_id,
                    "facets": {
                        "schema": {
                            "_producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/spark",
                            "_schemaURL":"https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/InputFacet",
                            "fields": [
                                {
                                    "name": "security",
                                    "type": "string"
                                },
                                {
                                    "name": "price",
                                    "type": "string"
                                },
                                {
                                    "name": "quantity",
                                    "type": "string"
                                }
                            ]
                        }
                    }
                }
            ],
            "job": {
                "name": f"{source_table}_to_{target_table}",
                "namespace": "default",
                "facets":{
                     "jobType":{
                        "_producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/glue",
                        "_schemaURL":"https://openlineage.io/spec/facets/2-0-2/JobTypeJobFacet.json#/$defs/JobTypeJobFacet",
                        "processingType":"BATCH",
                        "integration":"glue",
                        "jobType":"JOB"
                     }
                  }
            },
            "outputs": [
                {
                    "name": target_table,
                    "namespace": domain_id,
                    "facets": {
                        "schema": {
                            "_producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/spark",
                            "_schemaURL":"https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/OutputFacet",
                            "fields": [
                                {
                                    "name": "security",
                                    "type": "string"
                                },
                                {
                                    "name": "price",
                                    "type": "string"
                                },
                                {
                                    "name": "quantity",
                                    "type": "string"
                                }
                            ]
                        },
                        "columnLineage": {
                            "_producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/spark",
                            "_schemaURL":"https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/OutputFacet",
                            "fields": {
                                "security": {
                                    "inputFields": [
                                        {
                                            "namespace": domain_id,
                                            "name": source_table,
                                            "field": "security"
                                        }
                                    ]
                                },
                                "price": {
                                    "inputFields": [
                                        {
                                            "namespace": domain_id,
                                            "name": source_table,
                                            "field": "price"
                                        }
                                    ]
                                },
                                "quantity": {
                                    "inputFields": [
                                        {
                                            "namespace": domain_id,
                                            "name": source_table,
                                            "field": "quantity"
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            ],
            "run": {
                "runId": run_id,
                "facets":{
                     "environment-properties":{
                        "_producer":"https://github.com/OpenLineage/OpenLineage/tree/1.9.1/integration/spark",
                        "_schemaURL":"https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunFacet",
                         "environment-properties":{
                           "GLUE_VERSION":"3.0",
                           "GLUE_COMMAND_CRITERIA":"glueetl",
                           "GLUE_PYTHON_VERSION":"3"
                        }
                     }
                  }
            }
        }
        
        # Post the complete event
        dz_client = boto3.client('datazone')
        response = dz_client.post_lineage_event(
            domainIdentifier=domain_id,
            clientToken=str(uuid.uuid4()),
            event=json.dumps(complete_event)
        )
        
        print(f"Posted complete event: {response}")
        return response
        
    except Exception as e:
        print(f"Error posting complete event: {str(e)}")
        raise
    
def main():
    
    app = "daivi"
    env = "dev1"

    ssm_client = boto3.client('ssm')
    domain_id = ssm_client.get_parameter(Name=f'/{app}/{env}/smus_domain_id', WithDecryption=True)['Parameter']['Value']
    project_id = ssm_client.get_parameter(Name=f'/{app}/{env}/sagemaker/producer/id', WithDecryption=True)['Parameter']['Value']

    asset_name = "Order"
    asset_type_id = "Order"
    asset_type_desc = "Order"

    try:
        # First create the custom asset type
        asset_type_response = create_custom_asset_type(
            domain_id,
            project_id,
            asset_type_id,
            asset_type_desc
        )
        print("Created custom asset type")
        
        # Then create an asset using the custom asset type
        asset_response = create_asset_with_table_form(
            domain_id,
            project_id,
            asset_name,
            asset_type_id
        )
        print(f"Created asset using custom asset type: {asset_response}")
            
    except Exception as e:
        print(f"Failed to create asset type or asset: {str(e)}")


    asset_name = "Trade"
    asset_type_id = "Trade"
    asset_type_desc = "Trade"

    try:
        # First create the custom asset type
        asset_type_response = create_custom_asset_type(
            domain_id,
            project_id,
            asset_type_id,
            asset_type_desc
        )
        print("Created custom asset type")
        
        # Then create an asset using the custom asset type
        asset_response = create_asset_with_table_form(
            domain_id,
            project_id,
            asset_name,
            asset_type_id
        )
        print(f"Created asset using custom asset type: {asset_response}")
            
    except Exception as e:
        print(f"Failed to create asset type or asset: {str(e)}")

    source_table = "Order"
    target_table = "Trade"

    try:
        # Post START event
        start_response, run_id = post_job_run_event(
            domain_id,
            source_table,
            target_table,
            "START"
        )
        print("Successfully posted both START event with column lineage")
        print(start_response)
        
        if start_response:
            # Simulate some processing time
            import time
            time.sleep(10)
            
            # Post COMPLETE event with the same run ID
            complete_response = post_complete_job_run_event(
                domain_id,
                source_table,
                target_table,
                run_id
            )
            if complete_response:
                print("Successfully posted COMPLETE events with column lineage")
                print(complete_response)
            
    except Exception as e:
        print(f"Failed to post lineage events: {str(e)}")

if __name__ == "__main__":

    main()      
