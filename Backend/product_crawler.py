from firecrawl import Firecrawl
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional,Any
import requests
from urllib.robotparser import RobotFileParser
from pydantic import BaseModel, Field,ValidationError


# Define the schema for product data extraction
class ProductData(BaseModel):
    """Schema for structured product data extraction"""
    product_title: str = Field(description="The name or title of the product, course, certification, or workshop")
    product_description: str = Field(description="A detailed description of what the product/course/certification/workshop offers")
    product_pricing: str = Field(description="The price or cost information. Include currency symbol. If free, return 'Free'. If not found, return 'N/A'")
    product_type: str = Field(description="The type of offering. Must be one of: 'course', 'certification', 'workshop', or 'product'")


def crawl_firecrawl(url: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Crawl a single URL using Firecrawl's JSON (structured) mode.
    Returns the extracted JSON (as a dict) or None on error.
    """
    try:
        app = Firecrawl(api_key=api_key)

        result = app.scrape(
            url=url,
            formats=[{
                "type": "json",
                "schema": ProductData
            }],
            only_main_content=False,
            timeout=120000
        )

        # Debug: show the result repr to see its structure (uncomment while debugging)
        # print("DEBUG result repr:", repr(result))
        # print("DEBUG result:", result)

        # Firecrawl’s SDK should expose the structured JSON via an attribute `json`
        payload = None
        # Try direct attribute
        if hasattr(result, "json") and isinstance(getattr(result, "json"), dict):
            payload = getattr(result, "json")
        else:
            # Fallback: some SDKs nest under `data` or similar
            # e.g. result.data["json"] if result.data is dict
            data = getattr(result, "data", None)
            if isinstance(data, dict) and "json" in data:
                payload = data["json"]
        
        if payload is None:
            # Could not find JSON payload
            raise RuntimeError(f"No JSON payload found in Firecrawl result: {result}")

        # Validate (and normalize) via Pydantic
        try:
            pd = ProductData(**payload)
            # return the validated dict
            return pd.dict()
        except ValidationError as ve:
            # If validation fails, warn & return raw payload
            print("Warning: validation error for payload:", ve)
            return payload

    except Exception as e:
        print(f"Error crawling {url}: {e}")
        return None


def extract_company_links(website_url: str) -> List[str]:
    """
    Extract all crawlable links from a company website using robots.txt and sitemaps.
    Only returns links containing keywords: course, certification, workshop, or product.
    
    Args:
        website_url: The company's official website URL
    
    Returns:
        List of filtered URLs to crawl
    """
    parsed_url = urlparse(website_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    print(f"\n🔍 Starting link extraction for: {base_url}")
    
    # Initialize robot parser
    robot_parser = RobotFileParser()
    robot_parser.set_url(urljoin(base_url, '/robots.txt'))
    
    try:
        robot_parser.read()
        print("✓ Successfully read robots.txt")
    except Exception as e:
        print(f"⚠ Warning: Could not read robots.txt: {str(e)}")
        return []
    
    # Get sitemap URLs from robots.txt
    sitemap_urls = []
    try:
        response = requests.get(urljoin(base_url, '/robots.txt'), timeout=10)
        if response.status_code == 200:
            for line in response.text.split('\n'):
                if line.lower().startswith('sitemap:'):
                    sitemap_url = line.split(':', 1)[1].strip()
                    sitemap_urls.append(sitemap_url)
            
            if sitemap_urls:
                print(f"✓ Found {len(sitemap_urls)} sitemap(s) in robots.txt")
    except Exception as e:
        print(f"⚠ Error fetching robots.txt: {str(e)}")
    
    # If no sitemaps found, try default locations
    if not sitemap_urls:
        print("ℹ No sitemaps in robots.txt, trying default locations...")
        sitemap_urls = [
            urljoin(base_url, '/sitemap.xml'),
            urljoin(base_url, '/sitemap_index.xml'),
            urljoin(base_url, '/sitemap-index.xml'),
        ]
    
    # Extract all URLs from sitemaps
    all_urls = set()
    keywords = ['course', 'certification', 'workshop', 'product']
    visited_sitemaps = set()  # Track visited sitemaps to avoid duplicates
    
    for sitemap_url in sitemap_urls:
        if sitemap_url not in visited_sitemaps:
            print(f"\n📄 Parsing sitemap: {sitemap_url}")
            urls = _parse_sitemap(sitemap_url, robot_parser, visited_sitemaps, keywords)
            all_urls.update(urls)
    
    print(f"\n📊 Summary:")
    print(f"   Total relevant URLs found: {len(all_urls)}")
    
    return list(all_urls)


def _parse_sitemap(sitemap_url: str, robot_parser: RobotFileParser, visited_sitemaps: set = None, keywords: List[str] = None) -> set:
    """
    Recursively parse sitemap and return only URLs containing keywords.
    Handles nested sitemaps (sitemap index files).
    
    Args:
        sitemap_url: URL of the sitemap to parse
        robot_parser: RobotFileParser instance
        visited_sitemaps: Set of already visited sitemaps to avoid infinite loops
        keywords: List of keywords to filter URLs (e.g., ['course', 'certification'])
    
    Returns:
        Set of filtered URLs found in the sitemap
    """
    if visited_sitemaps is None:
        visited_sitemaps = set()
    
    if keywords is None:
        keywords = ['course', 'certification', 'workshop', 'product']
    
    # Avoid infinite loops
    if sitemap_url in visited_sitemaps:
        return set()
    
    visited_sitemaps.add(sitemap_url)
    urls = set()
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(sitemap_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"   ✗ Failed to fetch: Status {response.status_code}")
            return urls
        
        # Parse XML
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            print(f"   ✗ XML parse error: {str(e)}")
            return urls
        
        # Define namespaces
        namespaces = {
            'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        }
        
        # Check if this is a sitemap index (contains other sitemaps)
        sitemap_elements = root.findall('.//sm:sitemap/sm:loc', namespaces)
        if not sitemap_elements:
            sitemap_elements = root.findall('.//sitemap/loc')
        
        if sitemap_elements:
            # This is a sitemap index, recursively parse each sitemap
            # But only process sitemaps that might contain our keywords
            relevant_sitemaps = []
            for elem in sitemap_elements:
                nested_sitemap_url = elem.text.strip()
                nested_lower = nested_sitemap_url.lower()
                
                # Check if sitemap name contains any keyword (e.g., "courses-sitemap.xml")
                if any(keyword in nested_lower for keyword in keywords):
                    relevant_sitemaps.append(nested_sitemap_url)
            
            if relevant_sitemaps:
                print(f"   ↳ Found {len(relevant_sitemaps)} relevant nested sitemap(s) (out of {len(sitemap_elements)})")
                for nested_sitemap_url in relevant_sitemaps:
                    nested_urls = _parse_sitemap(nested_sitemap_url, robot_parser, visited_sitemaps, keywords)
                    urls.update(nested_urls)
            else:
                print(f"   ⊘ Skipped {len(sitemap_elements)} nested sitemap(s) (no keyword matches)")
        else:
            # This is a regular sitemap, extract and filter URLs
            url_elements = root.findall('.//sm:url/sm:loc', namespaces)
            if not url_elements:
                url_elements = root.findall('.//url/loc')
            
            # Filter URLs by keywords during extraction
            filtered_count = 0
            for elem in url_elements:
                url = elem.text.strip()
                url_lower = url.lower()
                
                # Check if URL contains any keyword AND is allowed by robots.txt
                if any(keyword in url_lower for keyword in keywords):
                    if robot_parser.can_fetch("*", url):
                        urls.add(url)
                        filtered_count += 1
            
            if filtered_count > 0:
                print(f"   ✓ Found {filtered_count} relevant URL(s) (out of {len(url_elements)} total)")
            else:
                print(f"   ⊘ No relevant URLs found (0 out of {len(url_elements)})")
    
    except requests.RequestException as e:
        print(f"   ✗ Request error: {str(e)}")
    except Exception as e:
        print(f"   ✗ Unexpected error: {str(e)}")
    
    return urls


def create_company_dataset(company_url: str, api_key: str, max_pages: int = 50) -> List[Dict[str, str]]:
    """
    Complete pipeline: Extract links from company website and crawl them with Firecrawl.
    
    Args:
        company_url: Company's official website URL
        api_key: Firecrawl API key
        max_pages: Maximum number of pages to crawl (to avoid excessive API usage)
    
    Returns:
        List of product data dictionaries
    """
    print("=" * 70)
    print("🚀 COMPANY WEBSITE CRAWLER - AI-Powered Data Extraction")
    print("=" * 70)
    
    # Step 1: Extract links
    print("\n📍 STEP 1: Extracting links from company website")
    print("-" * 70)
    links = extract_company_links(company_url)
    
    if not links:
        print("\n❌ No relevant links found. Please check the website URL.")
        return []
    
    # Limit number of pages
    links = links[:max_pages]
    
    print(f"\n✓ Will crawl {len(links)} page(s)")
    
    # Step 2: Crawl each link with Firecrawl
    print("\n" + "=" * 70)
    print("📍 STEP 2: Crawling pages with Firecrawl AI")
    print("-" * 70)
    
    dataset = []
    
    for i, link in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] 🔗 {link}")
        
        try:
            product_data = crawl_firecrawl(link, api_key)
            
            if product_data:
                dataset.append(product_data)
                print(f"   ✓ Extracted: {product_data['product_type'].upper()}")
                print(f"   📝 Title: {product_data['product_title'][:60]}...")
                print(f"   💰 Price: {product_data['product_pricing']}")
            else:
                print(f"   ⊘ Skipped (no relevant product data)")
                
        except Exception as e:
            print(f"   ✗ Error: {str(e)}")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 DATASET SUMMARY")
    print("=" * 70)
    print(f"Total products extracted: {len(dataset)}")
    
    if dataset:
        # Count by type
        type_counts = {}
        for item in dataset:
            ptype = item['product_type']
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
        
        print("\n📈 Breakdown by type:")
        for ptype, count in type_counts.items():
            print(f"   • {ptype.capitalize()}: {count}")
        
        # Show sample
        print("\n" + "=" * 70)
        print("📋 SAMPLE PRODUCT")
        print("=" * 70)
        sample = dataset[0]
        print(f"Title:       {sample['product_title']}")
        print(f"Description: {sample['product_description'][:150]}...")
        print(f"Pricing:     {sample['product_pricing']}")
        print(f"Type:        {sample['product_type']}")
        # print(f"URL:         {sample['url']}")
    
    return dataset


# Example usage
if __name__ == "__main__":
    # Configuration
    FIRECRAWL_API_KEY = "fc-007a697ab3494d0d980e7a53de598a7d"  # Replace with your actual API key
    COMPANY_WEBSITE = "https://www.netcomlearning.com/"  # Replace with target website
    MAX_PAGES = 20  # Limit to avoid excessive API usage
    
    # Run the complete pipeline
    dataset = create_company_dataset(
        company_url=COMPANY_WEBSITE,
        api_key=FIRECRAWL_API_KEY,
        max_pages=MAX_PAGES
    )
    
    # Optional: Save to file
    if dataset:
        import json
        
        output_file = "company_products_dataset.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Dataset saved to: {output_file}")