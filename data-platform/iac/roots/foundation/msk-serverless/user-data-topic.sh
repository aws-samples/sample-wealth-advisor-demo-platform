#!/bin/bash -ex
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
echo "STARTING MSK TOPIC CREATION SCRIPT"
MSK_CLUSTER_SSM=${msk_cluster_ssm}
MSK_CLUSTER_ARN=$(aws ssm get-parameter --name $MSK_CLUSTER_SSM --query "Parameter.Value" --output text)
echo "MSK CLUSTER ARN: $MSK_CLUSTER_ARN"

# Set Kafka version
MSK_VERSION="2.8.1"
BOOTSTRAP_SERVER=$(aws kafka get-bootstrap-brokers --cluster-arn $${MSK_CLUSTER_ARN} --output text)
echo "BOOTSTRAP SERVER: $BOOTSTRAP_SERVER"

# Install dependencies
echo "Installing dependencies..."
yum -y install java-11
yum -y install wget

# Download and extract Kafka
echo "Downloading Kafka $MSK_VERSION..."
wget https://archive.apache.org/dist/kafka/$MSK_VERSION/kafka_2.13-$MSK_VERSION.tgz
tar -xzf kafka_2.13-$MSK_VERSION.tgz

# Download AWS MSK IAM auth jar
cd kafka_2.13-$MSK_VERSION/libs
wget https://github.com/aws/aws-msk-iam-auth/releases/download/v1.1.1/aws-msk-iam-auth-1.1.1-all.jar
cd ../bin

# Create client properties file
echo "Creating client properties file..."
cat > client.properties << EOF
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
EOF

# Function to create topic if it doesn't exist
create_topic_if_not_exists() {
    local topic_name=$1
    local replication_factor=$2
    local partitions=$3
    
    echo "Checking if topic '$topic_name' exists..."
    
    # List topics and check if the topic exists
    topic_exists=$(./kafka-topics.sh --list --bootstrap-server $BOOTSTRAP_SERVER --command-config client.properties | grep "^$topic_name$" || true)
    
    if [ -z "$topic_exists" ]; then
        echo "Topic '$topic_name' does not exist. Creating..."
        ./kafka-topics.sh --create --bootstrap-server $BOOTSTRAP_SERVER --command-config client.properties \
            --replication-factor $replication_factor --partitions $partitions --topic $topic_name
        echo "Topic '$topic_name' created successfully."
    else
        echo "Topic '$topic_name' already exists. Skipping creation."
    fi
}

# Create topics if they don't exist
echo "Setting up Kafka topics..."
create_topic_if_not_exists "${source_topic_name}" 3 1
create_topic_if_not_exists "${sink_topic_name}" 3 1
create_topic_if_not_exists "${trade_topic_name}" 3 1

# List all topics
echo "Current Kafka topics:"
./kafka-topics.sh --list --bootstrap-server $BOOTSTRAP_SERVER --command-config client.properties

# Return to original directory
cd ../..

# Set up Kafdrop (Kafka UI)
echo "Setting up Kafdrop..."
cat << EOF > kafka.properties
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
EOF

mkdir -p extra-kafdrop-classes
wget --directory-prefix=extra-kafdrop-classes https://github.com/aws/aws-msk-iam-auth/releases/download/v1.1.1/aws-msk-iam-auth-1.1.1-all.jar

echo "Starting Kafdrop container..."
docker run --rm -p 9000:9000 \
    -v $(pwd)/kafka.properties:/tmp/kafka.properties:ro \
    -v $(pwd)/extra-kafdrop-classes:/extra-classes:ro \
    -e KAFKA_BROKERCONNECT=$BOOTSTRAP_SERVER \
    -e SERVER_SERVLET_CONTEXTPATH="/" \
    -e KAFKA_PROPERTIES_FILE=/tmp/kafka.properties \
    obsidiandynamics/kafdrop

echo "SCRIPT COMPLETED SUCCESSFULLY"
