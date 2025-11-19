import os
import json
import re
import requests
import difflib
import concurrent.futures
import random
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bot.models import PageContent
from django.conf import settings

# --- Caching Setup ---
PAGES_CACHE = None
SCRAPED_CONTENT_CACHE = None
LAST_SUGGESTED_PRODUCTS = []


def clean_scraped_text(text):
    """
    ✅ CLEAN scraped content - remove navigation, HTML artifacts
    """
    if not text:
        return ""
    
    # Remove common navigation/footer text
    noise_patterns = [
        r'skip to content',
        r'your cart is empty',
        r'continue shopping',
        r'have an account\?',
        r'log in to check out',
        r'estimated total',
        r'taxes.*calculated at checkout',
        r'check out',
        r'loading\.\.\.',
        r'add to cart',
        r'view cart',
        r'home.*clearance sale',  # Navigation menu
        r'co-ord sets.*elegant floral',  # Menu items
        r'cart.*loading',
        r'Rs \d+\.\d+',  # Prices without context
    ]
    
    cleaned = text
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\n+', '\n', cleaned)
    
    # Remove lines with only special characters
    lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
    meaningful_lines = [
        line for line in lines 
        if len(line) > 10 and not re.match(r'^[^\w\s]+$', line)
    ]
    
    return ' '.join(meaningful_lines).strip()


def extract_product_info(text, title=""):
    """
    ✅ Extract meaningful product information only
    """
    cleaned = clean_scraped_text(text)
    
    # Look for product descriptions (usually longer sentences)
    sentences = cleaned.split('.')
    product_sentences = []
    
    for sent in sentences:
        sent = sent.strip()
        # Keep sentences that are descriptive (5-100 words)
        word_count = len(sent.split())
        if 5 <= word_count <= 100:
            # Skip if it's just navigation/menu items
            if not any(nav in sent.lower() for nav in ['home', 'cart', 'checkout', 'log in', 'sign up']):
                product_sentences.append(sent)
    
    # Take first 2-3 meaningful sentences
    if product_sentences:
        result = '. '.join(product_sentences[:3])
        return result + '.' if result else cleaned[:300]
    
    # Fallback to first 300 chars of cleaned text
    return cleaned[:300]


def get_scraped_content():
    """Load all scraped content from database"""
    global SCRAPED_CONTENT_CACHE
    if SCRAPED_CONTENT_CACHE:
        return SCRAPED_CONTENT_CACHE
    
    all_pages = PageContent.objects.all()
    combined_content = "\n\n".join([
        f"Page: {p.title or p.url}\nContent: {extract_product_info(p.content, p.title)}"
        for p in all_pages[:20]
    ])
    
    SCRAPED_CONTENT_CACHE = combined_content[:3000]
    return SCRAPED_CONTENT_CACHE or "Website content not available"


def detect_language(text):
    """Detect if text is Urdu or English"""
    if re.search(r"[\u0600-\u06FF]", text):
        return "urdu"
    
    urdu_words = ["mujhe", "kaun", "kon", "kaha", "dikhao", "dikho",
                  "kya", "kaise", "batao", "chahiye", "hai", "ki", "ap"]
    if any(word in text.lower() for word in urdu_words):
        return "urdu"
    
    return "english"


def search_in_scraped_content(user_query, threshold=0.3):
    """
    ✅ IMPROVED: Better search with cleaned content + price queries
    """
    global LAST_SUGGESTED_PRODUCTS
    
    user_query_lower = user_query.lower()
    all_matches = []
    
     # ✅ NEW: Handle price queries first
    price_keywords = ['sasta', 'cheap', 'mehnga', 'expensive', 'price', 'budget']
    if any(word in user_query_lower for word in price_keywords):
        return handle_price_query(user_query_lower)
    
    # Extract key terms
    query_words = [w for w in user_query_lower.split() if len(w) > 2]
    
    # ✅ Add color/category detection
    colors = ['red', 'blue', 'green', 'black', 'white', 'pink', 'yellow', 'purple']
    categories = ['dress', 'saree', 'suit', 'kurta', 'shirt', 'pant', 'dupatta']
    
    query_colors = [c for c in colors if c in user_query_lower]
    query_categories = [c for c in categories if c in user_query_lower]
    
    all_pages = PageContent.objects.all()
    
    for page in all_pages:
        content_lower = page.content.lower()
        title_lower = (page.title or "").lower()
        score = 0
        excerpt = ""
        
        # Clean content first
        clean_content = extract_product_info(page.content, page.title)
        clean_content_lower = clean_content.lower()
        
        # 1. ✅ EXACT PHRASE in cleaned content
        if user_query_lower in clean_content_lower:
            score = 0.9
            excerpt = clean_content
            
        # 2. ✅ EXACT PHRASE in Title
        elif user_query_lower in title_lower:
            score = 0.85
            excerpt = clean_content
        
        # 3. ✅ COLOR + CATEGORY match (e.g., "red dress")
        elif query_colors and query_categories:
            color_match = any(c in clean_content_lower for c in query_colors)
            category_match = any(c in clean_content_lower for c in query_categories)
            
            if color_match and category_match:
                score = 0.8
                excerpt = clean_content
            elif color_match or category_match:
                score = 0.6
                excerpt = clean_content
        
        # 4. ✅ KEYWORD MATCHING
        elif query_words:
            matches = sum(1 for word in query_words if word in clean_content_lower)
            score = matches / len(query_words)
            
            if score > 0.4:
                excerpt = clean_content
        
        # Store matches
        if score >= threshold and excerpt:
            page_id = page.url
            if page_id not in LAST_SUGGESTED_PRODUCTS:
                all_matches.append({
                    'page': page,
                    'score': score,
                    'excerpt': excerpt,
                    'title': page.title or "Product"
                })
    
    # Return best match
    if all_matches:
        all_matches.sort(key=lambda x: x['score'], reverse=True)
        
        if all_matches[0]['score'] > 0.7:
            selected = all_matches[0]
        else:
            top_matches = all_matches[:3]
            selected = random.choice(top_matches)
        
        # Update tracking
        LAST_SUGGESTED_PRODUCTS.append(selected['page'].url)
        if len(LAST_SUGGESTED_PRODUCTS) > 10:
            LAST_SUGGESTED_PRODUCTS.pop(0)
        
        return selected['excerpt'], selected['score'], selected['title']
    
    return None, 0, None


def format_scraped_response(excerpt, query, language, title=""):
    # """
    # ✅ Format scraped content into SHORT natural response
    # """
    excerpt_clean = excerpt.strip()
    
    # Limit to 200 chars for concise response
    if len(excerpt_clean) > 300:
        # Take first 200 chars and find last complete sentence
        excerpt_clean = excerpt_clean[:300]
        last_period = excerpt_clean.rfind('.')
        if last_period > 100:
            excerpt_clean = excerpt_clean[:last_period + 1]
        else:
            excerpt_clean = excerpt_clean[:300] + "..."
    
    # Format based on language
    if language == "urdu":
        if title and title.lower() != "product":
            response = f"✨ **{title}**\n\n{excerpt_clean}\n\n💬 Aur details chahiye?"
        else:
            response = f"{excerpt_clean}\n\n💬 Kya aur janana chahein?"
    else:
        if title and title.lower() != "product":
            response = f"✨ **{title}**\n\n{excerpt_clean}\n\nWant more details?"
        else:
            response = f"{excerpt_clean}\n\nNeed more info?"
    
    return response


def query_gemini_for_alternative(user_query, no_exact_match=False):
    """
    ✅ Gemini for ALTERNATIVE suggestions when exact match not found
    """
    try:
        language = detect_language(user_query)
        
        # Get diverse products
        diverse_pages = get_diverse_product_samples(limit=5)
        
        if not diverse_pages:
            return "Sorry, no products available right now."
        
        # Build clean product list
        product_list = []
        for p in diverse_pages:
            clean_info = extract_product_info(p.content, p.title)
            product_list.append(f"- {p.title}: {clean_info[:100]}")
        
        products_text = "\n".join(product_list)
        
        if no_exact_match:
            context = f"User searched for: {user_query}\nBut exact match not found."
        else:
            context = f"User asked: {user_query}"
        
        prompt = f"""
You are a helpful sales assistant for silkandsaffron.store.

{context}

Available Products:
{products_text}

📝 RULES:
- Reply in {"Roman Urdu" if language == "urdu" else "English"}
- Keep it VERY SHORT (2-3 lines only)
- Suggest 2-3 RELEVANT alternatives from above list
- Be friendly and helpful
- End with a question

Reply:
"""

        GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)
        if not GEMINI_API_KEY:
            return "⚠️ Configuration issue."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.8,
                "maxOutputTokens": 200,
            }
        }

        response = requests.post(url, headers={"Content-Type": "application/json"}, 
                                json=payload, timeout=8)
        
        if response.status_code == 200:
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text.replace("**", "").replace("*", "")
        else:
            return f"⚠️ Error: {response.status_code}"
        
    except Exception as e:
        print(f"❌ Gemini Error: {str(e)}")
        return "⚠️ Server busy. Please try again."


def query_gemini_for_fallback(user_query, website_content):
    """
    ✅ Gemini for general chat/greetings
    """
    try:
        language = detect_language(user_query)
        
        prompt = f"""
            You are a friendly sales assistant for silkandsaffron.store (Pakistani clothing store).

            User said: "{user_query}"

            📝 RULES:
            - Reply in {"Roman Urdu" if language == "urdu" else "English"}
            - Keep it SHORT (1-2 lines only)
            - Be warm and conversational
            - If greeting: respond warmly
            - If thanks: acknowledge politely
            - Guide them to explore products

            Reply:
            """

        GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)
        if not GEMINI_API_KEY:
            return "⚠️ Configuration issue."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.9,
                "maxOutputTokens": 150,
            }
        }

        response = requests.post(url, headers={"Content-Type": "application/json"}, 
                                json=payload, timeout=8)
        
        if response.status_code == 200:
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text.replace("**", "").replace("*", "")
        else:
            return f"⚠️ Error: {response.status_code}"
        
    except Exception as e:
        print(f"❌ Gemini Error: {str(e)}")
        return "⚠️ Server busy. Please try again."


def get_diverse_product_samples(limit=10):
    """Get diverse random products"""
    global LAST_SUGGESTED_PRODUCTS
    
    all_pages = PageContent.objects.all()
    available_pages = [p for p in all_pages if p.url not in LAST_SUGGESTED_PRODUCTS]
    
    if not available_pages:
        available_pages = list(all_pages)
        LAST_SUGGESTED_PRODUCTS.clear()
    
    if len(available_pages) > limit:
        return random.sample(list(available_pages), limit)
    return available_pages


def handle_llm_query_intent(user_query):
    """
    ✅ LLMQueryIntent Handler with alternative suggestions
    """
    print(f"🎯 LLMQueryIntent triggered for: {user_query}")
    
    # Search in scraped content
    scraped_excerpt, confidence, title = search_in_scraped_content(user_query, threshold=0.3)
    
    language = detect_language(user_query)
    
    # ✅ HIGH CONFIDENCE: Return scraped DIRECTLY
    if scraped_excerpt and confidence > 0.7:
        print(f"✅ HIGH confidence ({confidence:.2f}) - Direct scraped response")
        return format_scraped_response(scraped_excerpt, user_query, language, title)
    
    # ⚠️ MEDIUM CONFIDENCE: Return scraped with note
    elif scraped_excerpt and confidence > 0.4:
        print(f"⚠️ MEDIUM confidence ({confidence:.2f}) - Scraped response")
        return format_scraped_response(scraped_excerpt, user_query, language, title)
    
    # ❌ LOW/NO MATCH: Give alternatives
    else:
        print(f"❌ LOW confidence - Using direct alternatives")
        #return query_gemini_for_alternative(user_query, no_exact_match=True)
        return get_direct_alternatives(user_query, language)

def get_direct_alternatives(user_query, language):
    """
    Provide alternatives WITHOUT calling Gemini API
    """
    products = get_diverse_product_samples(limit=5)
    
    if not products:
        if language == "urdu":
            return "Maaf kijiye! Abhi products load nahi ho rahe. Thodi der baad try karein."
        else:
            return "Sorry! Products not available right now. Please try again later."
    
    # Build response
    suggestions = []
    for p in products[:3]:
        title = p.title or "Product"
        price_match = re.search(r'Price:\s*([^\n]+)', p.content)
        price = price_match.group(1) if price_match else ""
        
        if price:
            suggestions.append(f"• {title} - {price}")
        else:
            suggestions.append(f"• {title}")
    
    suggestions_text = "\n".join(suggestions)
    
    if language == "urdu":
        response = f"""Yeh options dekh sakte hain:

{suggestions_text}

Kaunsa pasand aaya? 😊"""
    else:
        response = f"""Here are some options:

{suggestions_text}

Which one would you like to know more about? 😊"""
    
    return response

def handle_price_query(query_lower):
    """
    Handle price-based queries (cheapest/expensive)
    """
    language = detect_language(query_lower)
    
    # Get all products with prices
    all_products = PageContent.objects.filter(page_type='product')
    
    products_with_price = []
    
    for product in all_products:
        # Extract price from content
        price_match = re.search(r'Rs\.?(\d+(?:,\d{3})*(?:\.\d{2})?)', product.content)
        if price_match:
            try:
                price_str = price_match.group(1).replace(',', '')
                price = float(price_str)
                products_with_price.append({
                    'title': product.title,
                    'price': price,
                    'content': product.content[:300]
                })
            except:
                continue
    
    if not products_with_price:
        return None, 0, None
    
    # Check if looking for cheap or expensive
    if any(word in query_lower for word in ['sasta', 'cheap', 'budget', 'affordable']):
        # Sort by price (ascending)
        products_with_price.sort(key=lambda x: x['price'])
        selected_products = products_with_price[:3]
        
        if language == "urdu":
            response = "🌟 Sabse saste options:\n\n"
        else:
            response = "🌟 Most affordable options:\n\n"
    else:
        # Sort by price (descending)  
        products_with_price.sort(key=lambda x: x['price'], reverse=True)
        selected_products = products_with_price[:3]
        
        if language == "urdu":
            response = "🌟 Premium options:\n\n"
        else:
            response = "🌟 Premium options:\n\n"
    
    # Build response
    for i, p in enumerate(selected_products, 1):
        response += f"{i}. {p['title']} - Rs.{int(p['price'])}\n"
    
    if language == "urdu":
        response += "\nKaunsa dekhna chahein? 😊"
    else:
        response += "\nWhich one would you like to see? 😊"
    
    return response, 0.95, "Price Comparison"

# def handle_fallback_intent(user_query):
#     """
#     ✅ Fallback Intent - General chat 
#     """
#     print(f"🔄 Fallback intent triggered for: {user_query}")
    
#     website_content = get_scraped_content()
#     response = query_gemini_for_fallback(user_query, website_content)
    
#     return response

def handle_fallback_intent(user_query):
    """
    ✅ Fallback Intent - General chat WITHOUT Gemini
    """
    print(f"🔄 Fallback intent triggered for: {user_query}")
    
    language = detect_language(user_query)
    query_lower = user_query.lower()
    
    # Simple pattern-based responses
    
    # Greetings
    if any(word in query_lower for word in ['hello', 'hi', 'salam', 'hey']):
        if language == "urdu":
            return "Salam! Main aapki kaise madad kar sakti hoon? Aap apne pasand ka product puch sakte hain. 😊"
        else:
            return "Hello! How can I help you today? Feel free to ask about our products. 😊"
    
    # Thanks
    if any(word in query_lower for word in ['thanks', 'thank you', 'shukriya', 'thankyou']):
        if language == "urdu":
            return "Khushi hui madad karke! Kuch aur chahiye? 😊"
        else:
            return "You're welcome! Anything else I can help with? 😊"
    
    # Name
    if any(word in query_lower for word in ['naam', 'name', 'kaun', 'who']):
        if language == "urdu":
            return "Main Silk and Saffron ki assistant hoon. Aap mujhse products ke baare mein puch sakte hain! 💫"
        else:
            return "I'm Silk and Saffron's assistant. Ask me about our products! 💫"
    
    # Bye
    if any(word in query_lower for word in ['bye', 'khuda hafiz', 'goodbye']):
        if language == "urdu":
            return "Khuda hafiz! Dobara zaroor aaiyega. 👋"
        else:
            return "Goodbye! Visit us again soon. 👋"
    
    # Default: Show random products
    return get_direct_alternatives(user_query, language)


@csrf_exempt
def dialogflow_webhook(request):
    """
    ✅ Main Dialogflow webhook
    """
    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception as e:
            print(f"❌ Invalid JSON: {e}")
            return JsonResponse({"fulfillmentText": "⚠️ Invalid request."}, status=400)

        user_query = body.get("queryResult", {}).get("queryText", "")
        intent = body.get("queryResult", {}).get("intent", {}).get("displayName", "")
        
        print(f"\n{'='*50}")
        print(f"📝 User Query: {user_query}")
        print(f"🎯 Intent Detected: {intent}")
        print(f"{'='*50}\n")
        
        answer = None
        
        # Route based on intent
        if intent == "LLMQueryIntent":
            answer = handle_llm_query_intent(user_query)
        elif intent == "Default Fallback Intent" or not intent:
            answer = handle_fallback_intent(user_query)
        else:
            answer = handle_fallback_intent(user_query)
        
        # Safety check
        if not answer or len(answer.strip()) < 5:
            language = detect_language(user_query)
            if language == "urdu":
                answer = "Maaf kijiye! Kya aap apna sawal thoda detail mein puch sakte hain?"
            else:
                answer = "Sorry! Could you please provide more details?"
        
        print(f"📤 Final Response: {answer}\n")
        
        return JsonResponse({
            "fulfillmentText": answer,
            "fulfillmentMessages": [{"text": {"text": [answer]}}],
            "source": "webhook"
        })

    return JsonResponse({"error": "Only POST allowed"}, status=405)


def webhook_health(request):
    """Health check endpoint"""
    scraped_count = PageContent.objects.count()
    
    # Test content cleaning
    if scraped_count > 0:
        sample = PageContent.objects.first()
        cleaned_sample = extract_product_info(sample.content, sample.title)
    else:
        cleaned_sample = "No data"
    
    return JsonResponse({
        "status": "healthy",
        "scraped_pages": scraped_count,
        "cache_status": "loaded" if SCRAPED_CONTENT_CACHE else "empty",
        "last_suggested_count": len(LAST_SUGGESTED_PRODUCTS),
        "sample_cleaned_content": cleaned_sample[:200],
        "cleaning_enabled": True
    })