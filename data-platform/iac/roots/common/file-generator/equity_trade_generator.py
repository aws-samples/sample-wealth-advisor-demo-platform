#!/usr/bin/env python3
"""
Equity Trade Data Generator

This script generates synthetic equity trade data in CSV format with randomly generated values.
It creates realistic-looking equity trade data for testing and development purposes.

Usage:
    python equity_trade_generator.py [--num_records NUM] [--output_file PATH]
"""

import argparse
import csv
import datetime
import logging
import os
import random
import string
import uuid
from typing import Dict, List, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants for data generation
SIDES = ["BUY", "SELL", "BUY_TO_COVER", "SELL_SHORT"]

# Stock tickers for realistic security IDs
STOCK_TICKERS = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "JPM", 
    "V", "PG", "UNH", "HD", "BAC", "XOM", "AVGO", "MA", "JNJ", "WMT", 
    "CVX", "LLY", "MRK", "KO", "PEP", "ABBV", "COST", "MCD", "CRM", 
    "TMO", "ABT", "ACN", "DHR", "CSCO", "NKE", "ADBE", "TXN", "AMD"
]

# Generate a fixed pool of 500 account IDs
ACCOUNT_IDS = [f"ACC-{''.join(random.choices(string.digits, k=8))}" for _ in range(1000)]


def generate_order_id() -> str:
    """Generate a unique order ID."""
    return str(uuid.uuid4())


def generate_trade_id() -> str:
    """Generate a unique trade ID."""
    return str(uuid.uuid4())


def get_account_id() -> str:
    """Return a random account ID from the fixed pool of 500 accounts."""
    return random.choice(ACCOUNT_IDS)


def generate_security_id() -> str:
    """Generate a random security ID using real stock tickers."""
    ticker = random.choice(STOCK_TICKERS)
    return ticker


def generate_quantity() -> int:
    """Generate a random quantity of shares."""
    # Use a distribution that favors smaller quantities but allows for larger ones
    if random.random() < 0.8:
        return random.randint(1, 1000)
    else:
        return random.randint(1000, 10000)


def generate_price() -> float:
    """Generate a random price between $1 and $1000 with 2 decimal places."""
    return round(random.uniform(1.0, 1000.0), 2)


def generate_timestamp() -> str:
    """Generate a random timestamp from the last 24 hours."""
    now = datetime.datetime.now()
    random_seconds = random.randint(0, 86400)  # 24 hours in seconds
    random_time = now - datetime.timedelta(seconds=random_seconds)
    return random_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def generate_equity_trade() -> Dict[str, Any]:
    """Generate a single equity trade with random data."""
    side = random.choice(SIDES)
    quantity = generate_quantity()

    # Base trade data
    trade = {
        "order_id": generate_order_id(),
        "trade_id": generate_trade_id(),
        "account_id": get_account_id(),  # Using the fixed pool of account IDs
        "security_id": generate_security_id(),
        "side": side,
        "quantity": quantity,
        "price": generate_price(),
        "execution_time": generate_timestamp(),
        "fee": quantity * 0.01,
        "commission": quantity * 0.02
    }
    
    return trade


def generate_equity_trades(num_records: int) -> List[Dict[str, Any]]:
    """Generate multiple equity trades."""
    logger.info(f"Generating {num_records} equity trades")
    return [generate_equity_trade() for _ in range(num_records)]


def write_to_csv(trades: List[Dict[str, Any]], output_file: str) -> None:
    """Write trades to a CSV file."""
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        
        # Get fieldnames from the first trade
        if not trades:
            logger.error("No trades to write to CSV")
            return
            
        fieldnames = trades[0].keys()
        
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(trades)
            
        logger.info(f"Successfully wrote {len(trades)} trades to {output_file}")
    except Exception as e:
        logger.warning(f"Error writing to CSV: {e}")
        raise


def parse_arguments() -> Tuple[int, str]:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate synthetic equity trade data')
    parser.add_argument('--num_records', type=int, default=10000,
                        help='Number of records to generate (default: 1000)')
    parser.add_argument('--output_file', type=str, default="../../../../data/equity_trades/equity_trades.csv",
                        help='Output CSV file path (default: equity_trades.csv)')
    
    args = parser.parse_args()
    return args.num_records, args.output_file


def main() -> None:
    """Main function to generate and save equity trade data."""
    try:
        num_records, output_file = parse_arguments()
        
        logger.info(f"Starting equity trade data generation: {num_records} records")
        trades = generate_equity_trades(num_records)
        write_to_csv(trades, output_file)
        logger.info("Data generation completed successfully")
        
    except Exception as e:
        logger.warning(f"Error in data generation: {e}")
        raise


if __name__ == "__main__":
    main()