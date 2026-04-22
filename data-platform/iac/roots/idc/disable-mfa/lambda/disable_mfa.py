import boto3
import requests
import json
import hashlib
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from datetime import datetime, timezone

def get_sso_instance_arn():
    try:
        sso_admin_client = boto3.client("sso-admin")
        response = sso_admin_client.list_instances()

        if not response["Instances"]:
            raise ValueError("No SSO instances found in this account")

        return response["Instances"][0]["InstanceArn"]

    except Exception as e:
        print(f"Error retrieving SSO Instance ARN: {e}")
        raise

def generate_aws_headers(credentials, region_name):
    amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    payload = json.dumps({
        "instanceArn": get_sso_instance_arn(),
        "configurationType": "APP_AUTHENTICATION_CONFIGURATION",
        "ssoConfiguration": { "mfaMode": "DISABLED" }
    })

    request = AWSRequest(
        method="POST",
        url=f"https://sso.{region_name}.amazonaws.com/control/",
        data=payload,
        headers={
            "Content-Type": "application/x-amz-json-1.1",
            "x-amz-target": "SWBService.UpdateSsoConfiguration",
            "x-amz-date": amz_date,
            "Host": f"sso.{region_name}.amazonaws.com"
        }
    )

    signer = SigV4Auth(
        credentials=credentials,
        service_name="sso",
        region_name=region_name
    )
    signer.add_auth(request)

    signed_headers = dict(request.headers)
    signed_headers["x-amz-content-sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return signed_headers, payload

def disable_sso_mfa(region_name):
    try:
        headers, payload = generate_aws_headers(boto3.Session().get_credentials(), region_name)

        response = requests.post(
            f"https://sso.{region_name}.amazonaws.com/control/",
            headers=headers,
            data=payload
        )

        response.raise_for_status()
        print("SSO MFA configuration updated successfully.")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "SSO MFA configuration updated successfully",
                "response": response.text if response.text else ""
            })
        }

    except requests.RequestException as e:
        error_message = f"Error updating SSO MFA configuration: {e}"
        response_content = e.response.text if hasattr(e, "response") else ""
        print(error_message)
        if response_content:
            print("Response content:", response_content)
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": error_message,
                "response": response_content
            })
        }

def lambda_handler(event, context):
    try:
        region_name = boto3.Session().region_name
        instance_arn = get_sso_instance_arn()
        print(f"Retrieved SSO Instance ARN: {instance_arn}")
        
        return disable_sso_mfa(region_name)
        
    except Exception as e:
        error_message = f"Failed to process SSO MFA configuration: {e}"
        print(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }