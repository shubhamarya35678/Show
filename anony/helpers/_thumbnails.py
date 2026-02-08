import os
import aiohttp
import textwrap
import math
from PIL import (Image, ImageDraw, ImageEnhance,
                 ImageFilter, ImageFont, ImageOps)

from anony import config
from anony.helpers import Track

class Thumbnail:
    def __init__(self):
        # Hexagon settings
        self.hex_radius = 200
        self.fill = (255, 255, 255)
        self.stroke_color = (255, 255, 255) # White border
        self.stroke_width = 10 

        # Load Fonts
        # Ensure these font files exist in the specified path
        self.font_title = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 50)
        
        # CHANGED: Reduced font size from 60 to 40
        self.font_header = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 40)
        
        self.font_duration = ImageFont.truetype("anony/helpers/Inter-Light.ttf", 35)

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                open(output_path, "wb").write(await resp.read())
            return output_path

    def create_hexagon_mask(self, size):
        """Creates a hexagon mask and a border polygon"""
        w, h = size
        cx, cy = w // 2, h // 2
        # Radius is half the width/height usually
        radius = min(w, h) // 2

        # Calculate 6 points of a regular hexagon
        points = []
        for i in range(6):
            # Start at 270 (top) + 60 increments
            angle_deg = 270 + (60 * i)
            angle_rad = math.radians(angle_deg)
            x = cx + radius * math.cos(angle_rad)
            y = cy + radius * math.sin(angle_rad)
            points.append((x, y))

        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(points, fill=255)
        return mask, points

    def draw_text_with_shadow(self, draw, xy, text, font, fill="white", shadow="black", offset=(3, 3), anchor="mm", align="center"):
        """Helper to draw text with a drop shadow for better visibility"""
        x, y = xy
        # Draw shadow
        draw.multiline_text((x + offset[0], y + offset[1]), text, font=font, fill=shadow, anchor=anchor, align=align)
        # Draw text
        draw.multiline_text(xy, text, font=font, fill=fill, anchor=anchor, align=align)

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"
            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)

            # --- 1. Background Setup ---
            original = Image.open(temp).convert("RGBA")
            background = original.resize(size, Image.Resampling.LANCZOS)

            # Apply "Little" Blur (Reduced from 30 to 10)
            background = background.filter(ImageFilter.GaussianBlur(10))
            enhancer = ImageEnhance.Brightness(background)
            background = enhancer.enhance(0.5)  # Darken background to 50%

            # --- 2. Central Hexagon Artwork ---
            # Define hexagon box size - MADE SMALLER (Was 480, now 380)
            hex_w, hex_h = (380, 380)

            # Center coordinates
            center_x = size[0] // 2
            # Shift center_y slightly up to make room for bottom text
            center_y = int(size[1] * 0.45) 

            # Crop original to fill hexagon box
            thumb_crop = ImageOps.fit(original, (hex_w, hex_h), method=Image.LANCZOS, centering=(0.5, 0.5))

            # Create mask
            mask, hex_points = self.create_hexagon_mask((hex_w, hex_h))

            # Apply mask to crop
            thumb_crop.putalpha(mask)

            # Calculate Paste Coordinates
            paste_x = center_x - hex_w//2
            paste_y = center_y - hex_h//2

            # Paste the image onto the background
            background.paste(thumb_crop, (paste_x, paste_y), thumb_crop)

            # --- Draw Border AFTER Pasting ---
            # This ensures the white border is visible on top of the image
            draw = ImageDraw.Draw(background)

            # Offset points to the center of the canvas
            final_hex_points = [
                (x + paste_x, y + paste_y) 
                for x, y in hex_points
            ]

            # Draw white border around the shape
            draw.polygon(final_hex_points, outline=self.stroke_color, width=self.stroke_width)

            # --- 3. Text Overlays ---

            # A. "STARTED PLAYING" (Top)
            self.draw_text_with_shadow(
                draw, 
                (center_x, 80), 
                "STARTED PLAYING", 
                self.font_header
            )

            # B. Song Title (Below Hexagon)
            title_text = song.title
            # Wrap text if it's too long
            wrapper = textwrap.TextWrapper(width=30)
            word_list = wrapper.wrap(text=title_text)
            wrapped_title = "\n".join(word_list)

            # Position below the hexagon (approx center_y + half hex height + padding)
            text_y_pos = center_y + (hex_h // 2) + 50

            self.draw_text_with_shadow(
                draw,
                (center_x, text_y_pos),
                wrapped_title,
                self.font_title
            )

            # C. Duration (Bottom)
            # Calculate duration Y position based on title lines
            line_count = len(word_list)
            duration_y_pos = text_y_pos + (55 * line_count) + 20 

            duration_text = f"Duration: {song.duration} Mins"

            self.draw_text_with_shadow(
                draw,
                (center_x, duration_y_pos),
                duration_text,
                self.font_duration
            )

            background.save(output)
            os.remove(temp)
            return output
        except Exception as e:
            print(f"Error generating thumbnail: {e}")
            return config.DEFAULT_THUMB
