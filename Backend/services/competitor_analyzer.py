import json
import requests
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from firecrawl import FirecrawlApp
from openai import OpenAI
from dotenv import load_dotenv
import os
load_dotenv()
# ---- CONFIG ----
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY") #"fc-007a697ab3494d0d980e7a53de598a7d"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") #"openai_api_sk_XXXXXXXXXXXXXXXX
client = OpenAI(api_key=OPENAI_API_KEY)


# -----------------------------
# 🔹 Firecrawl Extraction Schema
# -----------------------------
class ProductSchema(BaseModel):
    name: Optional[str]
    price: Optional[str]
    description: Optional[str]

class CompetitorDataSchema(BaseModel):
    company_name: Optional[str]
    products: Optional[List[ProductSchema]] = []
    key_features: Optional[List[str]] = []
    tech_stack: Optional[List[str]] = []
    marketing_focus: Optional[str]
    customer_feedback: Optional[str]
    date: Optional[str]


# -----------------------------
# 🔹 OpenAI Analysis Schema
# -----------------------------
class CompetitorAnalysisSchema(BaseModel):
    product_evolution_signals: List[str]
    pricing_strategy_changes: List[str]
    target_audience_focus: List[str]
    geographic_or_demographic_expansion: List[str]
    messaging_and_branding_shifts: List[str]
    technology_and_platform_innovation: List[str]
    partnerships_funding_and_hiring_trends: List[str]
    customer_feedback_patterns: List[str]
    predicted_strategic_direction: str


# -----------------------------
# 🔹 Firecrawl Extraction
# -----------------------------
def crawl_website(url: str) -> dict:
    app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    url_pattern = f"{url}/*"

    extraction_prompt = """
    Extract detailed information from this company's website and return:
    - The company name
    - A list of all individual products or certifications offered (name, price, short description)
    - Key features or capabilities
    - Technology stack
    - Marketing focus or target audience
    - Customer feedback and testimonials
    - Date of last content update, if available
    """

    response = app.extract(
        [url_pattern],
        prompt=extraction_prompt,
        schema=CompetitorDataSchema.model_json_schema()
    )

    if hasattr(response, "success") and response.success and hasattr(response, "data"):
        extracted_info = response.data
        if not isinstance(extracted_info, dict):
            extracted_info = extracted_info.dict() if hasattr(extracted_info, "dict") else {}

        today_str = datetime.now().strftime("%Y-%m-%d")
        return {
            "competitor_url": url,
            "company_name": extracted_info.get("company_name", "N/A"),
            "products": extracted_info.get("products", []),
            "key_features": extracted_info.get("key_features", []),
            "tech_stack": extracted_info.get("tech_stack", []),
            "marketing_focus": extracted_info.get("marketing_focus", "N/A"),
            "customer_feedback": extracted_info.get("customer_feedback", "N/A"),
            "date": extracted_info.get("date", today_str)
        }

    return None


# -----------------------------
# 🔹 OpenAI Analysis
# -----------------------------
def analyze_with_openai(competitor_data: dict) -> dict:
    formatted_data = json.dumps(competitor_data, indent=2)
    prompt = f"""
    You are a professional market analyst specializing in AI certification and education markets.

    Analyze the following competitor data (in JSON or text form):
    {formatted_data}

    Provide structured insights in JSON format with these keys:
    - product_evolution_signals
    - pricing_strategy_changes
    - target_audience_focus
    - geographic_or_demographic_expansion
    - messaging_and_branding_shifts
    - technology_and_platform_innovation
    - partnerships_funding_and_hiring_trends
    - customer_feedback_patterns
    - predicted_strategic_direction
    """

    response = client.responses.parse(
        model="gpt-4o-2024-08-06",
        input=[{"role": "user", "content": prompt}],
        text_format=CompetitorAnalysisSchema,
        temperature=0.4,
    )

    return response.output_parsed.model_dump()
