from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .telemetry import instrument_app

app = FastAPI(
    title="Products Service",
    description="Enterprise Product Catalog & Inventory Microservice",
    version="1.0.0"
)
instrument_app(app, "products-service")

@app.get("/healthz")
def healthz():
    return {"status": "healthy", "service": "products"}

class Review(BaseModel):
    author: str
    rating: int
    comment: str
    date: str

class Product(BaseModel):
    id: int
    name: str
    brand: str
    category: str
    price: float
    original_price: float
    discount_percentage: int
    rating: float
    rating_count: int
    stock: int
    badge: Optional[str] = None
    delivery: str
    image_url: str
    description: str
    features: List[str]
    specs: Dict[str, str] = {}
    in_stock: bool = True

class ReviewRequest(BaseModel):
    author: str = Field(..., min_length=2)
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=5)

class StockUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=1)

CATALOG: Dict[int, Dict[str, Any]] = {
    1: {
        "id": 1,
        "name": "Apple iPhone 16 Pro Max (256 GB) - Natural Titanium",
        "brand": "Apple",
        "category": "Mobiles",
        "price": 1199.00,
        "original_price": 1399.00,
        "discount_percentage": 14,
        "rating": 4.9,
        "rating_count": 8420,
        "stock": 45,
        "badge": "Best Seller",
        "delivery": "FREE Prime Next-Day Delivery",
        "image_url": "https://images.unsplash.com/photo-1695048133142-1a20484d2569?auto=format&fit=crop&w=800&q=80",
        "description": "Forged in titanium with industry-leading A18 Pro chip, 48MP Fusion camera system, and extraordinary battery life.",
        "features": [
            "Titanium design with textured matte glass back",
            "A18 Pro chip with 6-core GPU",
            "48MP Fusion Camera with 5x Telephoto Optical Zoom",
            "Super Retina XDR display with ProMotion up to 120Hz"
        ],
        "specs": {
            "Screen Size": "6.9 inches OLED",
            "Storage": "256 GB",
            "Color": "Natural Titanium",
            "Battery": "Up to 33 hours video playback",
            "Connectivity": "5G, Wi-Fi 7, Bluetooth 5.3"
        },
        "in_stock": True
    },
    2: {
        "id": 2,
        "name": "Samsung Galaxy S24 Ultra 5G (512 GB) - Titanium Gray",
        "brand": "Samsung",
        "category": "Mobiles",
        "price": 1299.99,
        "original_price": 1499.99,
        "discount_percentage": 13,
        "rating": 4.8,
        "rating_count": 6210,
        "stock": 38,
        "badge": "Amazon's Choice",
        "delivery": "FREE Prime Delivery Tomorrow, 11 AM",
        "image_url": "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?auto=format&fit=crop&w=800&q=80",
        "description": "Welcome to the era of Galaxy AI. Effortlessly edit photos, live-translate calls, and capture night photos with 200MP camera.",
        "features": [
            "Galaxy AI with Live Translate and Note Assist",
            "Built-in S Pen for precision writing & gestures",
            "200MP wide-angle camera with Quad Tele System",
            "Corning Gorilla Armor anti-reflective glass"
        ],
        "specs": {
            "Screen Size": "6.8 inches Dynamic AMOLED 2X",
            "RAM / Storage": "12 GB RAM / 512 GB Storage",
            "Processor": "Snapdragon 8 Gen 3 for Galaxy",
            "Battery": "5000 mAh Fast Charging"
        },
        "in_stock": True
    },
    3: {
        "id": 3,
        "name": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
        "brand": "Sony",
        "category": "Audio",
        "price": 348.00,
        "original_price": 399.99,
        "discount_percentage": 13,
        "rating": 4.8,
        "rating_count": 14200,
        "stock": 85,
        "badge": "Top Deal",
        "delivery": "FREE Delivery Today by 7 PM",
        "image_url": "https://images.unsplash.com/photo-1546435770-a3e426bf472b?auto=format&fit=crop&w=800&q=80",
        "description": "Industry-leading noise cancellation optimized automatically with two processors and 8 microphones for unparalleled clarity.",
        "features": [
            "Auto NC Optimizer delivers custom noise cancellation",
            "Up to 30-hour battery life with 3-minute quick charge for 3 hours playback",
            "Crystal-clear hands-free calling with 4 beamforming mics",
            "Multipoint connection allows pairing two Bluetooth devices"
        ],
        "specs": {
            "Type": "Over-Ear Wireless",
            "Battery Life": "30 Hours ANC On",
            "Weight": "250g Ultra-lightweight",
            "Audio Codecs": "LDAC, AAC, SBC, Hi-Res Audio"
        },
        "in_stock": True
    },
    4: {
        "id": 4,
        "name": "Apple MacBook Pro 14-inch (M3 Max, 36GB Unified Memory, 1TB SSD)",
        "brand": "Apple",
        "category": "Laptops",
        "price": 2799.00,
        "original_price": 3199.00,
        "discount_percentage": 12,
        "rating": 4.9,
        "rating_count": 3150,
        "stock": 20,
        "badge": "Flipkart Assured",
        "delivery": "FREE Express Delivery Tomorrow",
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=800&q=80",
        "description": "Monster performance with M3 Max 14-core CPU and 30-core GPU. Liquid Retina XDR display with Extreme Dynamic Range.",
        "features": [
            "Apple M3 Max Chip (14-core CPU, 30-core GPU)",
            "14.2-inch Liquid Retina XDR display (1000 nits sustained)",
            "Up to 18 hours battery life on a single charge",
            "HDMI port, SDXC card slot, 3x Thunderbolt 4 ports, MagSafe 3"
        ],
        "specs": {
            "Memory": "36 GB Unified RAM",
            "Storage": "1 TB Superfast NVMe SSD",
            "Color": "Space Black",
            "Weight": "1.62 kg"
        },
        "in_stock": True
    },
    5: {
        "id": 5,
        "name": "Apple Watch Ultra 2 GPS + Cellular 49mm Titanium",
        "brand": "Apple",
        "category": "Wearables",
        "price": 749.00,
        "original_price": 799.00,
        "discount_percentage": 6,
        "rating": 4.9,
        "rating_count": 4890,
        "stock": 32,
        "badge": "Prime Deal",
        "delivery": "FREE Prime Delivery Tomorrow",
        "image_url": "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?auto=format&fit=crop&w=800&q=80",
        "description": "The ultimate sports and adventure watch with precision dual-frequency GPS, 3000 nits display, and customizable Action Button.",
        "features": [
            "49mm aerospace-grade titanium case",
            "Brightest Apple display ever at 3000 nits",
            "Up to 36 hours of normal use, 72 hours in Low Power Mode",
            "Water resistance 100m, high-speed water sports and scuba diving to 40m"
        ],
        "specs": {
            "Case Size": "49mm Titanium",
            "Connectivity": "GPS + Cellular LTE",
            "Band": "Orange Ocean Band",
            "Sensors": "ECG, Blood Oxygen, Depth Gauge, Water Temp"
        },
        "in_stock": True
    },
    6: {
        "id": 6,
        "name": "Sony Alpha 7 IV Full-Frame Mirrorless Hybrid Camera (Body Only)",
        "brand": "Sony",
        "category": "Cameras",
        "price": 2298.00,
        "original_price": 2499.99,
        "discount_percentage": 8,
        "rating": 4.8,
        "rating_count": 2840,
        "stock": 14,
        "badge": "Pro Choice",
        "delivery": "FREE Insured Express Delivery",
        "image_url": "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=800&q=80",
        "description": "Next-generation 33MP Exmor R CMOS sensor with 4K 60p 10-bit 4:2:2 video and Real-time Eye AF for Humans, Animals, and Birds.",
        "features": [
            "33MP Full-Frame Back-Illuminated CMOS Sensor",
            "BIONZ XR image processor for 8x faster processing",
            "4K 60p 10-bit 4:2:2 movie recording & S-Cinetone",
            "759-point phase-detection AF covering 94% of image area"
        ],
        "specs": {
            "Sensor": "33 Megapixel Full-Frame",
            "Mount": "Sony E-Mount",
            "ISO Range": "100 - 51,200",
            "Stabilization": "5-Axis Optical In-Body Image Stabilization"
        },
        "in_stock": True
    },
    7: {
        "id": 7,
        "name": "Bose QuietComfort Ultra Wireless Noise Cancelling Earbuds",
        "brand": "Bose",
        "category": "Audio",
        "price": 249.00,
        "original_price": 299.00,
        "discount_percentage": 17,
        "rating": 4.7,
        "rating_count": 5120,
        "stock": 60,
        "badge": "Best Seller",
        "delivery": "FREE Prime Delivery Tomorrow",
        "image_url": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=800&q=80",
        "description": "Breakthrough spatialized audio for immersive listening no matter the content, paired with world-class noise cancellation.",
        "features": [
            "Bose Immersive Audio pushes boundaries of sound staging",
            "CustomTune technology tailors audio to your ear shape",
            "Nine soft eartip & stability band combinations for all-day comfort",
            "Simple touch controls on each earbud for music & volume"
        ],
        "specs": {
            "Battery": "6 Hours per charge (24 Hours with Case)",
            "Water Rating": "IPX4 Sweat & Weather Resistant",
            "Color": "Black Smoke",
            "Bluetooth": "5.3 with Snapdragon Sound"
        },
        "in_stock": True
    },
    8: {
        "id": 8,
        "name": "LG UltraGear 27-inch 4K OLED 240Hz 0.03ms Gaming Monitor",
        "brand": "LG",
        "category": "Laptops",
        "price": 899.99,
        "original_price": 1099.99,
        "discount_percentage": 18,
        "rating": 4.9,
        "rating_count": 1940,
        "stock": 25,
        "badge": "Top Deal",
        "delivery": "FREE Scheduled Delivery",
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=800&q=80",
        "description": "Blistering 240Hz refresh rate and near-instant 0.03ms response time with true RGB OLED self-lit pixels and 1.5M:1 contrast.",
        "features": [
            "27-inch 4K UHD (3840 x 2160) OLED Panel",
            "240Hz Refresh Rate with 0.03ms (GtG) response time",
            "NVIDIA G-SYNC Compatible & AMD FreeSync Premium Pro",
            "DisplayHDR True Black 400 with 98.5% DCI-P3 color gamut"
        ],
        "specs": {
            "Resolution": "3840 x 2160 Pixels (4K)",
            "Ports": "2x HDMI 2.1, 1x DisplayPort 1.4, USB 3.0 Hub",
            "Stand": "Tilt, Height, Swivel, Pivot Adjustable"
        },
        "in_stock": True
    },
    9: {
        "id": 9,
        "name": "Amazon Echo Studio - High-Fidelity Smart Speaker with 3D Audio",
        "brand": "Amazon",
        "category": "Smart Home",
        "price": 199.99,
        "original_price": 249.99,
        "discount_percentage": 20,
        "rating": 4.7,
        "rating_count": 9830,
        "stock": 50,
        "badge": "Amazon's Choice",
        "delivery": "FREE Prime Same-Day Delivery",
        "image_url": "https://images.unsplash.com/photo-1543512214-318c7553f230?auto=format&fit=crop&w=800&q=80",
        "description": "Immersive sound with 5 strategically positioned speakers producing powerful bass, dynamic midrange, and crisp highs with Dolby Atmos.",
        "features": [
            "5 directional speakers with Dolby Atmos & Sony 360 Reality Audio",
            "Automatically senses acoustics of your space and fine-tunes playback",
            "Built-in smart home hub compatible with Zigbee & Matter devices",
            "Ask Alexa to stream music, check weather, or control your smart home"
        ],
        "specs": {
            "Speakers": "3x 2-inch midrange, 1-inch tweeter, 5.25-inch woofer",
            "DAC": "24-bit DAC with 100 kHz bandwidth",
            "Smart Protocols": "Zigbee, Matter, Thread, Wi-Fi 6"
        },
        "in_stock": True
    },
    10: {
        "id": 10,
        "name": "Dyson V15 Detect Extra Cordless Vacuum Cleaner",
        "brand": "Dyson",
        "category": "Smart Home",
        "price": 649.99,
        "original_price": 749.99,
        "discount_percentage": 13,
        "rating": 4.8,
        "rating_count": 3410,
        "stock": 19,
        "badge": "Flipkart Assured",
        "delivery": "FREE Express Delivery",
        "image_url": "https://images.unsplash.com/photo-1558317374-067fb5f30001?auto=format&fit=crop&w=800&q=80",
        "description": "Dyson's most powerful, intelligent cordless vacuum with laser illumination revealing invisible dust on hard floors.",
        "features": [
            "Laser reveals microscopic dust invisible to the naked eye",
            "Piezo sensor continuously sizes and counts dust particles",
            "LCD screen shows scientific proof of a deep clean in real time",
            "Up to 60 minutes of run time with advanced whole-machine filtration"
        ],
        "specs": {
            "Suction Power": "240 Air Watts",
            "Bin Volume": "0.77 Liters",
            "Weight": "3.1 kg",
            "Run Time": "60 Minutes"
        },
        "in_stock": True
    },
    11: {
        "id": 11,
        "name": "Nike Air Jordan 1 Retro High OG - Chicago Lost & Found",
        "brand": "Nike",
        "category": "Fashion",
        "price": 180.00,
        "original_price": 220.00,
        "discount_percentage": 18,
        "rating": 4.9,
        "rating_count": 7890,
        "stock": 40,
        "badge": "Trending",
        "delivery": "FREE 2-Day Delivery",
        "image_url": "https://images.unsplash.com/photo-1552346154-21d32810aba3?auto=format&fit=crop&w=800&q=80",
        "description": "The legendary 1985 silhouette returns with vintage aged aesthetic, premium cracked leather, and original packaging box.",
        "features": [
            "Genuine leather upper with vintage cracked leather collar",
            "Encapsulated Nike Air-Sole unit in the heel for lightweight cushioning",
            "Solid rubber outsole with deep flex grooves for traction",
            "Authentic archival retro receipt and packaging"
        ],
        "specs": {
            "Colorway": "Varsity Red / Black / Sail / Muslin",
            "Material": "100% Full-grain Leather",
            "Sizes Available": "US 7 to US 13"
        },
        "in_stock": True
    },
    12: {
        "id": 12,
        "name": "Logitech MX Master 3S Wireless Performance Mouse",
        "brand": "Logitech",
        "category": "Accessories",
        "price": 99.99,
        "original_price": 119.99,
        "discount_percentage": 17,
        "rating": 4.9,
        "rating_count": 22100,
        "stock": 110,
        "badge": "Best Seller",
        "delivery": "FREE Prime Delivery Tomorrow",
        "image_url": "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?auto=format&fit=crop&w=800&q=80",
        "description": "An icon remastered. Feel every single moment of your workflow with Quiet Clicks and an 8,000 DPI track-on-glass sensor.",
        "features": [
            "8,000 DPI Darkfield sensor tracks on any surface, even glass",
            "Quiet Click switches offer tactile feel with 90% less click noise",
            "MagSpeed electromagnetic scrolling scrolls 1,000 lines in 1 second",
            "Pair up to 3 devices via Bluetooth or Logi Bolt receiver"
        ],
        "specs": {
            "Sensor DPI": "200 to 8000 DPI",
            "Battery": "Up to 70 days on full charge",
            "Charging": "USB-C Fast Charging (1 min = 3 hrs)",
            "Color": "Graphite"
        },
        "in_stock": True
    }
}

REVIEWS: Dict[int, List[Dict[str, Any]]] = {
    1: [
        {"author": "Rohit Sharma", "rating": 5, "comment": "Outstanding battery life and titanium finish feels so premium in hand!", "date": "2 days ago"},
        {"author": "Ananya Iyer", "rating": 5, "comment": "Camera quality is unmatched, 5x telephoto is super sharp.", "date": "1 week ago"}
    ],
    2: [
        {"author": "Vikram Singh", "rating": 5, "comment": "Galaxy AI circle-to-search is actually mindblowing for work.", "date": "3 days ago"}
    ],
    3: [
        {"author": "Deepak Kumar", "rating": 5, "comment": "Best noise cancellation on flights, cuts out jet engine noise completely.", "date": "5 days ago"}
    ]
}

@app.get("/products")
def list_products(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search keyword in name or brand"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    badge: Optional[str] = Query(None, description="Filter by badge like 'Best Seller'"),
    sort_by: Optional[str] = Query("popular", description="Sort: popular, price_asc, price_desc, rating")
) -> List[Dict[str, Any]]:
    results = list(CATALOG.values())

    if category and category.lower() != "all":
        results = [p for p in results if p["category"].lower() == category.lower()]

    if search:
        s = search.lower().strip()
        results = [
            p for p in results 
            if s in p["name"].lower() or s in p["brand"].lower() or s in p["description"].lower() or s in p["category"].lower()
        ]

    if min_price is not None:
        results = [p for p in results if p["price"] >= min_price]

    if max_price is not None:
        results = [p for p in results if p["price"] <= max_price]

    if badge:
        results = [p for p in results if p.get("badge") and badge.lower() in p["badge"].lower()]

    if sort_by == "price_asc":
        results.sort(key=lambda x: x["price"])
    elif sort_by == "price_desc":
        results.sort(key=lambda x: x["price"], reverse=True)
    elif sort_by == "rating":
        results.sort(key=lambda x: x["rating"], reverse=True)
    elif sort_by == "discount":
        results.sort(key=lambda x: x["discount_percentage"], reverse=True)

    return results

@app.get("/products/{product_id}")
def get_product(product_id: int):
    if product_id not in CATALOG:
        raise HTTPException(status_code=404, detail=f"Product with ID {product_id} not found")
    
    prod = dict(CATALOG[product_id])
    prod["reviews"] = REVIEWS.get(product_id, [
        {"author": "Verified Customer", "rating": 5, "comment": "Great product, highly recommend!", "date": "Just now"}
    ])
    return prod

@app.get("/categories")
def get_categories():
    categories = {}
    for p in CATALOG.values():
        c = p["category"]
        if c not in categories:
            categories[c] = {
                "name": c,
                "count": 0,
                "thumbnail": p["image_url"]
            }
        categories[c]["count"] += 1
    return list(categories.values())

@app.get("/deals")
def get_deals():
    deals = [p for p in CATALOG.values() if p.get("discount_percentage", 0) >= 12]
    deals.sort(key=lambda x: x["discount_percentage"], reverse=True)
    return deals[:6]

@app.put("/products/{product_id}/stock")
def update_stock(product_id: int, req: StockUpdateRequest):
    if product_id not in CATALOG:
        raise HTTPException(status_code=404, detail="Product not found")
    
    current_stock = CATALOG[product_id]["stock"]
    if current_stock < req.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock. Available: {current_stock}, Requested: {req.quantity}")
    
    CATALOG[product_id]["stock"] -= req.quantity
    if CATALOG[product_id]["stock"] <= 0:
        CATALOG[product_id]["in_stock"] = False
        
    return {
        "product_id": product_id,
        "remaining_stock": CATALOG[product_id]["stock"],
        "in_stock": CATALOG[product_id]["in_stock"]
    }

@app.post("/products/{product_id}/reviews")
def add_review(product_id: int, req: ReviewRequest):
    if product_id not in CATALOG:
        raise HTTPException(status_code=404, detail="Product not found")
        
    if product_id not in REVIEWS:
        REVIEWS[product_id] = []
        
    new_rev = {
        "author": req.author,
        "rating": req.rating,
        "comment": req.comment,
        "date": "Just now"
    }
    REVIEWS[product_id].insert(0, new_rev)
    return {"message": "Review submitted successfully", "review": new_rev}