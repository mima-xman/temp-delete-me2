from playwright.sync_api import sync_playwright
from PlaywrightHelper import PlaywrightHelper


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        helper = PlaywrightHelper(
            page=page,
            default_retries=3,
            default_timeout=10000,
            humanize=True
        )

        # Navigate to page
        helper.goto("https://example.com")
        helper.wait_natural_delay(1, 2)

        # =====================================================================
        # Example 1: Get text content
        # =====================================================================
        title = helper.get_element_content("h1", content_type="text")
        print(f"Title: {title}")

        # =====================================================================
        # Example 2: Get input value
        # =====================================================================
        email = helper.get_element_content("#email-input", content_type="value")
        print(f"Email value: {email}")

        # =====================================================================
        # Example 3: Get attribute
        # =====================================================================
        href = helper.get_element_content(
            "a.main-link",
            content_type="attribute",
            attribute="href"
        )
        print(f"Link href: {href}")

        # =====================================================================
        # Example 4: Get inner HTML
        # =====================================================================
        html = helper.get_element_content("#content-div", content_type="inner_html")
        print(f"Inner HTML: {html}")

        # =====================================================================
        # Example 5: Get content from iframe element
        # =====================================================================
        iframe_content = helper.get_element_content(
            selector="#payment-status",
            content_type="text",
            iframe_selector="iframe#payment-frame"
        )
        print(f"Iframe content: {iframe_content}")

        # =====================================================================
        # Example 6: Get multiple elements content
        # =====================================================================
        list_items = helper.get_multiple_elements_content(
            "ul.menu li",
            content_type="text"
        )
        print(f"Menu items: {list_items}")

        # Get all product links
        product_links = helper.get_multiple_elements_content(
            "a.product-link",
            content_type="attribute",
            attribute="href"
        )
        print(f"Product links: {product_links}")

        # =====================================================================
        # Example 7: Get multiple attributes at once
        # =====================================================================
        img_attrs = helper.get_element_attributes(
            "img.product-image",
            attributes=["src", "alt", "data-id", "width", "height"]
        )
        print(f"Image attributes: {img_attrs}")

        # =====================================================================
        # Example 8: Get comprehensive element info
        # =====================================================================
        button_info = helper.get_element_info("#submit-button")
        print(f"Button info: {button_info}")

        # =====================================================================
        # Example 9: Using execute_actions with get_content
        # =====================================================================
        actions = [
            {
                "type": "Goto link",
                "url": "https://example.com/products"
            },
            {
                "type": "Wait",
                "min_delay": 1.0,
                "max_delay": 2.0
            },
            {
                "type": "Get element content",
                "selector": "h1.page-title",
                "content_type": "text",
                "save_as": "page_title"
            },
            {
                "type": "Get element content",
                "selector": ".product-price",
                "content_type": "text",
                "save_as": "price"
            },
            {
                "type": "Get element content",
                "selector": "img.product-image",
                "content_type": "attribute",
                "attribute": "src",
                "save_as": "image_url"
            },
            {
                "type": "Get element content",
                "selector": "#product-description",
                "content_type": "inner_html",
                "save_as": "description_html"
            },
            {
                "type": "Click",
                "selector": "#add-to-cart"
            }
        ]

        result = helper.execute_actions(actions)
        
        if isinstance(result, dict):
            if result['success']:
                print("✓ All actions completed successfully")
                print(f"  Page title: {result['data'].get('page_title')}")
                print(f"  Price: {result['data'].get('price')}")
                print(f"  Image URL: {result['data'].get('image_url')}")
            else:
                print("✗ Some actions failed")
                print(f"  Collected data: {result['data']}")

        browser.close()


if __name__ == "__main__":
    main()