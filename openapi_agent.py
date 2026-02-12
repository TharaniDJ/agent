"""
OpenAPI Spec Finder Agent
Uses Claude to navigate docs and extract OpenAPI spec URLs
"""

import anthropic
import json
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

class OpenAPIAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.conversation_history = []

    def fetch_page(self, url: str) -> Dict[str, Any]:
        """Fetch a webpage and return its content"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (OpenAPI Spec Finder Bot)'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Check if it's already JSON/YAML
            content_type = response.headers.get('content-type', '')
            if 'json' in content_type:
                return {
                    'url': url,
                    'type': 'json',
                    'content': response.text[:50000]  # Limit size
                }
            elif 'yaml' in content_type or url.endswith(('.yaml', '.yml')):
                return {
                    'url': url,
                    'type': 'yaml',
                    'content': response.text[:50000]
                }

            # Otherwise parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style tags
            for tag in soup(['script', 'style', 'nav', 'footer']):
                tag.decompose()

            text = soup.get_text(separator='\n', strip=True)

            # Extract all links
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(x in href.lower() for x in ['openapi', 'swagger', 'api-spec', '.json', '.yaml', '.yml']):
                    links.append({
                        'text': a.get_text(strip=True),
                        'href': href
                    })

            return {
                'url': url,
                'type': 'html',
                'content': text[:20000],  # Limit size
                'relevant_links': links
            }

        except Exception as e:
            return {
                'url': url,
                'type': 'error',
                'error': str(e)
            }

    def is_openapi_spec(self, content: str) -> bool:
        """Quick check if content looks like OpenAPI spec"""
        try:
            data = json.loads(content)
            return 'openapi' in data or 'swagger' in data
        except:
            # Check YAML indicators
            return 'openapi:' in content or 'swagger:' in content

    def run(self, starting_url: str, max_iterations: int = 10) -> Optional[str]:
        """
        Main agent loop - navigates from starting URL to find OpenAPI spec
        Returns the URL of the spec file
        """

        system_prompt = """You are an OpenAPI spec finder agent. Your goal is to find and return the direct URL to an OpenAPI specification file (JSON or YAML format).

You have access to a fetch_page tool that retrieves web pages. Use it strategically to:
1. Start at the given documentation URL
2. Look for links to API documentation, OpenAPI specs, or Swagger files
3. Follow promising links until you find the actual spec file URL
4. Return the final URL when you find it

The spec URL typically:
- Ends in .json, .yaml, or .yml
- Contains keywords like 'openapi', 'swagger', 'api-spec'
- Is often at paths like /api/openapi.json, /docs/swagger.yaml, etc.

When you find a URL that points directly to a spec file, respond with:
SPEC_FOUND: <url>

If you determine no spec exists after thorough search, respond with:
NO_SPEC_FOUND"""

        tools = [
            {
                "name": "fetch_page",
                "description": "Fetches a web page and returns its content, links, and metadata. Use this to navigate through documentation.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to fetch"
                        }
                    },
                    "required": ["url"]
                }
            }
        ]

        # Initialize with starting instruction
        messages = [
            {
                "role": "user",
                "content": f"Find the OpenAPI spec URL starting from: {starting_url}"
            }
        ]

        for iteration in range(max_iterations):
            print(f"\n--- Iteration {iteration + 1} ---")

            response = self.client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=4000,
                system=system_prompt,
                tools=tools,
                messages=messages
            )

            print(f"Stop reason: {response.stop_reason}")

            # Check if agent is done
            for block in response.content:
                if block.type == "text":
                    print(f"Claude: {block.text}")

                    if "SPEC_FOUND:" in block.text:
                        spec_url = block.text.split("SPEC_FOUND:")[1].strip()
                        return spec_url

                    if "NO_SPEC_FOUND" in block.text:
                        return None

            # Handle tool use
            if response.stop_reason == "tool_use":
                # Add assistant response to messages
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Process tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        if block.name == "fetch_page":
                            url = block.input["url"]
                            print(f"Fetching: {url}")

                            result = self.fetch_page(url)

                            # Check if we directly hit a spec
                            if result['type'] in ['json', 'yaml']:
                                if self.is_openapi_spec(result['content']):
                                    print(f"✓ Found OpenAPI spec directly at: {url}")
                                    return url

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, indent=2)
                            })

                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

            elif response.stop_reason == "end_turn":
                # Agent stopped without finding spec
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })
                messages.append({
                    "role": "user",
                    "content": "Continue searching or conclude with SPEC_FOUND or NO_SPEC_FOUND"
                })

        print("\n⚠ Max iterations reached")
        return None


def main():
    # Example usage
    import os

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY environment variable")
        return

    agent = OpenAPIAgent(api_key)

    # Test URLs - replace with your targets
    test_urls = [
        "https://docs.stripe.com/api",
        # Add more documentation URLs here
    ]

    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Searching: {url}")
        print('='*60)

        spec_url = agent.run(url, max_iterations=8)

        if spec_url:
            print(f"\n✓ SUCCESS: {spec_url}")
        else:
            print(f"\n✗ No spec found")


if __name__ == "__main__":
    main()
