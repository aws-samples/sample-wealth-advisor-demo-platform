import boto3
import json
import logging
import os
import socket
import time
import traceback
from multiprocessing import Process
from threading import Thread

from aws_msk_iam_sasl_signer import MSKAuthTokenProvider
from kafka import KafkaProducer
from kafka.errors import KafkaError
from kafka.sasl.oauth import AbstractTokenProvider

import datagenerator

# Configure logging
logger = logging.getLogger()
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.setLevel(getattr(logging, log_level))

# Constants
DEFAULT_PARALLEL = 10
DEFAULT_EXECUTION = "threads"
DEFAULT_TOPIC = "intraday-source-topic"
DEFAULT_DURATION = 15
DEFAULT_SLEEP = 1


class MSKTokenProvider(AbstractTokenProvider):
    """Token provider for MSK IAM authentication."""
    
    def token(self):
        """Generate authentication token for MSK."""
        token, _ = MSKAuthTokenProvider.generate_auth_token(os.environ['AWS_REGION'])
        return token


def get_msk_bootstrap_servers(secret_name):
    """Retrieve MSK bootstrap servers from Secrets Manager.
    
    Args:
        secret_name: Name of the secret containing bootstrap servers
        
    Returns:
        str: Bootstrap servers string
        
    Raises:
        Exception: If secret retrieval fails
    """
    secretsmanager = boto3.client('secretsmanager')
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        logger.warning(f"Failed to retrieve bootstrap servers from secret {secret_name}: {e}")
        raise


def create_kafka_producer(bootstrap_servers, token_provider):
    """Create a Kafka producer with the specified configuration.
    
    Args:
        bootstrap_servers: MSK bootstrap servers string
        token_provider: OAuth token provider for authentication
        
    Returns:
        KafkaProducer: Configured Kafka producer
    """
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        security_protocol='SASL_SSL',
        sasl_mechanism='OAUTHBEARER',
        sasl_oauth_token_provider=token_provider,
        client_id=socket.gethostname(),
        value_serializer=lambda m: json.dumps(m).encode('ascii'),
        acks='all',                   # Wait for all replicas to acknowledge
        retries=3,                    # Retry failed sends
        retry_backoff_ms=100,         # Backoff time between retries
        max_in_flight_requests_per_connection=1,  # Prevent message reordering on retries
        compression_type='gzip'       # Compress messages for efficiency
    )


def publish_events(topic, duration, producer, sleep, event_generator, key_extractor):
    """Generic function to publish events to Kafka.
    
    Args:
        topic: Kafka topic to publish to
        duration: Duration in minutes to run
        producer: Kafka producer instance
        sleep: Sleep time between messages in seconds
        event_generator: Function to generate events
        key_extractor: Function to extract key from event
    """
    counter = 0
    t_end = time.time() + 60 * duration
    logger.info(f"Publishing events to topic {topic} for {duration} minutes")
    
    try:
        while time.time() < t_end:
            event = event_generator()
            event_dict = event.to_dict()
            key = key_extractor(event)
            
            # Log at debug level to avoid excessive logging in production
            logger.debug(f"Sending event to topic {topic}: {event_dict}")
            
            # Send message with callback for better error handling
            producer.send(
                topic, 
                event_dict, 
                key=str(key).encode(encoding='UTF-8')
            ).add_callback(
                lambda metadata: logger.debug(f"Message delivered to {metadata.topic}-{metadata.partition} at offset {metadata.offset}")
            ).add_errback(
                lambda e: logger.error(f"Message delivery failed: {e}")
            )
            
            # Flush periodically instead of after every message for better performance
            counter += 1
            if counter % 10 == 0:  # Flush every 10 messages
                producer.flush()
                
            if sleep > 0:
                time.sleep(sleep)

    except Exception as e:
        logger.error(f"Failed to send messages: {e}")
        logger.debug(traceback.format_exc())
    finally:
        # Ensure final flush before reporting
        producer.flush()
        logger.info(f"Total events produced: {counter}")


def publish_intraday_thread(topic, duration, producer, sleep):
    """Thread function to publish intraday events."""
    publish_events(
        topic=topic,
        duration=duration,
        producer=producer,
        sleep=sleep,
        event_generator=datagenerator.get_intra_day_event,
        key_extractor=lambda event: event.account
    )


def publish_trade_thread(topic, duration, producer, sleep):
    """Thread function to publish trade events."""
    publish_events(
        topic=topic,
        duration=duration,
        producer=producer,
        sleep=sleep,
        event_generator=datagenerator.get_trade_event,
        key_extractor=lambda event: event.mc
    )


def publish_intraday_process(topic, duration, bootstrap_servers, token_provider, sleep):
    """Process function to publish intraday events."""
    producer = create_kafka_producer(bootstrap_servers, token_provider)
    try:
        publish_intraday_thread(topic, duration, producer, sleep)
    finally:
        producer.close()


def publish_trade_process(topic, duration, bootstrap_servers, token_provider, sleep):
    """Process function to publish trade events."""
    producer = create_kafka_producer(bootstrap_servers, token_provider)
    try:
        publish_trade_thread(topic, duration, producer, sleep)
    finally:
        producer.close()


def get_cluster_arn():
    """Retrieve MSK cluster ARN from SSM Parameter Store."""
    app_name = os.environ["APP_NAME"]
    env_name = os.environ["ENV_NAME"]
    param_name = f"/{app_name}/{env_name}/msk/cluster_arn"
    
    logger.info(f"Retrieving cluster ARN from parameter: {param_name}")
    
    ssm_client = boto3.client('ssm')
    try:
        response = ssm_client.get_parameter(Name=param_name)
        cluster_arn = response['Parameter']['Value']
        logger.info(f"Retrieved cluster ARN: {cluster_arn}")
        return cluster_arn
    except Exception as e:
        logger.warning(f"Failed to retrieve cluster ARN: {e}")
        raise


def parse_event_parameters(event):
    """Parse parameters from the Lambda event.
    
    Args:
        event: Lambda event object
        
    Returns:
        tuple: (topic, duration, parallel, execution, sleep)
    """
    # Default values
    topic = DEFAULT_TOPIC
    duration = DEFAULT_DURATION
    parallel = DEFAULT_PARALLEL
    execution = DEFAULT_EXECUTION
    sleep = DEFAULT_SLEEP

    # Try to parse parameters from event body
    input_body = event.get("body", {})
    if input_body:
        try:
            if isinstance(input_body, str):
                json_param = json.loads(input_body)
            else:
                json_param = input_body
                
            topic = json_param.get("topic", topic)
            duration = json_param.get("duration", duration)
            parallel = json_param.get("parallel", parallel)
            execution = json_param.get("execution", execution)
            sleep = json_param.get("sleep", sleep)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse event body as JSON: {e}")
    
    logger.info(f"Using parameters: topic={topic}, duration={duration}, parallel={parallel}, execution={execution}, sleep={sleep}")
    return topic, duration, parallel, execution, sleep


def lambda_handler(event, context):
    """Lambda function handler.
    
    Args:
        event: Lambda event object
        context: Lambda context object
        
    Returns:
        dict: Response object
    """
    logger.info("Starting MSK producer Lambda")
    start_time = time.time()
    
    try:
        # Get cluster ARN (not used directly but kept for logging/debugging)
        cluster_arn = get_cluster_arn()
        
        # Parse parameters from event
        topic, duration, parallel, execution, sleep = parse_event_parameters(event)
        
        # Get bootstrap servers
        msk_endpoint_secret_name = os.environ['GLOBAL_MSK_ENDPOINT']
        msk_bootstrap_servers = get_msk_bootstrap_servers(msk_endpoint_secret_name)
        logger.info(f"Using MSK bootstrap servers: {msk_bootstrap_servers}")
        
        # Create token provider for IAM Auth
        token_provider = MSKTokenProvider()
        
        # Create producer for thread mode
        producer = None
        if execution == "threads":
            producer = create_kafka_producer(msk_bootstrap_servers, token_provider)
        
        # Start workers
        workers = []
        for i in range(parallel):
            if topic == "intraday-source-topic":
                if execution == "threads":
                    worker = Thread(
                        target=publish_intraday_thread, 
                        args=(topic, duration, producer, sleep),
                        name=f"intraday-thread-{i}"
                    )
                else:
                    worker = Process(
                        target=publish_intraday_process, 
                        args=(topic, duration, msk_bootstrap_servers, token_provider, sleep),
                        name=f"intraday-process-{i}"
                    )
            else:
                if execution == "threads":
                    worker = Thread(
                        target=publish_trade_thread, 
                        args=(topic, duration, producer, sleep),
                        name=f"trade-thread-{i}"
                    )
                else:
                    worker = Process(
                        target=publish_trade_process, 
                        args=(topic, duration, msk_bootstrap_servers, token_provider, sleep),
                        name=f"trade-process-{i}"
                    )
            
            workers.append(worker)
            worker.start()
            logger.debug(f"Started worker {i+1}/{parallel}: {worker.name}")
        
        # Wait for all workers to complete
        for worker in workers:
            worker.join()
        
        # Close producer if using threads
        if execution == "threads" and producer:
            producer.close()
        
        execution_time = time.time() - start_time
        logger.info(f"Lambda execution completed successfully in {execution_time:.2f} seconds")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Successfully published events to topic {topic}",
                "workers": parallel,
                "execution_mode": execution,
                "duration_minutes": duration
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        logger.debug(traceback.format_exc())
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }
