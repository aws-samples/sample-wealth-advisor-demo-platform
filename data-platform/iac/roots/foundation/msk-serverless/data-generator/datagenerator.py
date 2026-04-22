import logging
from datetime import datetime
from faker import Faker
import random
import string
import uuid
import os

# Configure logging
logger = logging.getLogger()
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logger.setLevel(getattr(logging, log_level))

# Initialize Faker once as a global instance for better performance
fake = Faker()

def generate_random_string(length):
    """Generate a random alphanumeric string of specified length.
    
    Args:
        length (int): Length of the string to generate
        
    Returns:
        str: Random alphanumeric string
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_random_string_ascii(length):
    """Generate a random uppercase ASCII string of specified length.
    
    Args:
        length (int): Length of the string to generate
        
    Returns:
        str: Random uppercase ASCII string
    """
    return ''.join(random.choices(string.ascii_uppercase, k=length))


def get_intra_day_event():
    """Generate a single intra-day transaction event.
    
    Returns:
        Event: A transaction event object
    """
    transaction_counter = fake.random_number(digits=5)
    account_number = fake.random_number(digits=6)
    trade_date_quantity = fake.random_number(digits=3)
    transaction_type = random.choice(['BUY', 'SELL'])
    multiplier = 1 if transaction_type == 'BUY' else -1
    settle_amount = trade_date_quantity * random.randint(10, 100) * multiplier

    # Determine source dataset name with occasional "poison" value for testing
    source_dataset_name = "source_dataset_1"
    if random.randint(1, 10) == 1:
        source_dataset_name = "poison"
        logger.debug(f"Generated poison record for account {account_number}")

    # Create transaction object
    transaction = RealTimeTransaction(
        id=transaction_counter,
        transactionSourceName="TransactionSource1",
        sourceTransactionId=fake.random_number(digits=10),
        sourceTransactionEntryTime=datetime.now().isoformat(),
        accountNumber=account_number,
        security=generate_random_string_ascii(3),
        transactionType=transaction_type,
        transactionEventType=random.choice(['NEW', 'AMEND', 'CANCEL']),
        tradeDate=fake.past_datetime().isoformat(),
        settleDate=fake.past_datetime().isoformat(),
        settleCurrency="USD",
        tradeQuantity=trade_date_quantity,
        settleAmount=settle_amount
    )
    
    # Create event wrapper
    transaction_event = Event(
        version="1.0",
        eventType="TRANSACTION_RECORD",
        eventCreationTime=datetime.now().isoformat(),
        sourceDatasetName=source_dataset_name,
        sourcePartition="1",
        sourceOffset="1",
        account=account_number,
        payloadType="TransactionEventPayload",
        payload=transaction,
        additional=False
    )

    return transaction_event


class Event:
    """Event wrapper for all event types."""

    def __init__(self,
                 version,
                 eventType,
                 eventCreationTime,
                 sourceDatasetName,
                 sourcePartition,
                 sourceOffset,
                 account,
                 payloadType,
                 payload,
                 additional):
        """Initialize the event.

        Args:
            version (str): The version
            eventType (str): The event type
            eventCreationTime (str): The event creation time
            sourceDatasetName (str): The source dataset name
            sourcePartition (str): The source partition
            sourceOffset (str): The source offset
            account (str): The account
            payloadType (str): The payload type
            payload (object): The payload object
            additional (bool): Flag for including additional data
        """
        self.version = version
        self.eventType = eventType
        self.eventCreationTime = eventCreationTime
        self.sourceDatasetName = sourceDatasetName
        self.sourcePartition = sourcePartition
        self.sourceOffset = sourceOffset
        self.account = account
        self.payloadType = payloadType
        self.payload = payload
        self.additional = additional

    def to_dict(self):
        """Convert event to dictionary representation.
        
        Returns:
            dict: Dictionary representation of the event
        """
        base_dict = {
            'version': str(self.version),
            'eventType': str(self.eventType),
            'eventCreationTime': str(self.eventCreationTime),
            'sourceDatasetName': str(self.sourceDatasetName),
            'sourcePartition': str(self.sourcePartition),
            'sourceOffset': str(self.sourceOffset),
            'account': str(self.account),
            'payloadType': str(self.payloadType),
            'payload': self.payload.to_dict()
        }
        
        # Optional: Add extra data if flag is set
        if self.additional:
            extra = """
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"""
            base_dict['extra'] = extra
            
        return base_dict


class RealTimeTransaction:
    """Represents a real-time transaction for intra-day events."""

    def __init__(self,
                 id,
                 transactionSourceName,
                 sourceTransactionId,
                 sourceTransactionEntryTime,
                 accountNumber,
                 security,
                 transactionType,
                 transactionEventType,
                 tradeDate,
                 settleDate,
                 settleCurrency,
                 tradeQuantity,
                 settleAmount):
        """Initialize the real-time transaction.

        Args:
            id (int): The transaction ID
            transactionSourceName (str): The transaction source name
            sourceTransactionId (int): The source transaction ID
            sourceTransactionEntryTime (str): The source transaction entry time
            accountNumber (int): The account number
            security (str): The security code
            transactionType (str): The transaction type (BUY/SELL)
            transactionEventType (str): The transaction event type (NEW/AMEND/CANCEL)
            tradeDate (str): The trade date
            settleDate (str): The settle date
            settleCurrency (str): The settle currency
            tradeQuantity (int): The trade quantity
            settleAmount (float): The settle amount
        """
        self.id = id
        self.transactionSourceName = transactionSourceName
        self.sourceTransactionId = sourceTransactionId
        self.sourceTransactionEntryTime = sourceTransactionEntryTime
        self.accountNumber = accountNumber
        self.security = security
        self.transactionType = transactionType
        self.transactionEventType = transactionEventType
        self.tradeDate = tradeDate
        self.settleDate = settleDate
        self.settleCurrency = settleCurrency
        self.tradeQuantity = tradeQuantity
        self.settleAmount = settleAmount

    def to_dict(self):
        """Convert transaction to dictionary representation.
        
        Returns:
            dict: Dictionary representation of the transaction
        """
        return {
            'id': str(self.id),
            'transactionSourceName': str(self.transactionSourceName),
            'sourceTransactionId': str(self.sourceTransactionId),
            'sourceTransactionEntryTime': str(self.sourceTransactionEntryTime),
            'accountNumber': str(self.accountNumber),
            'security': str(self.security),
            'transactionType': str(self.transactionType),
            'transactionEventType': str(self.transactionEventType),
            'tradeDate': str(self.tradeDate),
            'settleDate': str(self.settleDate),
            'settleCurrency': str(self.settleCurrency),
            'tradeQuantity': str(self.tradeQuantity),
            'settleAmount': str(self.settleAmount)
        }

# Stock tickers for realistic security IDs
SYMBOLS = [
    "WTI", "WNC", "WAB", "WAFD", "WBA", "WD", "WBX", "WMT", "WRBY", "WBD", 
    "WMG", "HCC", "WASH", "WCN", "WM", "WAT", "WSBF", "WSO", "WTS", "WVE", 
    "W", "WAY", "WDFC", "WFRD", "WEAV", "WBS", "WBTN", "BULL", "WEC", "WB", 
    "WFC", "WELL", "WEN", "HOWL", "WRD", "WERN", "WSBC", "WCC", "WTBA", "WFG", 
    "WST", "WABC", "WAL", "WDC", "WES", "WU", "WLKP", "WLK", "WPRT", "WEST", 
    "WWR", "WEX", "WY", "WPM", "UP", "WHR", "WHF", "WSR", "WOW", "WLY", 
    "WLDN", "WMB", "WSM", "WTW", "WSC", "WIMI", "WING", "WGO", "WTFC", "WIT", 
    "WBAT", "GDE", "WT", "USDU", "WCLD", "XSOE", "ELD", "DEM", "CEW", "DGS", 
    "GCC", "EUDG", "HEDJ", "DFE", "OPPE", "USFR", "DNL", "EPI", "AIVI", "DLS", 
    "IHDG", "DXJ", "DFJ", "DXJS", "AIVL", "DLN", "DON", "DGRW", "QGRW", "EES", 
    "WTV", "AGGY", "USMF", "WIX", "KLG", "MAPS", "WNS", "WOLF", "WWW", "WDS", 
    "WWD", "WDAY", "WKHS", "WK", "WKSP", "WKC", "WOR", "WS", "WPC", "WPP", 
    "WRAP", "WSFS", "WH", "WYNN", "XFOR", "XBIT", "XEL", "XNCR", "XHR", "XENE", 
    "XERS", "XRX", "XOMA", "XMTR", "XP", "XPEL", "XPEV", "XIFR", "XPO", "XPOF", 
    "XNET", "XYL", "YMAB", "YALA", "YSG", "YELP", "YETI", "YEXT", "YRD", "YORW", 
    "DAO", "YPF", "YUM", "YUMC", "ZLAB", "ZBRA", "ZDGE", "ZK", "ZEPP", "ZETA", 
    "ZVRA", "ZH", "ZD", "ZG", "Z", "ZIM", "ZBH", "ZIMV", "ZION", "ZIP", 
    "ZTS", "ZM", "GTM", "ZS", "ZTO", "ZUMZ", "ZWS", "ZYME", "ZYXI"
]

MARKET_CENTERS = ["Y", "Z", "A", "X", "C", "U", "M", "L", "N", "D", "T", "V", "S"]


def get_trade_event():
    """Generate a single trade event.
    
    Returns:
        Trade: A trade event object
    """
    m = "T"
    ts = generate_timestamp()
    sy = random.choice(SYMBOLS)
    mc = random.choice(MARKET_CENTERS)
    e = fake.random_number(digits=12)
    lp = round(random.uniform(1.0, 1000.0), 2)
    ls = fake.random_number(digits=3)
    cv = fake.random_number(digits=5)
    sv = fake.random_number(digits=5)
    f = "1"
 
    trade = Trade(m=m, ts=ts, sy=sy, mc=mc, e=e, lp=lp, ls=ls, cv=cv, sv=sv, f=f)
    
    logger.debug(f"Generated trade event for symbol {sy} at market center {mc}")
    return trade


class Trade:
    """Represents a trade message."""

    def __init__(self,
                 m,
                 ts,
                 sy,
                 mc,
                 e,
                 lp,
                 ls,
                 cv,
                 sv,
                 f):
        """Initialize the trade.

        Args:
            m (str): The message type
            ts (str): The timestamp
            sy (str): The symbol
            mc (str): The market center
            e (int): The execution ID
            lp (float): The last price
            ls (int): The last size
            cv (int): The cumulative volume
            sv (int): The national volume
            f (str): The flags
        """
        self.m = m
        self.ts = ts
        self.sy = sy
        self.mc = mc
        self.e = e
        self.lp = lp
        self.ls = ls
        self.cv = cv
        self.sv = sv
        self.f = f

    def to_dict(self):
        """Convert trade to dictionary representation.
        
        Returns:
            dict: Dictionary representation of the trade
        """
        return {
            'message_type': str(self.m),
            'timestamp': str(self.ts),
            'symbol': str(self.sy),
            'market_center': str(self.mc),
            'execution_id': str(self.e),
            'last_price': str(self.lp),
            'last_size': str(self.ls),
            'cumulative_volume': str(self.cv),
            'national_volume': str(self.sv),
            'flags': str(self.f)
        }


def generate_timestamp() -> str:
    """Calculate the number of nanoseconds since midnight of the current day.
    
    Returns:
        str: Nanoseconds elapsed since midnight as a string
    """
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate the difference and convert to nanoseconds
    delta = now - midnight
    seconds_since_midnight = delta.total_seconds()
    nanoseconds = int(seconds_since_midnight * 1_000_000_000)
    
    return str(nanoseconds)


def main():
    """Main function for testing the module directly."""
    # Configure logging for direct execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Generate a single intra-day transaction event
    intra_day_event = get_intra_day_event()
    
    # Print the event as a dictionary
    logger.info("Generated intra-day event:")
    logger.info(str(intra_day_event.to_dict()))
    
    # Generate a trade event
    trade_event = get_trade_event()
    
    # Print the trade event as a dictionary
    logger.info("Generated trade event:")
    logger.info(str(trade_event.to_dict()))
    
if __name__ == "__main__":
    main()
