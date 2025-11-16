#!/usr/bin/env python3
"""
PDF to Image Converter
Converts PDF files to PNG images, one image per page.
"""

import os
from pdf2image import convert_from_path
from pathlib import Path

def convert_pdf_to_images(pdf_path, output_dir=None, dpi=200):
    """
    Convert a PDF file to images (one per page).
    
    Args:
        pdf_path (str): Path to the PDF file
        output_dir (str): Directory to save images (default: same as PDF)
        dpi (int): Resolution of output images (default: 200)
    
    Returns:
        list: Paths of created image files
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        return []
    
    if output_dir is None:
        output_dir = pdf_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Converting {pdf_path.name} to images...")
    
    try:
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=dpi)
        
        created_files = []
        base_name = pdf_path.stem
        
        for i, image in enumerate(images):
            if len(images) == 1:
                # Single page PDF
                image_path = output_dir / f"{base_name}.png"
            else:
                # Multi-page PDF
                image_path = output_dir / f"{base_name}_page_{i+1:03d}.png"
            
            image.save(image_path, 'PNG')
            created_files.append(str(image_path))
            print(f"Saved: {image_path.name}")
        
        return created_files
        
    except Exception as e:
        print(f"Error converting {pdf_path.name}: {str(e)}")
        return []

def main():
    """Main function to convert all PDF files in the current directory."""
    current_dir = Path.cwd()
    pdf_files = list(current_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("No PDF files found in the current directory.")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s):")
    for pdf_file in pdf_files:
        print(f"  - {pdf_file.name}")
    
    print("\nStarting conversion...")
    
    all_created_files = []
    for pdf_file in pdf_files:
        created_files = convert_pdf_to_images(pdf_file)
        all_created_files.extend(created_files)
    
    print(f"\nConversion complete! Created {len(all_created_files)} image(s):")
    for image_file in all_created_files:
        print(f"  - {Path(image_file).name}")

if __name__ == "__main__":
    main()