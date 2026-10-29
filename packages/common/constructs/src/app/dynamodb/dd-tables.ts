import { RemovalPolicy } from 'aws-cdk-lib';
import {
  AttributeType,
  BillingMode,
  Table,
  TableEncryption,
} from 'aws-cdk-lib/aws-dynamodb';
import { Key } from 'aws-cdk-lib/aws-kms';
import { Construct } from 'constructs';

export class DDSessionsTable extends Table {
  constructor(scope: Construct, id: string) {
    const encryptionKey = new Key(scope, `${id}Key`, {
      description: 'CMK for DD Sessions DynamoDB table',
      enableKeyRotation: true,
    });

    super(scope, id, {
      billingMode: BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'session_id', type: AttributeType.STRING },
      encryption: TableEncryption.CUSTOMER_MANAGED,
      encryptionKey,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: RemovalPolicy.DESTROY,
    });
  }
}

export class DDReportsTable extends Table {
  constructor(scope: Construct, id: string) {
    const encryptionKey = new Key(scope, `${id}Key`, {
      description: 'CMK for DD Reports DynamoDB table',
      enableKeyRotation: true,
    });

    super(scope, id, {
      billingMode: BillingMode.PAY_PER_REQUEST,
      partitionKey: { name: 'session_id', type: AttributeType.STRING },
      encryption: TableEncryption.CUSTOMER_MANAGED,
      encryptionKey,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: RemovalPolicy.DESTROY,
    });
  }
}
