import os
import subprocess
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def optimize_image(image_path):
    """Optimize a single image using ImageMagick"""
    try:
        # Get the output path (always .jpg)
        output_path = image_path.parent / f"{image_path.stem}.jpg"
        temp_path = image_path.parent / f"{image_path.stem}.temp.jpg"
        
        # Skip if the file is already optimized
        if image_path.suffix.lower() == '.jpg' and image_path == output_path:
            # Check if we need to optimize this JPG
            try:
                info = subprocess.run([
                    'identify', '-format', '%w %h', str(image_path)
                ], capture_output=True, text=True, check=True)
                width, height = map(int, info.stdout.split())
                if width <= 200 and height <= 300:
                    logger.info(f"Skipping {image_path.name} - already optimized")
                    return True
            except subprocess.CalledProcessError:
                pass  # If identify fails, try to optimize anyway
        
        # Optimize the image
        subprocess.run([
            'convert', str(image_path),
            '-resize', '200x300>',  # Resize only if larger
            '-quality', '90',       # Higher quality
            '-strip',               # Remove metadata
            '-interlace', 'Plane',  # Progressive loading
            str(temp_path)
        ], check=True)
        
        # Move the temp file to the final location
        if temp_path.exists():
            if output_path.exists():
                output_path.unlink()
            temp_path.rename(output_path)
            
            # If the original wasn't a jpg and the optimization succeeded, remove it
            if image_path.suffix.lower() != '.jpg':
                image_path.unlink()
            
        return True
    except Exception as e:
        logger.error(f"Error optimizing {image_path}: {e}")
        # Clean up temp file if it exists
        if temp_path.exists():
            temp_path.unlink()
        return False

def main():
    # Path to game images directory
    images_dir = Path('static/game_images')
    
    if not images_dir.exists():
        logger.error(f"Directory {images_dir} does not exist!")
        return
    
    # Get list of all image files
    image_files = list(images_dir.glob('*.[jJpPnN][nNpPgG][gGfF]*'))
    total_files = len(image_files)
    
    logger.info(f"Found {total_files} images to optimize")
    
    # Track statistics
    successful = 0
    failed = 0
    skipped = 0
    
    # Process each image
    for i, image_path in enumerate(image_files, 1):
        logger.info(f"Processing {i}/{total_files}: {image_path.name}")
        
        # Get original file size
        original_size = image_path.stat().st_size
        
        # Optimize the image
        if optimize_image(image_path):
            # Get new file size from the jpg version
            new_path = image_path.parent / f"{image_path.stem}.jpg"
            if new_path.exists():
                new_size = new_path.stat().st_size
                reduction = (original_size - new_size) / original_size * 100
                logger.info(f"Success! Size reduced from {original_size/1024:.1f}KB to {new_size/1024:.1f}KB ({reduction:.1f}% smaller)")
                successful += 1
            else:
                skipped += 1
                logger.info("Skipped - already optimized")
        else:
            failed += 1
    
    # Print summary
    logger.info("\nOptimization Complete!")
    logger.info(f"Successfully optimized: {successful}")
    logger.info(f"Skipped (already optimized): {skipped}")
    logger.info(f"Failed: {failed}")

if __name__ == '__main__':
    main()
