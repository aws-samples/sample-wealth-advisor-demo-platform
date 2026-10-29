"""Generate all Portfolio DD source documents (14 PDFs across 5 portfolios).

Usage: python scripts/generate_source_docs.py
Output: packages/portfolio_dd/source_docs/*.pdf
"""

import subprocess
import sys
import os

SCRIPTS_DIR = os.path.dirname(__file__)

scripts = [
    "gen_docs_amp.py",
    "gen_docs_pendal.py",
    "gen_docs_macquarie.py",
    "gen_docs_aef.py",
    "gen_docs_hyperion.py",
]

print("=" * 60)
print("Generating all Portfolio DD source documents...")
print("=" * 60)

for script in scripts:
    print(f"\n--- {script} ---")
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, script)],
        capture_output=True,
        text=True,
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)

print("\n" + "=" * 60)
print("All 14 source documents generated successfully!")
print("Output: packages/portfolio_dd/source_docs/")
print("=" * 60)
