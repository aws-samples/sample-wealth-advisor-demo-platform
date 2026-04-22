import json
import logging
import os
import boto3
import time

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment Variables
DOMAIN_ID = os.environ.get('DOMAIN_ID')
PRODUCER_PROJECT_ID = os.environ.get('PRODUCER_PROJECT_ID')
TOOLING_ENV_ID = os.environ.get('TOOLING_ENV_ID')
AWS_REGION = os.environ.get('AWS_REGION')
AWS_ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID')

# Validate essential environment variables
if not all([DOMAIN_ID, PRODUCER_PROJECT_ID, TOOLING_ENV_ID, AWS_REGION, AWS_ACCOUNT_ID]):
    missing_vars = [var_name for var_name, var_value in {
        "DOMAIN_ID": DOMAIN_ID, "PRODUCER_PROJECT_ID": PRODUCER_PROJECT_ID,
        "TOOLING_ENV_ID": TOOLING_ENV_ID, "AWS_REGION": AWS_REGION,
        "AWS_ACCOUNT_ID": AWS_ACCOUNT_ID
    }.items() if not var_value]
    error_message = f"Missing one or more required environment variables: {', '.join(missing_vars)}"
    logger.error(error_message)
    raise ValueError(error_message)

TARGET_ROLE_ARN = f"arn:aws:iam::{AWS_ACCOUNT_ID}:role/datazone_usr_role_{PRODUCER_PROJECT_ID}_{TOOLING_ENV_ID}"
sts_client = boto3.client('sts', region_name=AWS_REGION)


def get_assumed_role_credentials():
    try:
        logger.info(f"Attempting to assume role: {TARGET_ROLE_ARN}")
        assumed_role_object = sts_client.assume_role(
            RoleArn=TARGET_ROLE_ARN,
            RoleSessionName="DataZoneConnectionLambdaSession"
        )
        logger.info(f"Successfully assumed role: {TARGET_ROLE_ARN}")
        return assumed_role_object['Credentials']
    except Exception as e:
        logger.warning(f"Error assuming role {TARGET_ROLE_ARN}: {str(e)}")
        raise


def get_datazone_client_with_credentials(credentials):
    return boto3.client(
        'datazone',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
        region_name=AWS_REGION
    )


def handle_create_or_update(props, credentials, is_update=False):
    connection_name = props.get('ConnectionName')
    cli_input_json_payload_str = props.get('CliInputJsonPayload')

    if not cli_input_json_payload_str:
        logger.error(
            "CliInputJsonPayload not provided in props for Create/Update.")
        raise ValueError(
            "Missing CliInputJsonPayload for Create/Update operation.")

    datazone_client = get_datazone_client_with_credentials(credentials)

    try:
        connection_params = json.loads(cli_input_json_payload_str)
        logger.info(
            f"Parsed connection parameters for Boto3: {json.dumps(connection_params)}")

        # Ensure environmentIdentifier is present, defaulting if necessary
        if 'environmentIdentifier' not in connection_params:
            logger.info(
                f"environmentIdentifier not in CliInputJsonPayload, using default TOOLING_ENV_ID: {TOOLING_ENV_ID}")
            connection_params['environmentIdentifier'] = TOOLING_ENV_ID

        # Ensure name is present, defaulting if necessary
        if 'name' not in connection_params:
            logger.info(
                f"Connection name not in CliInputJsonPayload, using ConnectionName from props: {connection_name}")
            connection_params['name'] = connection_name

        action = "Updating" if is_update else "Creating"
        logger.info(
            f"{action} connection using Boto3 with domain ID: {DOMAIN_ID} and effective params: {json.dumps(connection_params)}")

        response = datazone_client.create_connection(
            domainIdentifier=DOMAIN_ID,
            **connection_params
        )
        logger.info(
            f"Boto3 create_connection raw response: {json.dumps(response)}")

        # Use 'connectionId' (camelCase) as confirmed
        retrieved_connection_id = response.get('connectionId')

        if not retrieved_connection_id:
            error_msg = f"create_connection response did not include a 'connectionId' or it was null/empty. Full response: {json.dumps(response)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(
            f"Boto3 create_connection successful. Connection ID: {retrieved_connection_id}")
        return retrieved_connection_id

    except json.JSONDecodeError as e:
        logger.error(
            f"Failed to parse CliInputJsonPayload: {str(e)}. Payload was: {cli_input_json_payload_str}")
        raise
    except Exception as e:
        logger.error(
            f"Error calling Boto3 create_connection: {str(e)}. Effective Params: {json.dumps(connection_params if 'connection_params' in locals() else 'not parsed')}")
        raise


def handle_delete(props, credentials, physical_resource_id=None):
    connection_name_to_delete = props.get('ConnectionName')
    # This should be the actual connection ID
    connection_id_to_delete = physical_resource_id

    logger.info(
        f"Attempting to delete connection. Name from props: '{connection_name_to_delete}', ID to delete: '{connection_id_to_delete}'")
    datazone_client = get_datazone_client_with_credentials(credentials)

    if not connection_id_to_delete:
        logger.warning(
            f"PhysicalResourceId (connection ID) not provided for delete. Attempting to find connection ID by name: '{connection_name_to_delete}' in environment '{TOOLING_ENV_ID}'. This is a fallback.")
        try:
            paginator = datazone_client.get_paginator('list_connections')
            found_connection_for_delete = False
            for page in paginator.paginate(domainIdentifier=DOMAIN_ID):
                for item in page.get('items', []):
                    if item.get('name') == connection_name_to_delete:
                        logger.info(
                            f"Found potential match by name: {item.get('name')} with ID: {item.get('id')}. Verifying environment...")
                        # Fetch details to confirm it's in the correct environment
                        connection_details = datazone_client.get_connection(
                            domainIdentifier=DOMAIN_ID, identifier=item['id'])
                        if connection_details.get('environmentId') == TOOLING_ENV_ID:
                            # Use the actual ID from DataZone
                            connection_id_to_delete = item['id']
                            logger.info(
                                f"Confirmed connection ID: {connection_id_to_delete} for name '{connection_name_to_delete}' in environment '{TOOLING_ENV_ID}'")
                            found_connection_for_delete = True
                            break
                if found_connection_for_delete:
                    break

            if not connection_id_to_delete:
                logger.warning(
                    f"Connection named '{connection_name_to_delete}' not found in domain '{DOMAIN_ID}' and environment '{TOOLING_ENV_ID}' after search. Skipping deletion.")
                return  # Nothing to delete if not found by name either
        except Exception as e:
            logger.error(
                f"Error listing connections to find ID for '{connection_name_to_delete}': {str(e)}. Assuming it might be already deleted or unfindable.")
            return  # If search fails, cannot proceed with name-based delete

    if not connection_id_to_delete:
        logger.warning(
            f"Could not determine a valid connection ID for '{connection_name_to_delete}'. Skipping deletion as it might already be deleted or was never created/found.")
        return

    try:
        logger.info(
            f"Attempting to delete Connection ID: {connection_id_to_delete} for domain {DOMAIN_ID}")
        datazone_client.delete_connection(
            domainIdentifier=DOMAIN_ID,
            identifier=connection_id_to_delete  # Use the actual ID
        )
        logger.info(
            f"DataZone connection (ID: {connection_id_to_delete}) deletion command successfully initiated.")
    except datazone_client.exceptions.ResourceNotFoundException:
        logger.info(
            f"Connection (ID: {connection_id_to_delete}) already deleted or not found, which is okay for a delete operation.")
    except Exception as e:
        logger.error(
            f"Error during connection deletion for ID '{connection_id_to_delete}': {str(e)}")
        raise  # Re-raise to signal failure to Terraform


def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    request_type = event.get('RequestType')
    props = event.get('ResourceProperties', {})
    # Provided by CFN/Terraform for Update/Delete
    physical_resource_id = event.get('PhysicalResourceId')

    connection_name_from_props = props.get(
        'ConnectionName')  # For logging and fallback

    response_data = {}

    try:
        credentials = get_assumed_role_credentials()

        if request_type == 'Create':
            logger.info(
                f"Processing Create for connection: {connection_name_from_props}")
            new_connection_id = handle_create_or_update(
                props, credentials, is_update=False)
            # The new ID becomes the PhysicalResourceId
            physical_resource_id = new_connection_id
            response_data['ConnectionId'] = new_connection_id
            logger.info(
                f"Create successful. PhysicalResourceId: {physical_resource_id}")

        elif request_type == 'Update':
            logger.info(
                f"Processing Update for connection: {connection_name_from_props} (Old PhysicalResourceId: {physical_resource_id})")

            if physical_resource_id:
                logger.info(
                    f"Update operation: attempting to delete existing connection with ID '{physical_resource_id}' first.")
                try:
                    handle_delete(props, credentials,
                                  physical_resource_id=physical_resource_id)
                    logger.info(
                        f"Deletion of old resource '{physical_resource_id}' as part of update seems complete. Waiting before recreate.")
                    time.sleep(10)  # Give some time for deletion to propagate
                except Exception as del_ex:
                    logger.warning(
                        f"Error deleting old resource '{physical_resource_id}' during update: {str(del_ex)}. Proceeding with create attempt.")
            else:
                logger.warning(
                    "Update event did not have PhysicalResourceId. This is unusual. Attempting delete by name if necessary before create.")
                handle_delete(props, credentials)  # Tries to find by name
                time.sleep(10)

            logger.info(
                f"Update operation: creating new version of connection for '{connection_name_from_props}'.")
            new_connection_id = handle_create_or_update(
                props, credentials, is_update=True)
            # For replacement, the new ID is returned
            physical_resource_id = new_connection_id
            response_data['ConnectionId'] = new_connection_id
            logger.info(
                f"Update successful. New PhysicalResourceId: {physical_resource_id}")

        elif request_type == 'Delete':
            logger.info(
                f"Processing Delete for connection: {connection_name_from_props} (PhysicalResourceId from event: {physical_resource_id})")
            if not physical_resource_id:
                logger.warning(
                    "PhysicalResourceId not provided for Delete operation. Attempting to delete by name as a fallback.")
                handle_delete(props, credentials)
            else:
                handle_delete(props, credentials,
                              physical_resource_id=physical_resource_id)
            logger.info(
                f"Delete processing complete for PhysicalResourceId: {physical_resource_id}")
            # For Delete, the PhysicalResourceId in the response should be the one from the event.

        else:
            error_msg = f"Unsupported RequestType: {request_type}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # For Terraform null_resource, the PhysicalResourceId is the primary output.
        # The last line printed to stdout by the 'create' provisioner is used as the resource ID.
        # For 'destroy', stdout is not typically used by Terraform to change state.
        # The Lambda response structure here is more aligned with CloudFormation Custom Resources,
        # but for Terraform, the key is that the Lambda exits successfully (or raises an error).
        # The 'echo "$PHYSICAL_ID"' in the Terraform create provisioner is what sets null_resource.id.
        return {
            'PhysicalResourceId': physical_resource_id,
            'Status': 'SUCCESS',
            'Data': response_data
        }

    except Exception as e:
        logger.warning(
            f"Error processing {request_type} for {connection_name_from_props} (PhysicalResourceId: {physical_resource_id}): {str(e)}", exc_info=True)
        # For Terraform null_resource, raising an exception is the way to signal failure.
        # The specific structure of the return for failure is less critical than for CFN.
        # This will cause the Lambda invocation to be marked as failed by AWS Lambda.
        raise
