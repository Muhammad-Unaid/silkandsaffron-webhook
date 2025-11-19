# bot/web_scrap.py - SHOPIFY API VERSION (No Selenium needed!)

import requests
from .models import PageContent
import time


def scrape_shopify_products(domain):
    """
    Scrape products using Shopify's products.json API
    This works for most Shopify stores without JavaScript rendering
    """
    base_url = domain.rstrip('/')
    products_url = f"{base_url}/products.json"
    
    all_products = []
    page = 1
    
    print(f"🔍 Fetching products from Shopify API...")
    
    while True:
        try:
            url = f"{products_url}?page={page}&limit=250"
            print(f"   Page {page}: {url}")
            
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"   ❌ Status {response.status_code}")
                break
            
            data = response.json()
            products = data.get('products', [])
            
            if not products:
                break
            
            all_products.extend(products)
            print(f"   ✅ Found {len(products)} products")
            
            page += 1
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            break
    
    return all_products


def scrape_shopify_collections(domain):
    """
    Scrape collections using Shopify API
    """
    base_url = domain.rstrip('/')
    collections_url = f"{base_url}/collections.json"
    
    try:
        print(f"🔍 Fetching collections from Shopify API...")
        response = requests.get(collections_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            collections = data.get('collections', [])
            print(f"   ✅ Found {len(collections)} collections")
            return collections
        else:
            print(f"   ⚠️ Collections API not available")
            return []
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return []


def save_product_to_db(product, domain):
    """
    Save Shopify product to database
    """
    try:
        # Extract product info
        product_id = product.get('id')
        title = product.get('title', '')
        handle = product.get('handle', '')
        url = f"{domain.rstrip('/')}/products/{handle}"
        
        # Description
        body_html = product.get('body_html', '')
        # Remove HTML tags for clean text
        import re
        description = re.sub(r'<[^>]+>', '', body_html).strip()
        
        # Variants (sizes, colors, etc.)
        variants = product.get('variants', [])
        variant_info = []
        prices = []
        
        for variant in variants:
            title_var = variant.get('title', '')
            if title_var and title_var != 'Default Title':
                variant_info.append(title_var)
            
            price = variant.get('price', '')
            if price:
                prices.append(f"Rs.{price}")
        
        # Product type and vendor
        product_type = product.get('product_type', '')
        vendor = product.get('vendor', '')
        
        # Tags
        tags = product.get('tags', [])
        if isinstance(tags, list):
            tags_str = ', '.join(tags)
        else:
            tags_str = str(tags)
        
        # Availability
        available = product.get('available', True)
        availability = 'Available' if available else 'Sold out'
        
        # Build content
        content_parts = [
            f"Product: {title}",
        ]
        
        if prices:
            unique_prices = list(set(prices))
            content_parts.append(f"Price: {' | '.join(unique_prices[:2])}")
        
        content_parts.append(f"Status: {availability}")
        
        if variant_info:
            unique_variants = list(set(variant_info))
            content_parts.append(f"Options: {', '.join(unique_variants[:10])}")
        
        if product_type:
            content_parts.append(f"Category: {product_type}")
        
        if vendor:
            content_parts.append(f"Brand: {vendor}")
        
        if tags_str:
            content_parts.append(f"Tags: {tags_str}")
        
        if description:
            content_parts.append(f"Description: {description[:500]}")
        
        content = '\n\n'.join(content_parts)
        
        # Save to database
        obj, created = PageContent.objects.update_or_create(
            url=url,
            defaults={
                'title': title,
                'content': content,
                'page_type': 'product',
                'is_active': True
            }
        )
        
        return created
        
    except Exception as e:
        print(f"   ❌ Error saving product: {str(e)}")
        return False


def save_collection_to_db(collection, domain):
    """
    Save Shopify collection to database
    """
    try:
        title = collection.get('title', '')
        handle = collection.get('handle', '')
        url = f"{domain.rstrip('/')}/collections/{handle}"
        
        # Description
        body_html = collection.get('body_html', '')
        import re
        description = re.sub(r'<[^>]+>', '', body_html).strip()
        
        # Build content
        content_parts = [
            f"Collection: {title}",
        ]
        
        if description:
            content_parts.append(f"Description: {description}")
        
        content = '\n\n'.join(content_parts)
        
        # Save to database
        obj, created = PageContent.objects.update_or_create(
            url=url,
            defaults={
                'title': title,
                'content': content,
                'page_type': 'collection',
                'is_active': True
            }
        )
        
        return created
        
    except Exception as e:
        print(f"   ❌ Error saving collection: {str(e)}")
        return False


def scrape_all_pages(domain, limit=100):
    """
    Main scraping function using Shopify API
    """
    print(f"🚀 Starting Shopify API scrape of {domain}\n")
    
    scraped_count = 0
    new_count = 0
    
    # Scrape products
    print("="*60)
    print("📦 SCRAPING PRODUCTS")
    print("="*60)
    
    products = scrape_shopify_products(domain)
    
    if products:
        print(f"\n💾 Saving {len(products)} products to database...")
        for i, product in enumerate(products[:limit], 1):
            title = product.get('title', 'Unknown')
            print(f"   [{i}/{len(products[:limit])}] {title}")
            
            created = save_product_to_db(product, domain)
            scraped_count += 1
            if created:
                new_count += 1
            
            # Rate limiting
            if i % 10 == 0:
                time.sleep(0.5)
    else:
        print("⚠️ No products found via API")
    
    # Scrape collections
    print("\n" + "="*60)
    print("📁 SCRAPING COLLECTIONS")
    print("="*60)
    
    collections = scrape_shopify_collections(domain)
    
    if collections:
        print(f"\n💾 Saving {len(collections)} collections to database...")
        for i, collection in enumerate(collections, 1):
            title = collection.get('title', 'Unknown')
            print(f"   [{i}/{len(collections)}] {title}")
            
            created = save_collection_to_db(collection, domain)
            scraped_count += 1
            if created:
                new_count += 1
    
    # Add homepage
    print("\n" + "="*60)
    print("🏠 ADDING HOMEPAGE")
    print("="*60)
    
    try:
        PageContent.objects.update_or_create(
            url=domain,
            defaults={
                'title': 'Silk and Saffron - Home',
                'content': 'Welcome to Silk and Saffron. Browse our collections of premium Pakistani clothing including co-ord sets, dresses, and more.',
                'page_type': 'page',
                'is_active': True
            }
        )
        print("   ✅ Homepage added")
        scraped_count += 1
    except Exception as e:
        print(f"   ❌ Error adding homepage: {e}")
    
    print("\n" + "="*60)
    print(f"✅ SCRAPING COMPLETE")
    print("="*60)
    print(f"📊 Total items processed: {scraped_count}")
    print(f"📊 New items added: {new_count}")
    print(f"📊 Updated items: {scraped_count - new_count}")
    
    return {domain}  # Return as set for compatibility