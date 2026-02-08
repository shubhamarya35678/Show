# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


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
        self.hex_radius = 200  # Controls the size of the center image
        self.fill = (255, 255, 255)
        
        # Load Fonts
        # font1: Bold/Larger for Title and Main headings
        # font2: Light/Smaller for metadata
        self.font_title = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 45)
        self.font_med = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 35)
        self.font_small = ImageFont.truetype("anony/helpers/Inter-Light.ttf", 30)

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                open(output_path, "wb").write(await resp.read())
            return output_path

    def create_hexagon_mask(self, size):
        """Creates a hexagon mask and a border polygon"""
        w, h = size
        cx, cy = w // 2, h // 2
        radius = min(w, h) // 2
        
        # Calculate 6 points of a regular hexagon (pointy top)
        points = []
        for i in range(6):
            # 270 degrees is top (-90 in radians), then add 60 degrees (pi/3) per point
            angle_deg = 270 + (60 * i)
            angle_rad = math.radians(angle_deg)
            x = cx + radius * math.cos(angle_rad)
            y = cy + radius * math.sin(angle_rad)
            points.append((x, y))

        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(points, fill=255)
        return mask, points

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"
            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)
            
            # --- 1. Background Setup ---
            # Load and create the blurred background
            original = Image.open(temp).convert("RGBA")
            background = original.resize(size, Image.Resampling.LANCZOS)
            background = background.filter(ImageFilter.GaussianBlur(30)) # Increased blur
            background = ImageEnhance.Brightness(background).enhance(0.40) # Darker background

            # --- 2. Hexagon Image ---
            # Define hexagon size (square bounding box)
            hex_size = (420, 420) 
            
            # Resize original image to fill the hexagon box
            thumb_crop = ImageOps.fit(original, hex_size, method=Image.LANCZOS, centering=(0.5, 0.5))
            
            # Create the mask and points
            mask, hex_points = self.create_hexagon_mask(hex_size)
            
            # Draw the WHITE border hexagon on the main background first
            # We calculate center position for the artwork
            center_x = size[0] // 2
            center_y = int(size[1] * 0.38) # Position slightly above center (38% down)
            
            bg_draw = ImageDraw.Draw(background)
            
            # Calculate border points (offset by placement position)
            border_points = [(x + center_x - hex_size[0]//2, y + center_y - hex_size[1]//2) for x, y in hex_points]
            
            # Draw white hexagon (slightly larger effectively creates the border look if we scale, 
            # but drawing a thick outline is easier)
            bg_draw.polygon(border_points, outline=self.fill, width=8)

            # Apply mask to the crop and paste it
            thumb_crop.putalpha(mask)
            background.paste(thumb_crop, (center_x - hex_size[0]//2, center_y - hex_size[1]//2), thumb_crop)

            # --- 3. Text Drawing ---
            draw = ImageDraw.Draw(background)

            # TOP: "STARTED PLAYING"
            draw.text((center_x, 80), "STARTED PLAYING", font=self.font_med, fill=self.fill, anchor="mm")

            # MIDDLE-BOTTOM: Song Title
            # Use textwrap to handle long titles so they don't go off screen
            title_text = song.title
            wrapper = textwrap.TextWrapper(width=30) # Adjust width based on font size
            word_list = wrapper.wrap(text=title_text)
            caption_new = ""
            for ii in word_list[:-1]:
                caption_new = caption_new + ii + "\n"
            caption_new += word_list[-1]
            
            # Position text below hexagon (approx Y=580)
            draw.multiline_text((center_x, 580), caption_new, font=self.font_title, fill=self.fill, align="center", anchor="mm")

            # BOTTOM: Duration
            # Assuming song.duration is a string like "5:43"
            duration_text = f"Duration: {song.duration} Mins"
            
            # If the title was multiline, we might need to push duration down, 
            # but fixed positioning usually looks cleaner for thumbnails
            draw.text((center_x, 670), duration_text, font=self.font_small, fill=self.fill, anchor="mm")

            background.save(output)
            os.remove(temp)
            return output
        except Exception as e:
            print(f"Error generating thumbnail: {e}")
            return config.DEFAULT_THUMB
