"""Design tools for presentation management."""

import uuid
from typing import Optional
from mcp.server.fastmcp import FastMCP

from ..models import (
    ThemeType,
    ThemeConfig,
    Slide,
    Presentation,
    PresentationStore,
)


# Initialize the store
store = PresentationStore()


def register_design_tools(mcp: FastMCP) -> None:
    """Register all design-related MCP tools."""
    
    @mcp.tool()
    def initialize_design(
        title: str,
        description: str,
        slide_num: int = 5,
        width: int = 1280,
        height: int = 720,
        theme: str = "business"
    ) -> dict:
        """
        Initialize a new presentation design.
        
        Creates a new presentation with specified dimensions and theme.
        Returns presentation ID for subsequent operations.
        
        Args:
            title: Presentation title
            description: Brief description of the presentation content
            slide_num: Expected number of slides (default: 5)
            width: Slide width in pixels (default: 1280)
            height: Slide height in pixels (default: 720)
            theme: Theme name - options: business, deep_tech, futuristic, sophisticated, minimal, dark_mode
        
        Returns:
            Dictionary with presentation_id, title, and configuration
        """
        # Generate unique ID
        presentation_id = str(uuid.uuid4())[:8]
        
        # Parse theme
        theme_map = {
            "business": ThemeType.BUSINESS,
            "deep_tech": ThemeType.DEEP_TECH,
            "futuristic": ThemeType.FUTURISTIC,
            "sophisticated": ThemeType.SOPHISTICATED,
            "minimal": ThemeType.MINIMAL,
            "dark_mode": ThemeType.DARK_MODE,
        }
        theme_type = theme_map.get(theme.lower(), ThemeType.BUSINESS)
        
        # Create presentation
        presentation = Presentation(
            id=presentation_id,
            title=title,
            description=description,
            width=width,
            height=height,
            theme=theme_type,
            slides=[]
        )
        
        store.create(presentation)
        
        theme_config = ThemeConfig.get_theme(theme_type)
        
        return {
            "success": True,
            "presentation_id": presentation_id,
            "title": title,
            "description": description,
            "dimensions": {"width": width, "height": height},
            "expected_slides": slide_num,
            "theme": {
                "name": theme_config.name,
                "background": theme_config.background,
                "primary": theme_config.primary,
                "accent": theme_config.accent,
                "fonts": {
                    "primary": theme_config.font_primary,
                    "secondary": theme_config.font_secondary
                }
            },
            "message": f"Presentation '{title}' initialized. Use insert_page to add slides."
        }
    
    @mcp.tool()
    def insert_page(
        presentation_id: str,
        index: int,
        action_description: str,
        html: str
    ) -> dict:
        """
        Insert a new slide into the presentation.
        
        Args:
            presentation_id: ID from initialize_design
            index: Slide position (1-based, e.g., 1 for first slide)
            action_description: Brief description of slide content
            html: Complete HTML content for the slide (must include DOCTYPE, html, head, body)
        
        Returns:
            Dictionary with slide info and current slide count
        """
        presentation = store.get(presentation_id)
        
        if not presentation:
            return {
                "success": False,
                "error": f"Presentation '{presentation_id}' not found. Initialize first with initialize_design."
            }
        
        # Validate HTML structure
        if not html.strip().startswith("<!DOCTYPE"):
            return {
                "success": False,
                "error": "HTML must start with <!DOCTYPE html>"
            }
        
        # Extract image URLs from HTML (basic extraction)
        import re
        image_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)
        
        # Create slide
        slide = Slide(
            index=index,
            html_content=html,
            action_description=action_description,
            image_urls=image_urls
        )
        
        presentation.add_slide(slide)
        store.update(presentation)
        
        return {
            "success": True,
            "presentation_id": presentation_id,
            "slide_index": index,
            "action_description": action_description,
            "images_found": len(image_urls),
            "total_slides": presentation.slide_count,
            "message": f"Slide {index} added. Total slides: {presentation.slide_count}"
        }
    
    @mcp.tool()
    def update_page(
        presentation_id: str,
        index: int,
        action_description: Optional[str] = None,
        html: Optional[str] = None
    ) -> dict:
        """
        Update an existing slide in the presentation.
        
        Args:
            presentation_id: ID from initialize_design
            index: Slide position to update (1-based)
            action_description: New description (optional, keeps existing if not provided)
            html: New HTML content (optional, keeps existing if not provided)
        
        Returns:
            Dictionary with updated slide info
        """
        presentation = store.get(presentation_id)
        
        if not presentation:
            return {
                "success": False,
                "error": f"Presentation '{presentation_id}' not found."
            }
        
        slide = presentation.get_slide(index)
        
        if not slide:
            return {
                "success": False,
                "error": f"Slide {index} not found in presentation."
            }
        
        # Update fields
        if action_description:
            slide.action_description = action_description
        
        if html:
            if not html.strip().startswith("<!DOCTYPE"):
                return {
                    "success": False,
                    "error": "HTML must start with <!DOCTYPE html>"
                }
            slide.html_content = html
            import re
            slide.image_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html)
        
        store.update(presentation)
        
        return {
            "success": True,
            "presentation_id": presentation_id,
            "slide_index": index,
            "action_description": slide.action_description,
            "total_slides": presentation.slide_count,
            "message": f"Slide {index} updated successfully."
        }
    
    @mcp.tool()
    def remove_pages(
        presentation_id: str,
        indices: list[int]
    ) -> dict:
        """
        Remove slides from the presentation.
        
        Args:
            presentation_id: ID from initialize_design
            indices: List of slide positions to remove (1-based)
        
        Returns:
            Dictionary with removal status
        """
        presentation = store.get(presentation_id)
        
        if not presentation:
            return {
                "success": False,
                "error": f"Presentation '{presentation_id}' not found."
            }
        
        removed_count = presentation.remove_slides(indices)
        store.update(presentation)
        
        return {
            "success": True,
            "presentation_id": presentation_id,
            "removed_count": removed_count,
            "remaining_slides": presentation.slide_count,
            "message": f"Removed {removed_count} slide(s). {presentation.slide_count} slides remaining."
        }
    
    @mcp.tool()
    def get_presentation(presentation_id: str) -> dict:
        """
        Get presentation details and all slides.
        
        Args:
            presentation_id: ID from initialize_design
        
        Returns:
            Complete presentation data including all slides
        """
        presentation = store.get(presentation_id)
        
        if not presentation:
            return {
                "success": False,
                "error": f"Presentation '{presentation_id}' not found."
            }
        
        theme_config = ThemeConfig.get_theme(presentation.theme)
        
        return {
            "success": True,
            "presentation": {
                "id": presentation.id,
                "title": presentation.title,
                "description": presentation.description,
                "dimensions": {
                    "width": presentation.width,
                    "height": presentation.height
                },
                "theme": {
                    "type": presentation.theme.value,
                    "config": theme_config.model_dump()
                },
                "slide_count": presentation.slide_count,
                "slides": [
                    {
                        "index": s.index,
                        "description": s.action_description,
                        "image_count": len(s.image_urls)
                    }
                    for s in sorted(presentation.slides, key=lambda x: x.index)
                ]
            }
        }
    
    @mcp.tool()
    def list_presentations() -> dict:
        """
        List all presentations in the store.
        
        Returns:
            List of all presentations with basic info
        """
        presentations = store.list_all()
        
        return {
            "success": True,
            "count": len(presentations),
            "presentations": [
                {
                    "id": p.id,
                    "title": p.title,
                    "slide_count": p.slide_count,
                    "theme": p.theme.value
                }
                for p in presentations
            ]
        }
