"""Presentation MCP Server - Main entry point."""

import os
import sys
import logging
import base64
import mimetypes
from typing import Optional
from mcp.server.fastmcp import FastMCP

from .models import PresentationStore, ThemeConfig
from .tools.design import register_design_tools
from .tools.images import search_images, get_image_url_for_slide
from .converter import convert_html_slides_to_pptx

# Configure logging to stderr for STDIO transport
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
MCP_MODEL_INSTRUCTIONS = """You are a presentation-design agent.

Goal: produce production-quality PPTX/PDF exports from HTML slides.

Process requirements:
1) Plan first.
   - Create an outline and decide an appropriate number of slides (do not blindly use defaults).
   - Confirm title, audience, tone, and language.
2) Strict slide layout.
   - Each slide MUST be a complete HTML document starting with <!DOCTYPE html>.
   - Slides are rendered at exactly 1280x720. Design within this fixed canvas.
   - Avoid auto-growing layouts that can overflow. Use fixed regions (header/content/footer), fixed image heights,
     and clamp text with max-height + overflow:hidden where needed.
   - Always set: html, body { margin:0; padding:0; width:1280px; height:720px; overflow:hidden; }
   - Prefer deterministic CSS over relying on external runtime behavior.
3) Images are required.
   - Unless the user explicitly requests a text-only deck, include relevant images and use them to support the message.
   - Recommended: use a strong full-bleed (hero) image on the first slide with a readable text overlay (gradient/scrim for contrast).
   - Spread images across slides (e.g., hero image + supporting visuals). Prefer fewer, stronger images over many low-quality ones.
   - Use search_images_tool to find suitable landscape images.
   - Reliability (avoid broken images in final export):
     - Prefer using URL-based <img src="http(s)://..."> for external images; the export pipeline will attempt to embed these
       into data URIs during export.
     - The export pipeline will also attempt to embed <img src="file://..."> and relative/absolute local paths during export.
     - If you need maximum reliability at authoring time (or a URL is flaky/blocked), you can pre-embed images as data URIs using:
       fetch_image_to_data_uri(url) or local_image_to_data_uri(path).
     - If the deck would get too large, downscale images via fetch_image_to_data_uri(max_size_px=...).
4) Quality control.
   - Keep content inside a safe area (recommend ~56px padding from edges).
   - Ensure contrast, legible font sizes, and consistent visual hierarchy.
5) Export is required.
   - Always export BOTH PPTX and PDF at the end, unless the user asks otherwise.
   - You MUST provide explicit output_path for BOTH export_pptx and export_pdf (no defaults).
   - Use: fit_mode='contain' (no crop), safe_margin_px≈56, render_bleed_px≈24.

Tool usage:
- initialize_design -> insert_page (for each slide) -> export_pptx and export_pdf.
"""

mcp = FastMCP("presentation-server", instructions=MCP_MODEL_INSTRUCTIONS)

# Register design tools
register_design_tools(mcp)

# Get the store instance
store = PresentationStore()


def _embed_external_images_in_html(
    html: str,
    max_size_px: int = 1024,
    timeout_s: float = 30.0,
) -> str:
    try:
        import re
        from io import BytesIO

        import httpx
        from PIL import Image

        if not html:
            return html

        img_src_re = re.compile(r"(<img\b[^>]*?\bsrc=)([\"'])([^\"']+)(\2)", re.IGNORECASE)

        def repl(m: re.Match) -> str:
            prefix, quote, src, suffix_quote = m.group(1), m.group(2), m.group(3), m.group(4)
            if src.startswith("data:"):
                return m.group(0)

            # Support local files to avoid pushing large base64 through MCP.
            local_path: Optional[str] = None
            if src.startswith("file://"):
                local_path = src[len("file://"):]
            elif src.startswith("/") or src.startswith("./") or src.startswith("../"):
                local_path = src

            if local_path is None and not (src.startswith("http://") or src.startswith("https://")):
                return m.group(0)

            try:
                raw_bytes: bytes
                if local_path is not None:
                    abs_path = os.path.abspath(local_path)
                    if not os.path.exists(abs_path):
                        logger.warning(f"export embed: local file not found path={abs_path}")
                        return m.group(0)
                    with open(abs_path, "rb") as f:
                        raw_bytes = f.read()
                else:
                    headers = {
                        "User-Agent": "presentation-mcp-server/1.0",
                        "Accept": "image/*,*/*;q=0.8",
                    }
                    resp = httpx.get(src, timeout=timeout_s, follow_redirects=True, headers=headers)
                    if resp.status_code != 200 or not resp.content:
                        return m.group(0)

                    content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
                    if content_type and not content_type.startswith("image/"):
                        logger.warning(f"export embed: non-image content-type={content_type} url={src}")
                    raw_bytes = resp.content

                with Image.open(BytesIO(raw_bytes)) as img:
                    img = img.convert("RGBA")
                    w, h = img.size
                    longest = max(w, h)
                    if max_size_px and longest > max_size_px:
                        scale = max_size_px / float(longest)
                        new_w = max(1, int(w * scale))
                        new_h = max(1, int(h * scale))
                        img = img.resize((new_w, new_h), resample=Image.LANCZOS)

                    out = BytesIO()
                    img.save(out, format="PNG", optimize=True)
                    png_bytes = out.getvalue()

                b64 = base64.b64encode(png_bytes).decode("ascii")
                data_uri = f"data:image/png;base64,{b64}"
                return f"{prefix}{quote}{data_uri}{suffix_quote}"

            except Exception as e:
                logger.warning(f"export embed: failed to embed src={src}: {e}")
                return m.group(0)

        return img_src_re.sub(repl, html)
    except Exception:
        return html


@mcp.tool()
def local_image_to_data_uri(file_path: str, max_size_px: int = 1920) -> dict:
    """Convert a local image file into a data URI.

    This enables models to embed local assets (charts, screenshots, generated
    plots) directly into slide HTML via <img src="data:..."> without hosting.

    Args:
        file_path: Absolute or relative path to an image file.

    Returns:
        data_uri: A base64-encoded data URI suitable for <img src="...">
    """
    try:
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            return {"success": False, "error": f"File not found: {abs_path}"}

        from io import BytesIO
        from PIL import Image

        # Decode and optionally downscale to reduce payload size.
        with Image.open(abs_path) as img:
            img = img.convert("RGBA")
            w, h = img.size
            longest = max(w, h)
            if max_size_px and longest > max_size_px:
                scale = max_size_px / float(longest)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                img = img.resize((new_w, new_h), resample=Image.LANCZOS)

            out = BytesIO()
            img.save(out, format="PNG", optimize=True)
            png_bytes = out.getvalue()

        b64 = base64.b64encode(png_bytes).decode("utf-8")
        return {
            "success": True,
            "file_path": abs_path,
            "mime": "image/png",
            "data_uri": f"data:image/png;base64,{b64}",
        }
    except Exception as e:
        logger.error(f"local_image_to_data_uri failed: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def fetch_image_to_data_uri(
    url: str,
    max_size_px: int = 1920,
    timeout_s: float = 30.0,
) -> dict:
    """Download an external image URL and convert it into a data URI.

    This makes image usage reliable (no hotlink/403 surprises during export).

    Args:
        url: Image URL (http/https)
        max_size_px: If the image is larger than this on the longest side, it will be downscaled.
        timeout_s: Download timeout

    Returns:
        data_uri: A base64-encoded data URI suitable for <img src="...">
    """
    try:
        if not url or not isinstance(url, str):
            return {"success": False, "error": "url is required"}

        import httpx
        from io import BytesIO
        from PIL import Image

        headers = {
            "User-Agent": "presentation-mcp-server/1.0",
            "Accept": "image/*,*/*;q=0.8",
        }

        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)

        if resp.status_code != 200:
            return {"success": False, "error": f"Failed to fetch image (status={resp.status_code})", "url": url}

        content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
        if content_type and not content_type.startswith("image/"):
            # still try to decode, but warn
            logger.warning(f"fetch_image_to_data_uri: non-image content-type={content_type} url={url}")

        raw = resp.content
        if not raw:
            return {"success": False, "error": "Empty response body", "url": url}

        # Validate + normalize by decoding with Pillow
        try:
            with Image.open(BytesIO(raw)) as img:
                img = img.convert("RGBA")
                w, h = img.size
                longest = max(w, h)
                if max_size_px and longest > max_size_px:
                    scale = max_size_px / float(longest)
                    new_w = max(1, int(w * scale))
                    new_h = max(1, int(h * scale))
                    img = img.resize((new_w, new_h), resample=Image.LANCZOS)

                out = BytesIO()
                # Use PNG to preserve alpha and avoid jpeg artifacts
                img.save(out, format="PNG", optimize=True)
                png_bytes = out.getvalue()
        except Exception as e:
            return {"success": False, "error": f"Failed to decode image: {str(e)}", "url": url}

        b64 = base64.b64encode(png_bytes).decode("ascii")
        return {
            "success": True,
            "source_url": url,
            "mime": "image/png",
            "data_uri": f"data:image/png;base64,{b64}",
            "bytes": len(png_bytes),
        }

    except Exception as e:
        logger.error(f"fetch_image_to_data_uri failed: {e}")
        return {"success": False, "error": str(e), "url": url}


@mcp.tool()
async def search_images_tool(
    query: str,
    limit: int = 5,
    orientation: Optional[str] = None
) -> dict:
    """
    Search for images suitable for presentation slides.
    
    Use this to find relevant images for your slides before inserting them.
    
    Args:
        query: Description of the image you're looking for (e.g., "business meeting", "technology background")
        limit: Maximum number of images to return (default: 5)
        orientation: Image orientation - 'landscape', 'portrait', or 'square' (default: landscape)
    
    Returns:
        List of image URLs with dimensions and descriptions
    """
    results = await search_images(
        query=query,
        limit=limit,
        orientation=orientation
    )
    
    return {
        "success": True,
        "query": query,
        "count": len(results),
        "images": [
            {
                "url": img.url,
                "width": img.width,
                "height": img.height,
                "alt": img.alt,
                "usage_hint": f"Use in <img> tag: <img src=\"{img.url}\" width=\"{min(img.width, 800)}\" />"
            }
            for img in results
        ]
    }


@mcp.tool()
def export_pptx(
    presentation_id: str,
    output_path: Optional[str] = None,
    fit_mode: str = "contain",
    safe_margin_px: int = 0,
    render_bleed_px: int = 0,
) -> dict:
    """
    Export the presentation as a PowerPoint (.pptx) file.
    
    Converts all HTML slides to a downloadable PPTX file.
    
    Args:
        presentation_id: ID from initialize_design
        output_path: Optional path to save the file. If not provided, saves to temp directory.
        fit_mode: How to fit rendered slides into PPTX: 'contain' (no crop), 'cover' (fill + crop), 'stretch'
        safe_margin_px: Optional safe padding injected into HTML to reduce text clipping
        render_bleed_px: Extra pixels around the viewport during render, then center-cropped to reduce edge clipping
    
    Returns:
        Path to the generated PPTX file
    """
    presentation = store.get(presentation_id)
    
    if not presentation:
        return {
            "success": False,
            "error": f"Presentation '{presentation_id}' not found."
        }
    
    if presentation.slide_count == 0:
        return {
            "success": False,
            "error": "No slides to export. Add slides with insert_page first."
        }

    if not output_path:
        return {
            "success": False,
            "error": "output_path is required. Provide an explicit .pptx path."
        }
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or os.getcwd(), exist_ok=True)
    
    # Get theme config
    theme_config = ThemeConfig.get_theme(presentation.theme)
    
    # Convert slides
    slides_data = [
        {
            "index": slide.index,
            "html_content": _embed_external_images_in_html(slide.html_content)
        }
        for slide in presentation.slides
    ]
    
    try:
        result_path = convert_html_slides_to_pptx(
            slides=slides_data,
            output_path=output_path,
            width=presentation.width,
            height=presentation.height,
            theme_config=theme_config.model_dump(),
            fit_mode=fit_mode,
            safe_margin_px=safe_margin_px,
            render_bleed_px=render_bleed_px,
        )
        
        return {
            "success": True,
            "presentation_id": presentation_id,
            "output_path": result_path,
            "slide_count": presentation.slide_count,
            "title": presentation.title,
            "message": f"Presentation exported successfully to: {result_path}"
        }
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return {
            "success": False,
            "error": f"Export failed: {str(e)}"
        }


@mcp.tool()
def export_pdf(
    presentation_id: str,
    output_path: Optional[str] = None,
    fit_mode: str = "contain",
    safe_margin_px: int = 0,
    render_bleed_px: int = 0,
) -> dict:
    """Export the presentation as a PDF.

    Implementation:
    - Export to PPTX first (same rendering settings)
    - Convert PPTX -> PDF via LibreOffice headless

    Args:
        presentation_id: ID from initialize_design
        output_path: Optional path to save the PDF. If not provided, saves next to the PPTX
        fit_mode: 'contain' (no crop), 'cover' (fill + crop), 'stretch'
        safe_margin_px: Optional safe padding injected into HTML to reduce text clipping

    Returns:
        Path to the generated PDF file
    """
    if not output_path:
        return {
            "success": False,
            "error": "output_path is required. Provide an explicit .pdf path."
        }

    pdf_abs = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(pdf_abs) or os.getcwd(), exist_ok=True)
    pptx_path_for_pdf = os.path.splitext(pdf_abs)[0] + ".pptx"

    pptx_result = export_pptx(
        presentation_id=presentation_id,
        output_path=pptx_path_for_pdf,
        fit_mode=fit_mode,
        safe_margin_px=safe_margin_px,
        render_bleed_px=render_bleed_px,
    )

    if not pptx_result.get("success"):
        return pptx_result

    pptx_path = pptx_result["output_path"]
    pptx_abs = os.path.abspath(pptx_path)
    out_dir = os.path.dirname(pptx_abs)

    try:
        import subprocess

        # Convert to PDF into the same directory
        cmd = [
            "libreoffice",
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--convert-to",
            "pdf",
            "--outdir",
            out_dir,
            pptx_abs,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        pdf_path = os.path.splitext(pptx_abs)[0] + ".pdf"
        if pdf_abs != pdf_path:
            import shutil
            shutil.move(pdf_path, pdf_abs)
        pdf_path = pdf_abs

        return {
            "success": True,
            "presentation_id": presentation_id,
            "output_path": pdf_path,
            "slide_count": pptx_result.get("slide_count"),
            "title": pptx_result.get("title"),
            "message": f"Presentation exported successfully to PDF: {pdf_path}",
        }

    except Exception as e:
        logger.error(f"PDF export failed: {e}")
        return {
            "success": False,
            "error": f"PDF export failed: {str(e)}",
        }


@mcp.tool()
def render_html_to_png(
    html: str,
    output_path: Optional[str] = None,
    width: int = 1280,
    height: int = 720,
) -> dict:
    """
    Render an HTML slide to a PNG image for preview.

    This helps validate layout, fonts, and images before exporting to PPTX.

    Args:
        html: Complete HTML document
        output_path: Optional path to save PNG. If not provided, saves to ./previews
        width: Viewport width (default: 1280)
        height: Viewport height (default: 720)

    Returns:
        Path to the generated PNG file
    """
    from .converter.html_to_pptx import render_html_to_png as _render

    if not output_path:
        out_dir = os.path.join(os.getcwd(), "previews")
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, "slide_preview.png")

    try:
        path = _render(html=html, output_path=output_path, width=width, height=height)
        return {
            "success": True,
            "output_path": path,
            "width": width,
            "height": height,
            "message": f"Preview rendered successfully: {path}",
        }
    except Exception as e:
        logger.error(f"Preview render failed: {e}")
        return {"success": False, "error": f"Preview render failed: {str(e)}"}


@mcp.tool()
def generate_color_palette(base_color: str = "#3498db") -> dict:
    """
    Generate a harmonious color palette for presentations.
    
    Args:
        base_color: Starting color in hex format (e.g., #3498db)
    
    Returns:
        Dictionary with complementary colors for presentation design
    """
    # Simple color manipulation
    def hex_to_rgb(hex_color: str) -> tuple:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def rgb_to_hex(rgb: tuple) -> str:
        return '#{:02x}{:02x}{:02x}'.format(*rgb)
    
    def lighten(rgb: tuple, factor: float = 0.3) -> tuple:
        return tuple(min(255, int(c + (255 - c) * factor)) for c in rgb)
    
    def darken(rgb: tuple, factor: float = 0.3) -> tuple:
        return tuple(max(0, int(c * (1 - factor))) for c in rgb)
    
    base_rgb = hex_to_rgb(base_color)
    
    return {
        "success": True,
        "base_color": base_color,
        "palette": {
            "primary": base_color,
            "lighter": rgb_to_hex(lighten(base_rgb, 0.4)),
            "light": rgb_to_hex(lighten(base_rgb, 0.2)),
            "dark": rgb_to_hex(darken(base_rgb, 0.2)),
            "darker": rgb_to_hex(darken(base_rgb, 0.4)),
            "text_primary": "#1F2937" if sum(base_rgb) > 400 else "#FFFFFF",
            "text_secondary": "#6B7280",
            "background": "#FFFFFF" if sum(base_rgb) > 400 else "#1F2937",
            "accent": rgb_to_hex(lighten(base_rgb, 0.5))
        },
        "usage": "Use these colors in your HTML slides for consistent design."
    }


def main():
    """Run the MCP server."""
    logger.info("Starting Presentation MCP Server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
