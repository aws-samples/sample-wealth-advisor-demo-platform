#!/usr/bin/env python3
"""
Opening Price Generator

This script generates synthetic opening price data in CSV format with randomly generated values.
It creates realistic-looking opening price data for testing and development purposes.

Usage:
    python opening_price_generator.py 
"""

import csv
import datetime
import logging
import os
import random
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants for data generation
MESSAGE_TYPE = "OP"
MARKET_CENTERS = ["Y", "Z", "A", "X", "C", "U", "M", "L", "N", "D", "T", "V", "S"]
OPEN_CLOSE_INDICATORS = ["O", "P"]

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

def generate_timestamp() -> int:
    """
    Calculate the number of nanoseconds since midnight of the current day.
    
    Returns:
        int: Nanoseconds elapsed since midnight
    """
    now = datetime.datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate the difference and convert to nanoseconds
    delta = now - midnight
    seconds_since_midnight = delta.total_seconds()
    nanoseconds = int(seconds_since_midnight * 1_000_000_000)
    
    return str(nanoseconds)

def generate_open_close_indicator() -> str:
    """Generate a random open/close indicator ('O' or 'P')."""
    return random.choice(OPEN_CLOSE_INDICATORS)

def generate_market_center() -> str:
    """Generate a random security ID using real stock tickers."""
    ticker = random.choice(MARKET_CENTERS)
    return ticker

def generate_price() -> float:
    """Generate a random price between $1 and $1000 with 2 decimal places."""
    return round(random.uniform(1.0, 1000.0), 2)

def generate_opening_price(symbol) -> Dict[str, Any]:
    """Generate a single opening price."""
    
    # Base price data
    price = {
        "message_type": MESSAGE_TYPE,
        "timestamp": generate_timestamp(),
        "symbol": symbol,  
        "market_center": generate_market_center(),
        "open_close_indicator": generate_open_close_indicator(),
        "price": generate_price()
    }
    
    return price

def generate_opening_prices() -> List[Dict[str, Any]]:
    """Generate opening prices."""
    logger.info(f"Generating opening prices")
    prices=[]
    for symbol in SYMBOLS:
        prices.append(generate_opening_price(symbol))
    return prices


def write_to_csv(prices: List[Dict[str, Any]], output_file: str) -> None:
    """Write prices to a CSV file."""
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        
        # Get fieldnames from the first order
        if not prices:
            logger.error("No prices to write to CSV")
            return
            
        fieldnames = prices[0].keys()
        
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(prices)
            
        logger.info(f"Successfully wrote {len(prices)} prices to {output_file}")
    except Exception as e:
        logger.warning(f"Error writing to CSV: {e}")
        raise


def main() -> None:
    """Main function to generate and save opening price data."""
    try:
        output_file = "../../../../data/price/price.csv"
        
        prices = generate_opening_prices()
        write_to_csv(prices, output_file)
        logger.info("Data generation completed successfully")
        
    except Exception as e:
        logger.warning(f"Error in data generation: {e}")
        raise


if __name__ == "__main__":
    main()