"""Image search functionality for presentations."""

import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Image search API configuration
IMAGE_SEARCH_BASE_URL = "https://sfile.chatglm.cn/images-ppt"


class ImageSearchResult:
    """Represents an image search result."""
    def __init__(self, url: str, width: int = 0, height: int = 0, alt: str = ""):
        self.url = url
        self.width = width
        self.height = height
        self.alt = alt
    
    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "width": self.width,
            "height": self.height,
            "alt": self.alt
        }


async def search_images(
    query: str,
    limit: int = 5,
    orientation: Optional[str] = None,
    min_width: int = 400,
    min_height: int = 300
) -> list[ImageSearchResult]:
    """
    Search for images suitable for presentations.
    
    Uses multiple free sources without API keys:
    1. Wikimedia Commons (curated, educational images)
    2. Unsplash Source (high-quality photos)
    3. Lorem Picsum (random beautiful images as fallback)
    
    Args:
        query: Search query describing the desired image
        limit: Maximum number of results to return
        orientation: Image orientation - 'landscape', 'portrait', or 'square'
        min_width: Minimum image width
        min_height: Minimum image height
    
    Returns:
        List of ImageSearchResult objects
    """
    results: list[ImageSearchResult] = []

    # Try Wikimedia Commons first (best for educational/technical content)
    try:
        wikimedia_results = await _search_wikimedia(query, limit, orientation, min_width, min_height)
        results.extend(wikimedia_results)
    except Exception as e:
        logger.warning(f"Wikimedia search failed: {e}")

    # If not enough results, add Unsplash Source images
    if len(results) < limit:
        try:
            unsplash_results = _get_unsplash_source_images(query, limit - len(results), orientation)
            results.extend(unsplash_results)
        except Exception as e:
            logger.warning(f"Unsplash source failed: {e}")

    # Final fallback to Lorem Picsum if still not enough
    if len(results) < limit:
        picsum_results = _get_picsum_images(query, limit - len(results))
        results.extend(picsum_results)

    return results[:limit]


async def _search_wikimedia(
    query: str,
    limit: int,
    orientation: Optional[str],
    min_width: int,
    min_height: int
) -> list[ImageSearchResult]:
    """Search Wikimedia Commons for images."""
    results: list[ImageSearchResult] = []
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": max(limit * 3, 10),
                "gsrnamespace": 6,  # File:
                "prop": "imageinfo",
                "iiprop": "url|size",
                "iiurlwidth": 1600,
            },
            headers={"User-Agent": "presentation-mcp-server/0.1.0"},
        )

        if response.status_code == 200:
            data = response.json()
            pages = (data.get("query", {}) or {}).get("pages", {}) or {}

            for _, page in pages.items():
                imageinfo = (page or {}).get("imageinfo") or []
                if not imageinfo:
                    continue
                ii = imageinfo[0] or {}

                url = ii.get("thumburl") or ii.get("url")
                width = int(ii.get("thumbwidth") or ii.get("width") or 0)
                height = int(ii.get("thumbheight") or ii.get("height") or 0)
                if not url:
                    continue

                if width and width < min_width:
                    continue
                if height and height < min_height:
                    continue

                if orientation:
                    o = orientation.lower()
                    if o == "landscape" and height and width and width < height:
                        continue
                    if o == "portrait" and height and width and height < width:
                        continue
                    if o == "square" and height and width and abs(width - height) > min(width, height) * 0.15:
                        continue

                results.append(
                    ImageSearchResult(
                        url=url,
                        width=width,
                        height=height,
                        alt=page.get("title", query),
                    )
                )

                if len(results) >= limit:
                    break

    return results


def _get_unsplash_source_images(
    query: str,
    limit: int,
    orientation: Optional[str] = None
) -> list[ImageSearchResult]:
    """
    Get images from Unsplash Source (free, no API key required).
    
    Unsplash Source provides random images matching keywords.
    URL format: https://source.unsplash.com/{width}x{height}/?{keywords}
    """
    results = []
    
    # Calculate dimensions based on orientation
    if orientation == "portrait":
        width, height = 600, 800
    elif orientation == "square":
        width, height = 800, 800
    else:  # landscape (default)
        width, height = 1280, 720
    
    # Clean query for URL
    keywords = query.replace(" ", ",").lower()
    
    for i in range(limit):
        # Unsplash Source URL with random parameter to get different images
        url = f"https://source.unsplash.com/{width}x{height}/?{keywords}&sig={hash(f'{query}_{i}') % 10000}"
        
        results.append(ImageSearchResult(
            url=url,
            width=width,
            height=height,
            alt=f"{query} - Unsplash photo {i+1}"
        ))
    
    return results


def _get_picsum_images(query: str, limit: int) -> list[ImageSearchResult]:
    """Get beautiful random images from Lorem Picsum."""
    results = []
    
    for i in range(limit):
        seed = abs(hash(f"{query}_{i}")) % 1000
        url = f"https://picsum.photos/seed/{seed}/1280/720"
        
        results.append(ImageSearchResult(
            url=url,
            width=1280,
            height=720,
            alt=f"{query} - image {i+1}"
        ))
    
    return results


def _get_placeholder_images(query: str, limit: int) -> list[ImageSearchResult]:
    """Generate placeholder image URLs as fallback."""
    # Use picsum.photos for placeholder images
    results = []
    categories = ["technology", "business", "nature", "abstract", "city"]
    
    for i in range(min(limit, 5)):
        # Generate unique placeholder URL
        seed = hash(f"{query}_{i}") % 1000
        url = f"https://picsum.photos/seed/{seed}/800/600"
        results.append(ImageSearchResult(
            url=url,
            width=800,
            height=600,
            alt=f"{query} image {i+1}"
        ))
    
    return results


def get_image_url_for_slide(
    description: str,
    theme: str = "professional",
    max_height: int = 720
) -> str:
    """
    Get a single optimized image URL for a slide.
    
    Args:
        description: Description of desired image
        theme: Visual theme preference
        max_height: Maximum height constraint
    
    Returns:
        URL of selected image
    """
    # Calculate appropriate dimensions
    aspect_ratio = 16 / 9  # Standard presentation aspect ratio
    width = int(max_height * aspect_ratio)
    
    # Use placeholder service with calculated dimensions
    seed = abs(hash(description)) % 1000
    return f"https://picsum.photos/seed/{seed}/{width}/{max_height}"


def get_icon_url(icon_name: str) -> str:
    """Get URL for an icon image."""
    # Using Material Icons or similar
    return f"https://fonts.googleapis.com/icon?family=Material+Icons"


# Pre-defined image categories for common slide types
SLIDE_IMAGE_CATEGORIES = {
    "title": ["abstract", "gradient", "pattern"],
    "about": ["team", "office", "people"],
    "features": ["technology", "innovation", "digital"],
    "benefits": ["success", "growth", "achievement"],
    "process": ["workflow", "diagram", "steps"],
    "team": ["teamwork", "collaboration", "people"],
    "contact": ["communication", "phone", "email"],
    "closing": ["thank you", "success", "celebration"],
}


def suggest_image_category(slide_type: str) -> list[str]:
    """Suggest image categories based on slide type."""
    return SLIDE_IMAGE_CATEGORIES.get(slide_type.lower(), ["abstract"])
