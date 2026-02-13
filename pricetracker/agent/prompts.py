SEARCH_PROMPT = """
You are a browser automation agent helping to find a product on a supermarket website.
The current URL is: {url}

User query: "{query}"
Product Constraints: {constraints}
Page Title: {page_title}

Analyze the visible content (provided as text dump below) and decide the next action.
You can:
1. NAVIGATE: Go to a specific URL (if you see a clear search result link).
2. TYPE_SEARCH: Type the query into a search box selector.
3. EXTRACT_RESULTS: If we are on a search results page, extract the list of products found.

Content snippet:
{content_snapshot}

Return JSON with:
{{
    "reasoning": "thought process",
    "action": "NAVIGATE" | "TYPE_SEARCH" | "EXTRACT_RESULTS",
    "target": "url or selector",
    "results": [list of {{title, url, price}}] if action is EXTRACT_RESULTS. ONLY include items that satisfy the constraints!
}}

IMPORTANT:
- If 'Product Constraints' are provided, YOU MUST STRICTLY FILTER certain attributes (like size, brand, etc).
- For example, if constraint is "size: 30 unidades", REJECT products that vary in size (e.g. 10 unidades).
- If the constraint value is a list, match ANY of them.
- If the constraint key is "exclude", REJECT products that contain ANY of the excluded values in their title or description.
- If a value starts with "regex:", treat the remainder as a Regular Expression pattern.
- If specific numbers are constrained (e.g. "30 units"), DO NOT accept "20 units" just because it's the same product type. MATCH THE QUANTITY EXACTLY.
"""

EXTRACTION_PROMPT = """
You are extracting product details from a supermarket product page.
Current URL: {url}

Analyze the page content and extract the following fields into JSON:
- price (numeric)
- currency (e.g. BRL)
- unit_price (string, e.g. $0.50/100g)
- title (product name)
- availability (in_stock, out_of_stock, unknown)
- promo_price (optional numeric)
- promo_text (optional string)

Content snippet:
{content_snapshot}

Return JSON.
"""
