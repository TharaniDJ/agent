"""
Batch process multiple API documentation URLs
"""

import json
from openapi_agent import OpenAPIAgent
import os

# List of API docs to monitor
API_DOCS = [
    {
    "name": "Twilio",
    "docs_url": "https://www.twilio.com/docs/api"
    }
    # Add your APIs here
]

def batch_find_specs(output_file: str = "openapi_specs.json"):
    """Find OpenAPI specs for all configured APIs"""

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY environment variable")

    agent = OpenAPIAgent(api_key)
    results = []

    for api in API_DOCS:
        print(f"\n{'='*70}")
        print(f"Processing: {api['name']}")
        print(f"URL: {api['docs_url']}")
        print('='*70)

        spec_url = agent.run(api['docs_url'], max_iterations=10)

        result = {
            "name": api["name"],
            "docs_url": api["docs_url"],
            "spec_url": spec_url,
            "status": "found" if spec_url else "not_found"
        }

        results.append(result)

        if spec_url:
            print(f"✓ Found: {spec_url}")
        else:
            print(f"✗ Not found")

    # Save results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*70}")
    print(f"Results saved to: {output_file}")
    print('='*70)

    # Summary
    found = sum(1 for r in results if r['status'] == 'found')
    print(f"\nSummary: {found}/{len(results)} specs found")

    for result in results:
        status = "✓" if result['status'] == 'found' else "✗"
        print(f"{status} {result['name']}: {result['spec_url'] or 'Not found'}")

if __name__ == "__main__":
    batch_find_specs()
