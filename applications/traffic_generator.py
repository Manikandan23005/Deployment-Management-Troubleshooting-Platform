import time
import random
import httpx

GATEWAY_URL = "http://gateway-service:8080"

print("🚀 Starting Enterprise E-Commerce Traffic Generator...")

SEARCH_TERMS = ["iphone", "sony", "macbook", "oled", "jordan", "audio", "camera", "vacuum", "galaxy", "watch"]
CATEGORIES = ["Mobiles", "Audio", "Laptops", "Wearables", "Cameras", "Smart Home", "Fashion", "Accessories"]
USERNAMES = ["customer", "admin", "guest", "shopper_vip", "unknown_user"]

while True:
    try:
        # 1. Browse All Products or Filtered Products (GET)
        cat = random.choice(CATEGORIES + [None, None])
        search = random.choice(SEARCH_TERMS + [None, None, None])
        params = {}
        if cat:
            params["category"] = cat
        if search:
            params["search"] = search
            
        httpx.get(f"{GATEWAY_URL}/api/v1/products/products", params=params, timeout=3.0)
        
        # 2. View Deals & Categories
        if random.random() < 0.4:
            httpx.get(f"{GATEWAY_URL}/api/v1/products/deals", timeout=3.0)
            httpx.get(f"{GATEWAY_URL}/api/v1/products/categories", timeout=3.0)
        
        # 3. View Specific Product Detail (IDs 1-12, plus occasional 999 for 404 metrics)
        prod_id = random.choice(list(range(1, 13)) + [999])
        httpx.get(f"{GATEWAY_URL}/api/v1/products/products/{prod_id}", timeout=3.0)
        
        # 4. User Authentication & Profile
        target_user = random.choice(USERNAMES)
        password = "password" if target_user == "admin" else ("customer123" if target_user == "customer" else "guest")
        login_res = httpx.post(f"{GATEWAY_URL}/api/v1/auth/login", json={"username": target_user, "password": password}, timeout=3.0)
        
        if login_res.status_code == 200:
            httpx.get(f"{GATEWAY_URL}/api/v1/users/users/{target_user}", timeout=3.0)
        
        # 5. Place Multi-Item Orders & Checkout Flow
        if random.random() < 0.6:
            item_count = random.randint(1, 3)
            selected_ids = random.sample(range(1, 13), item_count)
            order_items = [{"product_id": pid, "quantity": random.randint(1, 2)} for pid in selected_ids]
            
            checkout_payload = {
                "items": order_items,
                "customer_username": target_user,
                "payment_method": random.choice(["UPI", "CARD", "NETBANKING", "COD"]),
                "delivery_speed": "PRIME_EXPRESS" if random.random() > 0.3 else "STANDARD",
                "card_last4": str(random.randint(1000, 9999)),
                "shipping_address": {
                    "full_name": "Manikandan Srinivasan",
                    "phone": "+91 98765 43210",
                    "street": "142 Tech Hub Avenue, Koramangala",
                    "city": "Bangalore",
                    "state": "Karnataka",
                    "postal_code": "560034",
                    "country": "India"
                }
            }
            order_res = httpx.post(f"{GATEWAY_URL}/api/v1/orders/orders", json=checkout_payload, timeout=4.0)
            if order_res.status_code == 200:
                print(f"🛒 Order placed successfully: Total items: {item_count}")

        # 6. Periodic notification query
        if random.random() < 0.2:
            httpx.get(f"{GATEWAY_URL}/api/v1/notification/notifications", timeout=3.0)

    except Exception as e:
        print(f"⚠️ Simulation note: {str(e)}")
        
    time.sleep(random.uniform(0.2, 0.8))
