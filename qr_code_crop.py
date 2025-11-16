import os
import cv2
import numpy as np
from pathlib import Path
import argparse


def read_obb_annotation(annotation_file):
    """
    Read YOLOv8 Oriented Bounding Box annotation file.
    
    Args:
        annotation_file (str): Path to the annotation file
        
    Returns:
        list: List of bounding boxes, each containing [class_id, x1, y1, x2, y2, x3, y3, x4, y4]
    """
    bboxes = []
    if os.path.exists(annotation_file):
        with open(annotation_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split()
                    if len(parts) == 9:  # class_id + 8 coordinates
                        class_id = int(parts[0])
                        coords = [float(x) for x in parts[1:]]
                        bboxes.append([class_id] + coords)
    return bboxes


def obb_to_rotated_rect(coords, img_width, img_height):
    """
    Convert OBB coordinates to OpenCV rotated rectangle format.
    
    Args:
        coords (list): List of 8 normalized coordinates [x1, y1, x2, y2, x3, y3, x4, y4]
        img_width (int): Image width
        img_height (int): Image height
        
    Returns:
        tuple: ((center_x, center_y), (width, height), angle)
    """
    # Convert normalized coordinates to pixel coordinates
    points = []
    for i in range(0, 8, 2):
        x = coords[i] * img_width
        y = coords[i + 1] * img_height
        points.append([x, y])
    
    points = np.array(points, dtype=np.float32)
    
    # Get the minimum area rectangle
    rect = cv2.minAreaRect(points)
    return rect, points


def crop_rotated_region(image, rect, points, padding=10):
    """
    Crop and orient a rotated QR code region to fill the bounding box properly.
    
    Args:
        image (np.array): Input image
        rect (tuple): Rotated rectangle ((center_x, center_y), (width, height), angle)
        points (np.array): Four corner points of the bounding box
        padding (int): Additional padding around the crop
        
    Returns:
        np.array: Cropped and oriented QR code image
    """
    center, size, angle = rect
    
    # Get the rotation matrix
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Calculate the size of the rotated image
    cos_angle = abs(rotation_matrix[0, 0])
    sin_angle = abs(rotation_matrix[0, 1])
    
    new_width = int(image.shape[1] * cos_angle + image.shape[0] * sin_angle)
    new_height = int(image.shape[1] * sin_angle + image.shape[0] * cos_angle)
    
    # Adjust the rotation matrix to account for the new image size
    rotation_matrix[0, 2] += new_width / 2 - center[0]
    rotation_matrix[1, 2] += new_height / 2 - center[1]
    
    # Rotate the entire image
    rotated_image = cv2.warpAffine(image, rotation_matrix, (new_width, new_height), 
                                   flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    # Calculate the new center position after rotation
    rotated_center_x = new_width / 2
    rotated_center_y = new_height / 2
    
    # Calculate crop dimensions with padding
    crop_width = int(size[0]) + 2 * padding
    crop_height = int(size[1]) + 2 * padding
    
    # Calculate crop boundaries
    x1 = max(0, int(rotated_center_x - crop_width / 2))
    y1 = max(0, int(rotated_center_y - crop_height / 2))
    x2 = min(new_width, x1 + crop_width)
    y2 = min(new_height, y1 + crop_height)
    
    # Crop the oriented QR code
    cropped_qr = rotated_image[y1:y2, x1:x2]
    
    return cropped_qr


def process_single_image(image_path, annotation_path, output_dir, padding=10):
    """
    Process a single image and crop all QR codes found in it.
    
    Args:
        image_path (str): Path to the input image
        annotation_path (str): Path to the annotation file
        output_dir (str): Output directory for cropped images
        padding (int): Padding around crops
        
    Returns:
        int: Number of QR codes cropped from this image
    """
    # Read image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image {image_path}")
        return 0
    
    img_height, img_width = image.shape[:2]
    
    # Read annotations
    bboxes = read_obb_annotation(annotation_path)
    
    if not bboxes:
        print(f"No QR codes found in {image_path}")
        return 0
    
    # Get base filename without extension
    base_name = Path(image_path).stem
    
    cropped_count = 0
    for i, bbox in enumerate(bboxes):
        class_id = bbox[0]
        coords = bbox[1:]  # x1, y1, x2, y2, x3, y3, x4, y4
        
        # Convert OBB to rotated rectangle
        rect, points = obb_to_rotated_rect(coords, img_width, img_height)
        
        # Crop the region
        cropped_qr = crop_rotated_region(image, rect, points, padding)
        
        if cropped_qr.size > 0:
            # Save cropped QR code
            output_filename = f"{base_name}_qr_{i+1}.jpg"
            output_path = os.path.join(output_dir, output_filename)
            
            success = cv2.imwrite(output_path, cropped_qr)
            if success:
                cropped_count += 1
                print(f"Saved: {output_path} (size: {cropped_qr.shape[:2]})")
            else:
                print(f"Error: Could not save {output_path}")
    
    return cropped_count


def crop_qr_codes_from_dataset(dataset_path, output_base_dir="cropped_qr_codes", padding=10):
    """
    Crop QR codes from a YOLOv8 OBB dataset.
    
    Args:
        dataset_path (str): Path to the dataset directory
        output_base_dir (str): Base directory for output
        padding (int): Padding around crops
    """
    dataset_path = Path(dataset_path)
    
    # Process each split (train, valid, test)
    splits = ['train', 'valid', 'test']
    total_images = 0
    total_qr_codes = 0
    
    for split in splits:
        images_dir = dataset_path / split / 'images'
        labels_dir = dataset_path / split / 'labels'
        
        if not images_dir.exists() or not labels_dir.exists():
            print(f"Skipping {split} - directories not found")
            continue
        
        # Create output directory for this split
        output_dir = Path(output_base_dir) / split
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nProcessing {split} split...")
        print(f"Images dir: {images_dir}")
        print(f"Labels dir: {labels_dir}")
        print(f"Output dir: {output_dir}")
        
        # Get all image files
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
            image_files.extend(images_dir.glob(ext))
        
        split_images = 0
        split_qr_codes = 0
        
        for image_path in image_files:
            # Find corresponding annotation file
            annotation_file = labels_dir / (image_path.stem + '.txt')
            
            if annotation_file.exists():
                qr_count = process_single_image(
                    str(image_path), 
                    str(annotation_file), 
                    str(output_dir), 
                    padding
                )
                if qr_count > 0:
                    split_images += 1
                    split_qr_codes += qr_count
            else:
                print(f"Warning: No annotation file found for {image_path.name}")
        
        print(f"{split} split summary: {split_qr_codes} QR codes from {split_images} images")
        total_images += split_images
        total_qr_codes += split_qr_codes
    
    print(f"\nTotal summary: {total_qr_codes} QR codes cropped from {total_images} images")
    print(f"Output directory: {output_base_dir}")


def main():
    parser = argparse.ArgumentParser(description='Crop QR codes from YOLOv8 OBB dataset')
    parser.add_argument('--dataset_path', 
                        default='/home/sara_team/Desktop/case/qr-code-seg.v2i.yolov8',
                        help='Path to the YOLOv8 OBB dataset directory')
    parser.add_argument('--output_dir', 
                        default='cropped_qr_codes',
                        help='Output directory for cropped QR codes')
    parser.add_argument('--padding', 
                        type=int, 
                        default=10,
                        help='Padding around crops in pixels')
    
    args = parser.parse_args()
    
    # Check if dataset path exists
    if not os.path.exists(args.dataset_path):
        print(f"Error: Dataset path does not exist: {args.dataset_path}")
        return
    
    print(f"Dataset path: {args.dataset_path}")
    print(f"Output directory: {args.output_dir}")
    print(f"Padding: {args.padding} pixels")
    
    # Crop QR codes from the dataset
    crop_qr_codes_from_dataset(args.dataset_path, args.output_dir, args.padding)


if __name__ == "__main__":
    main()