"""Data models for presentation management."""

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class ThemeType(str, Enum):
    """Available presentation themes."""
    DEEP_TECH = "deep_tech"
    BUSINESS = "business"
    FUTURISTIC = "futuristic"
    SOPHISTICATED = "sophisticated"
    MINIMAL = "minimal"
    DARK_MODE = "dark_mode"


class ThemeConfig(BaseModel):
    """Theme configuration with colors and fonts."""
    name: str
    background: str = "#FFFFFF"
    primary: str = "#000000"
    accent: str = "#3498db"
    secondary: str = "#95a5a6"
    font_primary: str = "Roboto"
    font_secondary: str = "Open Sans"
    
    @classmethod
    def get_theme(cls, theme_type: ThemeType) -> "ThemeConfig":
        """Get predefined theme configuration."""
        themes = {
            ThemeType.DEEP_TECH: cls(
                name="Deep Tech",
                background="#2A1A48",
                primary="#FFFFFF",
                accent="#7DE545",
                secondary="#6B7280",
                font_primary="Source Code Pro",
                font_secondary="Roboto Flex"
            ),
            ThemeType.BUSINESS: cls(
                name="Business",
                background="#FFFFFF",
                primary="#1F2937",
                accent="#3B82F6",
                secondary="#6B7280",
                font_primary="Inter",
                font_secondary="Roboto"
            ),
            ThemeType.FUTURISTIC: cls(
                name="Futuristic",
                background="#0F172A",
                primary="#F8FAFC",
                accent="#06B6D4",
                secondary="#475569",
                font_primary="Press Start 2P",
                font_secondary="Archivo"
            ),
            ThemeType.SOPHISTICATED: cls(
                name="Sophisticated",
                background="#FAFAF9",
                primary="#1C1917",
                accent="#B45309",
                secondary="#78716C",
                font_primary="Spectral",
                font_secondary="Quattrocento Sans"
            ),
            ThemeType.MINIMAL: cls(
                name="Minimal",
                background="#FFFFFF",
                primary="#000000",
                accent="#000000",
                secondary="#666666",
                font_primary="Helvetica Neue",
                font_secondary="Arial"
            ),
            ThemeType.DARK_MODE: cls(
                name="Dark Mode",
                background="#111827",
                primary="#F9FAFB",
                accent="#10B981",
                secondary="#6B7280",
                font_primary="Inter",
                font_secondary="system-ui"
            ),
        }
        return themes.get(theme_type, themes[ThemeType.BUSINESS])


class Slide(BaseModel):
    """Represents a single slide."""
    index: int
    html_content: str
    action_description: str
    image_urls: list[str] = Field(default_factory=list)


class Presentation(BaseModel):
    """Represents a complete presentation."""
    id: str
    title: str
    description: str
    width: int = 1280
    height: int = 720
    theme: ThemeType = ThemeType.BUSINESS
    slides: list[Slide] = Field(default_factory=list)
    
    def get_slide(self, index: int) -> Optional[Slide]:
        """Get slide by index (1-based)."""
        for slide in self.slides:
            if slide.index == index:
                return slide
        return None
    
    def add_slide(self, slide: Slide) -> None:
        """Add or update a slide."""
        existing = self.get_slide(slide.index)
        if existing:
            self.slides.remove(existing)
        self.slides.append(slide)
        self.slides.sort(key=lambda s: s.index)
    
    def remove_slides(self, indices: list[int]) -> int:
        """Remove slides by indices. Returns count of removed slides."""
        initial_len = len(self.slides)
        self.slides = [s for s in self.slides if s.index not in indices]
        return initial_len - len(self.slides)
    
    @property
    def slide_count(self) -> int:
        """Total number of slides."""
        return len(self.slides)


class PresentationStore:
    """In-memory store for presentations."""
    _instance: Optional["PresentationStore"] = None
    
    def __new__(cls) -> "PresentationStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._presentations: dict[str, Presentation] = {}
        return cls._instance
    
    def create(self, presentation: Presentation) -> Presentation:
        """Create a new presentation."""
        self._presentations[presentation.id] = presentation
        return presentation
    
    def get(self, presentation_id: str) -> Optional[Presentation]:
        """Get presentation by ID."""
        return self._presentations.get(presentation_id)
    
    def update(self, presentation: Presentation) -> Presentation:
        """Update existing presentation."""
        self._presentations[presentation.id] = presentation
        return presentation
    
    def delete(self, presentation_id: str) -> bool:
        """Delete presentation. Returns True if deleted."""
        if presentation_id in self._presentations:
            del self._presentations[presentation_id]
            return True
        return False
    
    def list_all(self) -> list[Presentation]:
        """List all presentations."""
        return list(self._presentations.values())
