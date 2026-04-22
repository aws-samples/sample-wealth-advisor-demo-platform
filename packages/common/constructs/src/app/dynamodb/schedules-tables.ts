import { RemovalPolicy } from 'aws-cdk-lib';
import {
  AttributeType,
  BillingMode,
  GlobalSecondaryIndexProps,
  Table,
  TableEncryption,
} from 'aws-cdk-lib/aws-dynamodb';
import { Key } from 'aws-cdk-lib/aws-kms';
import { Construct } from 'constructs';

export class SchedulesTable extends Table {
  constructor(scope: Construct, id: string) {
    const encryptionKey = new Key(scope, `${id}Key`, {
      description: 'CMK for Schedules DynamoDB table',
      enableKeyRotation: true,
    });

    super(scope, id, {
      billingMode: BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'PK', type: AttributeType.STRING },
      sortKey: { name: 'SK', type: AttributeType.STRING },
      encryption: TableEncryption.CUSTOMER_MANAGED,
      encryptionKey,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: RemovalPolicy.RETAIN,
    });

    this.addGlobalSecondaryIndex({
      indexName: 'GSI1',
      partitionKey: { name: 'GSI1PK', type: AttributeType.STRING },
      sortKey: { name: 'GSI1SK', type: AttributeType.STRING },
    } as GlobalSecondaryIndexProps);
  }
}

export class ScheduleResultsTable extends Table {
  constructor(scope: Construct, id: string) {
    const encryptionKey = new Key(scope, `${id}Key`, {
      description: 'CMK for Schedule Results DynamoDB table',
      enableKeyRotation: true,
    });

    super(scope, id, {
      billingMode: BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'PK', type: AttributeType.STRING },
      sortKey: { name: 'SK', type: AttributeType.STRING },
      timeToLiveAttribute: 'ttl',
      encryption: TableEncryption.CUSTOMER_MANAGED,
      encryptionKey,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: RemovalPolicy.RETAIN,
    });
  }
}
