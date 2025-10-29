"""
Web Crawler Module for Sitemap Processing
Handles XML sitemap parsing, URL extraction, and page metadata fetching.
"""

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
import json
# ============================================================================
# CONFIGURATION
# ============================================================================

DELAY_BETWEEN_REQUESTS = 1  # seconds
TIMEOUT = 10  # seconds
MAX_COURSES_TO_SCRAPE = 200
MAX_DEPTH = 3
SORT_BY_DATE = True

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Sitemap URLs for supported companies
SITEMAP_URLS = {
    "Great Learning": "https://www.mygreatlearning.com/sitemap.xml",
    "DataCamp": "https://www.datacamp.com/sitemap.xml",
    "Simplilearn": "https://www.simplilearn.com/sitemap.xml",
    "Coursera": "https://blog.coursera.org/sitemap.xml",
    "Udacity": "https://www.udacity.com/sitemap.xml",
    "Skillsoft": "https://www.skillsoft.com/sitemap.xml"
}

# Keywords to identify course/product pages
COURSE_KEYWORDS = [
    'course', 'courses', 'certification', 'certifications', 
    'program', 'training', 'learning-path', 'nanodegree', 
    'bootcamp', 'class'
]

# Date formats for parsing
DATE_FORMATS = [
    '%Y-%m-%dT%H:%M:%S%z',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%d',
    '%B %d, %Y',
    '%b %d, %Y'
]


# ============================================================================
# URL FILTERING
# ============================================================================

def is_course_url(url: str) -> bool:
    """Check if URL is likely a course/product page."""
    url_lower = url.lower()
    
    # Exclude blog/news URLs
    if any(x in url_lower for x in ['/blog', '/news', '/article']):
        return False
    
    # Include course-related URLs
    return any(keyword in url_lower for keyword in COURSE_KEYWORDS)


# ============================================================================
# XML/SITEMAP PROCESSING
# ============================================================================

def fetch_xml(url: str) -> Optional[ET.Element]:
    """Fetch and parse XML content from URL."""
    try:
        response = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
        response.raise_for_status()
        return ET.fromstring(response.content)
    except Exception as e:
        print(f"❌ Failed to fetch {url}: {e}")
        return None


def is_sitemap_index(root: Optional[ET.Element]) -> bool:
    """Check if XML is a sitemap index."""
    if root is None:
        return False
    
    if root.tag.endswith('sitemapindex'):
        return True
    
    for child in root:
        if child.tag.endswith('sitemap'):
            return True
    
    return False


def extract_sitemap_urls(root: ET.Element) -> List[str]:
    """Extract sitemap URLs from a sitemap index."""
    sitemap_urls = []
    
    # Try with namespace
    for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
        loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc is not None and loc.text:
            sitemap_urls.append(loc.text)
    
    # Try without namespace
    for sitemap in root.findall('.//sitemap'):
        loc = sitemap.find('loc')
        if loc is not None and loc.text:
            sitemap_urls.append(loc.text)
    
    return list(set(sitemap_urls))


def extract_urls_from_sitemap(root: Optional[ET.Element]) -> List[Dict[str, Optional[str]]]:
    """Extract URLs with lastmod dates from a regular sitemap."""
    if root is None:
        return []
    
    urls = []
    
    # Try with namespace
    for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc = url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        lastmod = url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
        
        if loc is not None and loc.text:
            urls.append({
                'url': loc.text,
                'lastmod': lastmod.text if lastmod is not None and lastmod.text else None
            })
    
    # Try without namespace if no results
    if not urls:
        for url in root.findall('.//url'):
            loc = url.find('loc')
            lastmod = url.find('lastmod')
            
            if loc is not None and loc.text:
                urls.append({
                    'url': loc.text,
                    'lastmod': lastmod.text if lastmod is not None and lastmod.text else None
                })
    
    return urls


def crawl_sitemaps_recursive(sitemap_url: str, depth: int = 0, max_depth: int = MAX_DEPTH) -> List[Dict[str, Optional[str]]]:
    """Recursively crawl sitemaps to find all URLs."""
    if depth > max_depth:
        print(f"   ⚠️  Max depth reached at {sitemap_url}")
        return []
    
    indent = "   " * depth
    print(f"{indent}🔍 Fetching: {sitemap_url}")
    
    root = fetch_xml(sitemap_url)
    if root is None:
        return []
    
    if is_sitemap_index(root):
        print(f"{indent}📑 Found nested sitemap index")
        child_sitemaps = extract_sitemap_urls(root)
        print(f"{indent}   Found {len(child_sitemaps)} child sitemaps")
        
        all_urls = []
        for i, child_url in enumerate(child_sitemaps, 1):
            print(f"{indent}   [{i}/{len(child_sitemaps)}] Processing child sitemap...")
            child_urls = crawl_sitemaps_recursive(child_url, depth + 1, max_depth)
            all_urls.extend(child_urls)
            time.sleep(0.3)
        
        return all_urls
    else:
        urls = extract_urls_from_sitemap(root)
        print(f"{indent}✅ Found {len(urls)} URLs")
        return urls


# ============================================================================
# DATE PARSING
# ============================================================================

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string to datetime object."""
    if not date_str:
        return None
    
    try:
        for fmt in DATE_FORMATS:
            try:
                clean_date = date_str.replace('Z', '+0000').split('T')[0] if 'T' in date_str else date_str
                return datetime.strptime(clean_date, fmt)
            except:
                continue
        return None
    except:
        return None


def is_2025_post(date_str: Optional[str]) -> bool:
    """Check if post is from 2025."""
    if not date_str or date_str == 'N/A':
        return False
    
    parsed_date = parse_date(date_str)
    if parsed_date and parsed_date.year == 2025:
        return True
    
    if '2025' in str(date_str):
        return True
    
    return False


# ============================================================================
# PAGE METADATA EXTRACTION
# ============================================================================

def get_page_info(url: str) -> Dict[str, Optional[str]]:
    """Fetch title, description, and date from a URL."""
    try:
        response = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title = _extract_title(soup)
        
        # Extract description
        description = _extract_description(soup)
        
        # Extract date
        date = _extract_date(soup)
        
        return {
            'title': title or 'No title found',
            'description': description or 'No description found',
            'date': date
        }
    
    except Exception as e:
        return {
            'title': f"Error: {str(e)}",
            'description': None,
            'date': None
        }


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    """Extract title from page."""
    # Try <title> tag
    title_tag = soup.find('title')
    if title_tag:
        return title_tag.get_text(strip=True)
    
    # Try og:title
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        return og_title['content']
    
    # Try <h1>
    h1_tag = soup.find('h1')
    if h1_tag:
        return h1_tag.get_text(strip=True)
    
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """Extract description from page."""
    # Try meta description
    desc_meta = soup.find('meta', attrs={'name': 'description'})
    if desc_meta and desc_meta.get('content'):
        return desc_meta['content']
    
    # Try og:description
    og_desc = soup.find('meta', property='og:description')
    if og_desc and og_desc.get('content'):
        return og_desc['content']
    
    return None


def _extract_date(soup: BeautifulSoup) -> Optional[str]:
    """Extract date from page."""
    # Try article:published_time
    date_meta = soup.find('meta', property='article:published_time')
    if date_meta and date_meta.get('content'):
        return date_meta['content']
    
    # Try publish-date
    date_meta = soup.find('meta', attrs={'name': 'publish-date'})
    if date_meta and date_meta.get('content'):
        return date_meta['content']
    
    # Try <time> tag
    time_tag = soup.find('time')
    if time_tag:
        return time_tag.get('datetime') or time_tag.get_text(strip=True)
    
    return None


# ============================================================================
# MAIN SCRAPING LOGIC
# ============================================================================

def scrape_company_sitemap(company_name: str, sitemap_url: str) -> List[Dict[str, Any]]:
    """Scrape courses from a company's sitemap."""
    print(f"\n{'='*80}")
    print(f"🏢 {company_name}")
    print(f"📥 Fetching sitemap: {sitemap_url}")
    print('='*80)
    
    root = fetch_xml(sitemap_url)
    if root is None:
        return []
    
    all_urls = []
    
    if is_sitemap_index(root):
        print("📑 Detected sitemap index\n")
        sitemap_urls = extract_sitemap_urls(root)
        print(f"🗂️  Found {len(sitemap_urls)} sitemaps\n")
        
        # Filter for course-related sitemaps
        keywords = ['course', 'program', 'certification', 'training', 'learning']
        course_sitemaps = [url for url in sitemap_urls if any(kw in url.lower() for kw in keywords)]
        
        if not course_sitemaps:
            course_sitemaps = sitemap_urls
        
        for i, sm_url in enumerate(course_sitemaps, 1):
            print(f"[Sitemap {i}/{len(course_sitemaps)}]")
            urls = crawl_sitemaps_recursive(sm_url, depth=0)
            all_urls.extend(urls)
            print()
    else:
        print("📄 Regular sitemap detected\n")
        all_urls = extract_urls_from_sitemap(root)
    
    # Filter and process URLs
    print(f"📊 Total URLs found: {len(all_urls)}")
    course_urls = [u for u in all_urls if is_course_url(u['url'] if isinstance(u, dict) else u)]
    print(f"🎓 Course-related URLs: {len(course_urls)}")
    print("-" * 80)
    
    # Remove duplicates
    course_urls = _remove_duplicate_urls(course_urls)
    
    # Sort by date
    if SORT_BY_DATE:
        course_urls = _sort_urls_by_date(course_urls)
    
    # Filter for 2025 posts
    urls_2025 = [u for u in course_urls if isinstance(u, dict) and is_2025_post(u.get('lastmod'))]
    
    if not urls_2025:
        print("⚠️  No 2025 courses found in sitemap dates, will check page content...")
        urls_to_check = course_urls[:MAX_COURSES_TO_SCRAPE]
    else:
        print(f"✅ Found {len(urls_2025)} courses from 2025")
        urls_to_check = urls_2025[:MAX_COURSES_TO_SCRAPE]
    
    # Fetch course information
    return _fetch_course_details(company_name, urls_to_check)


def _remove_duplicate_urls(urls: List[Dict]) -> List[Dict]:
    """Remove duplicate URLs."""
    seen_urls = set()
    unique_urls = []
    
    for item in urls:
        url = item['url'] if isinstance(item, dict) else item
        if url not in seen_urls:
            seen_urls.add(url)
            unique_urls.append(item)
    
    return unique_urls


def _sort_urls_by_date(urls: List[Dict]) -> List[Dict]:
    """Sort URLs by date."""
    if not urls or not isinstance(urls[0], dict):
        return urls
    
    urls_with_dates = [u for u in urls if u.get('lastmod')]
    urls_without_dates = [u for u in urls if not u.get('lastmod')]
    
    urls_with_dates.sort(
        key=lambda x: parse_date(x['lastmod']) or datetime.min, 
        reverse=True
    )
    
    return urls_with_dates + urls_without_dates


def _fetch_course_details(company_name: str, urls_to_check: List[Dict]) -> List[Dict[str, Any]]:
    """Fetch detailed information for each course URL."""
    print(f"\n🔄 Fetching course information...\n")
    results = []
    
    for i, course_item in enumerate(urls_to_check, 1):
        course_url = course_item['url'] if isinstance(course_item, dict) else course_item
        sitemap_date = course_item.get('lastmod', None) if isinstance(course_item, dict) else None
        
        page_data = get_page_info(course_url)
        final_date = page_data['date'] or sitemap_date
        
        if is_2025_post(final_date):
            course_data = {
                'company': company_name,
                'title': page_data['title'],
                'description': page_data['description'],
                'url': course_url,
                'date': final_date
            }
            
            results.append(course_data)
            print(f"✅ [{i}/{len(urls_to_check)}] {page_data['title'][:60]}... ({final_date})")
        else:
            print(f"⏭️  [{i}/{len(urls_to_check)}] Skipped (not 2025)")
        
        if i < len(urls_to_check):
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    print(f"\n📝 Total courses found: {len(results)}")
    return results


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    print("🚀 Starting Course Scraper (2025 Courses Only)\n")
    
    all_results = []
    
    for company_name, sitemap_url in SITEMAP_URLS.items():
        try:
            results = scrape_company_sitemap(company_name, sitemap_url)
            all_results.extend(results)
        except Exception as e:
            print(f"❌ Error scraping {company_name}: {e}")
        
        time.sleep(2)
    
    # Print summary
    _print_summary(all_results)
    
    # Save results
    if all_results:
        _save_results(all_results)


def _print_summary(results: List[Dict[str, Any]]):
    """Print summary of scraping results."""
    print(f"\n{'='*80}")
    print(f"✅ Scraping complete!")
    print(f"📊 Total courses collected: {len(results)}")
    print('='*80)
    
    if results:
        # Company counts
        print("\n📈 Summary by Company:")
        company_counts = {}
        for result in results:
            company = result['company']
            company_counts[company] = company_counts.get(company, 0) + 1
        
        for company, count in sorted(company_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   {company}: {count} courses")
        
        # Sample courses
        print("\n📋 Sample Courses Found:")
        for result in results[:5]:
            print(f"\n   🎓 {result['title']}")
            print(f"      Provider: {result['company']}")
            print(f"      Date: {result['date']}")
            print(f"      URL: {result['url']}")
    else:
        print("\n⚠️  No courses found")


def _save_results(results: List[Dict[str, Any]]):
    """Save results to JSON file."""
    filename = 'courses_2025.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Saved to {filename}")


if __name__ == "__main__":
    main()