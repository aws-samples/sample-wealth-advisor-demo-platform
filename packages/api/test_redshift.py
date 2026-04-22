#!/usr/bin/env python3
"""Test Redshift connection and query advisor_monthly_aum view."""
import sys
import os

# Add to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../portfolio_data_access'))

from wealth_management_portal_portfolio_data_access.engine import iam_connection_factory

try:
    print("Connecting to Redshift...")
    conn_factory = iam_connection_factory()
    
    with conn_factory() as conn, conn.cursor() as cur:
        print("Connected! Querying advisor_monthly_aum...")
        cur.execute("SELECT COUNT(*) FROM public.advisor_monthly_aum")
        count = cur.fetchone()[0]
        print(f"Total rows: {count}")
        
        if count > 0:
            cur.execute("SELECT * FROM public.advisor_monthly_aum LIMIT 5")
            cols = [d[0] for d in cur.description]
            print(f"Columns: {cols}")
            for row in cur.fetchall():
                print(row)
        else:
            print("View is empty!")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
