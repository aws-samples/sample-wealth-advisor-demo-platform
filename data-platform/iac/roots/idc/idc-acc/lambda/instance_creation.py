import json
import time
import boto3

sso_client = boto3.client('sso-admin')
id_store_client = boto3.client('identitystore')

def lambda_handler(event, context):
    try:
        print("Check for existing IDC Instance")
        list_inst_response = sso_client.list_instances()
        if list_inst_response["Instances"]:
            print("IDC Instance exists. Skipping creation.")
            instance_arn = list_inst_response["Instances"][0]['InstanceArn']
            instance_desc = sso_client.describe_instance(InstanceArn=instance_arn)
            print("IDC Instance:" + json.dumps(instance_desc, indent=4, default=str))
            identity_store_id = instance_desc['IdentityStoreId']
            return {
                'statusCode': 200,
                'body': json.dumps({'InstanceArn': instance_arn})
            }

        print("Creating IDC Instance")
        create_response = sso_client.create_instance()
        instance_arn = create_response['InstanceArn']
        identity_store_id = None

        for idx in range(10):
            instance_desc = sso_client.describe_instance(InstanceArn=instance_arn)
            print("IDC Instance:" + json.dumps(instance_desc, indent=4, default=str))
            if instance_desc['Status'] != "ACTIVE":
                time.sleep(10)
            else:
                identity_store_id = instance_desc['IdentityStoreId']
                break

        return {
            'statusCode': 200,
            'body': json.dumps({
                'InstanceArn': instance_arn,
                'IdentityStoreId': identity_store_id
            })
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
