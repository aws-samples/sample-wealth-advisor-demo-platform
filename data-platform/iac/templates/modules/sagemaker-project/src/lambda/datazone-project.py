# Copyright 2025 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import signal
import urllib3
import json
import logging as log


def handler(event, context):
    log.getLogger().setLevel(log.INFO)
    print(event)
 
    datazone_client = boto3.client('datazone')
    

    domain_id = event['ResourceProperties']['domainId']
    project_name = event['ResourceProperties']['name']
    project_description = event['ResourceProperties']['description']
    project_owner = event['ResourceProperties']['owner']
    owner_type = event['ResourceProperties']['userType']
    project_role = event['ResourceProperties']['role']
    #project_glossary_terms = event['ResourceProperties'].get('glossaryTerms', [])
    domain_unit = event['ResourceProperties'].get('domainUnitId', None)
    project_profile_id = event['ResourceProperties'].get('projectProfileId', None)
    glueDB = event['ResourceProperties'].get('glueDB', 'glue_db')
    wgName = event['ResourceProperties'].get('workgroupName', 'workgroup')
    project_id = None 
    try:
        if event['RequestType'] == 'Create':
            set_domain_policy(datazone_client, domain_id, domain_unit, project_role)
            enable_EMRServerless(datazone_client, domain_id, project_profile_id)
            project_id = create_project(datazone_client, domain_unit, domain_id, project_name, project_description, project_profile_id, glueDB, wgName)
            log.info('project id: %s', project_id)
            add_project_owner(datazone_client, domain_id, project_id, project_owner, owner_type)
            response_data = {"ProjectId": project_id}
            sendResponseCfn(event, context, 'SUCCESS', project_id, response_data)

        elif event['RequestType'] == 'Update':
            identifier = event['PhysicalResourceId']
            if identifier is None or identifier == "":
                print("Project Id is empty or None")
            else:    
                project_id = update_project(datazone_client, identifier, domain_id, project_name, project_description)
                add_project_owner(datazone_client, domain_id, project_id, project_owner)
            response_data = {"ProjectId": identifier}
            sendResponseCfn(event, context, 'SUCCESS', identifier, response_data)

        elif event['RequestType'] == 'Delete':
            identifier = event['PhysicalResourceId']
            # Ensure identifier is a string
            if identifier is None or identifier == "" or identifier == "None":
                print("Project Id is empty or None, using fallback")
                identifier = "DELETED-" + context.request_id
            else: 
                delete_project(datazone_client, domain_id, identifier)
            sendResponseCfn(event, context, 'SUCCESS', identifier, json.loads("{}"))
    except Exception as e: 
        log.info('FAILED!')
        log.error(e, stack_info=True, exc_info=True)
        # PhysicalResourceId must be a string, use a fallback if project_id is None
        fallback_id = "FAILED-" + context.request_id
        physical_id = project_id if project_id and isinstance(project_id, str) else fallback_id
        response_data = {"ProjectId": str(project_id) if project_id else "None"}
        sendResponseCfn(event, context, "FAILED", physical_id, response_data)


def get_project_blueprint(datazone_client, domain_id, blueprint_name):
    response = datazone_client.list_environment_blueprints(
        domainIdentifier=domain_id,
        managed=True,
    )
    for blueprint in response['items']:
        if blueprint['name'] == blueprint_name:
            return blueprint['id']

def enable_EMRServerless(datazone_client, domain_id, project_profile_id):
    profileId = project_profile_id.split(':')[0]
    response = datazone_client.get_project_profile(
        domainIdentifier=domain_id,
        identifier=profileId
    )
    blueprint_id = get_project_blueprint(datazone_client, domain_id, 'EmrServerless')
    log.info('blueprint_id: %s', blueprint_id)
    profiles = response['environmentConfigurations']
    for profile in profiles:
        if profile['environmentBlueprintId'] == blueprint_id:
            profile['deploymentMode'] = "ON_CREATE"
    
    log.info('profiles: %s', profiles)
    response = datazone_client.update_project_profile(
        domainIdentifier=domain_id,
        identifier=profileId,
        environmentConfigurations=profiles
    )
    return response

def create_project(datazone_client, domain_unit, domain_id, project_name, project_description, project_profile_id, glueDB, wgName):
    if domain_unit == None:
        getDomainId = datazone_client.get_domain(
            identifier=domain_id
        )
        domain_unit = getDomainId['rootDomainUnitId']
        log.info('domain root id: %s', getDomainId['rootDomainUnitId'])
    profileId = project_profile_id.split(':')[0]
    userParameters=[
    {
        'environmentConfigurationName': 'LakeHouseDatabaseisen',
        'environmentParameters': [
            {
                'name': 'glueDbName',
                'value': glueDB
            },
            {
                'name': 'workgroupName',
                'value': wgName
            }
        ]
    }]
    response = datazone_client.create_project(
        domainIdentifier=domain_id,
        #domainUnitId=domain_unit,
        name=project_name,
        projectProfileId=profileId,
        userParameters=userParameters,
        #glossaryTerms=project_glossary_terms,
        description=project_description
    )

    return response['id']

def update_project(datazone_client, identifier, domain_id, project_name, project_description):
    userParameters=[
    {
        'environmentConfigurationName': 'datazone-project',
        'environmentParameters': [
            {
                'name': 'string',
                'value': 'string'
            },
        ]
    }]
    response = datazone_client.update_project(
        domainIdentifier=domain_id,
        identifier=identifier,
        name=project_name,
        #glossaryTerms=project_glossary_terms,
        description=project_description
    )
    return response['id']

def delete_project(datazone_client, domain_id, identifier):
    datazone_client.delete_project(
        domainIdentifier=domain_id,
        identifier=identifier,
        skipDeletionCheck=True
    )

def add_project_owner(datazone_client, domain_id, project_id, project_owner, owner_type):
    log.info('project owner: %s', project_owner)
    for owner in project_owner:
        member_type = { owner_type + 'Identifier': owner}
        datazone_client.create_project_membership(
            designation='PROJECT_OWNER',
            domainIdentifier=domain_id,
            member=member_type,
            projectIdentifier=project_id
        )

def set_domain_policy(datazone_client, domain_id, domain_unit_id, domain_owner):   
    try:
        getUserProfile = datazone_client.get_user_profile(
            domainIdentifier=domain_id,
            type='IAM',
            userIdentifier=domain_owner
        )
    except datazone_client.exceptions.ResourceNotFoundException:
        #if len(getUserProfile['details']) == 0:
        log.info('Create user profile')
        datazone_client.create_user_profile(
            domainIdentifier=domain_id,
            userIdentifier=domain_owner,
            userType='IAM_ROLE'
            )
    domain_unit_id = datazone_client.get_domain(
            identifier=domain_id
        )['rootDomainUnitId']    
    owners = {
                'user': {
                    'userIdentifier': domain_owner
                }
        }
    project_policy = {
                "createProject": {
                    "includeChildDomainUnits": True
                }
        }
    datazone_client.add_policy_grant(
            domainIdentifier=domain_id,
            entityIdentifier=domain_unit_id,
            entityType='DOMAIN_UNIT',
            principal=owners,
            policyType='CREATE_PROJECT_FROM_PROJECT_PROFILE',
            detail=project_policy
        )
    
def sendResponseCfn(event, context, responseStatus, identifier, response_data):

    response_url = event['ResponseURL']
    
    response_body = {
        'Status': responseStatus,
        'Reason': f'See details in CloudWatch Log Stream: {context.log_stream_name}',
        'PhysicalResourceId': identifier,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': response_data
    }
    
    json_response_body = json.dumps(response_body)
    
    log.info(f"Response body: {json_response_body}")
    
    headers = {
        'content-type': '',
        'content-length': str(len(json_response_body))
    }
    
    http = urllib3.PoolManager()
    
    try:
        response = http.request('PUT', response_url,
                              headers=headers,
                              body=json_response_body)
        log.info(f"CloudFormation response status code: {response.status}")
        
    except Exception as e:
        log.error(f"Failed to send CloudFormation response: {str(e)}")

def timeout_handler(_signal, _frame):
    '''Handle SIGALRM'''
    raise Exception('Time exceeded')


signal.signal(signal.SIGALRM, timeout_handler)
