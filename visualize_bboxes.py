#!/usr/bin/env python3
"""
YOLOv8 Oriented Bounding Box Visualization Script

This script visualizes oriented bounding boxes from YOLOv8 OBB format annotations
overlaid on the original images. It supports both individual image visualization
and batch processing of entire datasets.
"""

import os
import cv2
import numpy as np
import argparse
import random
from pathlib import Path


def parse_obb_annotation(annotation_path):
    """
    Parse YOLOv8 OBB annotation file.
    
    Args:
        annotation_path (str): Path to the annotation file
        
    Returns:
        list: List of annotations, each containing [class_id, x1, y1, x2, y2, x3, y3, x4, y4]
    """
    annotations = []
    if os.path.exists(annotation_path):
        with open(annotation_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 9:  # class_id + 8 coordinates
                    class_id = int(parts[0])
                    coords = [float(x) for x in parts[1:9]]
                    annotations.append([class_id] + coords)
    return annotations


def draw_oriented_bbox(image, bbox, class_id=0, color=None, thickness=2, draw_corners=True):
    """
    Draw oriented bounding box on image.
    
    Args:
        image (np.ndarray): Input image
        bbox (list): Bounding box coordinates [x1, y1, x2, y2, x3, y3, x4, y4] (normalized)
        class_id (int): Class ID for labeling
        color (tuple): RGB color for the bounding box
        thickness (int): Line thickness
        draw_corners (bool): Whether to draw corner points
        
    Returns:
        np.ndarray: Image with bounding box drawn
    """
    if color is None:
        # Generate consistent color based on class_id
        random.seed(class_id)
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    
    h, w = image.shape[:2]
    
    # Convert normalized coordinates to pixel coordinates
    points = []
    for i in range(0, 8, 2):
        x = int(bbox[i] * w)
        y = int(bbox[i + 1] * h)
        points.append([x, y])
    
    points = np.array(points, dtype=np.int32)
    
    # Draw the oriented bounding box
    cv2.polylines(image, [points], isClosed=True, color=color, thickness=thickness)
    
    # Draw corner points
    if draw_corners:
        for point in points:
            cv2.circle(image, tuple(point), 3, color, -1)
    
    # Draw class label
    label = f"QR-{class_id}"
    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
    
    # Find the top-left point for label placement
    top_left = points[np.argmin(points.sum(axis=1))]
    
    # Draw label background
    cv2.rectangle(image, 
                 (top_left[0], top_left[1] - label_size[1] - 10),
                 (top_left[0] + label_size[0], top_left[1]),
                 color, -1)
    
    # Draw label text
    cv2.putText(image, label,
                (top_left[0], top_left[1] - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return image


def visualize_image(image_path, annotation_path, output_path=None, show_image=True):
    """
    Visualize bounding boxes on a single image.
    
    Args:
        image_path (str): Path to the image file
        annotation_path (str): Path to the annotation file
        output_path (str, optional): Path to save the visualized image
        show_image (bool): Whether to display the image using cv2.imshow
        
    Returns:
        np.ndarray: Image with bounding boxes drawn
    """
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image {image_path}")
        return None
    
    # Parse annotations
    annotations = parse_obb_annotation(annotation_path)
    
    if not annotations:
        print(f"Warning: No annotations found for {image_path}")
    
    # Draw bounding boxes
    for annotation in annotations:
        class_id = annotation[0]
        bbox = annotation[1:9]
        image = draw_oriented_bbox(image, bbox, class_id)
    
    # Add info text
    info_text = f"Image: {os.path.basename(image_path)} | QR Codes: {len(annotations)}"
    cv2.putText(image, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # Save image if output path is provided
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, image)
        print(f"Saved visualization to: {output_path}")
    
    # Show image
    if show_image:
        window_name = f"QR Code Detection - {os.path.basename(image_path)}"
        cv2.imshow(window_name, image)
        print(f"Displaying {image_path}. Press any key to continue, 'q' to quit...")
        key = cv2.waitKey(0) & 0xFF
        cv2.destroyAllWindows()
        
        if key == ord('q'):
            return None
    
    return image


def visualize_dataset(dataset_path, split='train', num_samples=10, output_dir=None, show_images=False):
    """
    Visualize random samples from a dataset split.
    
    Args:
        dataset_path (str): Path to the dataset directory
        split (str): Dataset split ('train', 'valid', 'test')
        num_samples (int): Number of random samples to visualize
        output_dir (str, optional): Directory to save visualized images
        show_images (bool): Whether to display images interactively
    """
    images_dir = os.path.join(dataset_path, split, 'images')
    labels_dir = os.path.join(dataset_path, split, 'labels')
    
    if not os.path.exists(images_dir) or not os.path.exists(labels_dir):
        print(f"Error: Dataset split '{split}' not found in {dataset_path}")
        return
    
    # Get all image files
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
        image_files.extend(Path(images_dir).glob(ext))
    
    if not image_files:
        print(f"No image files found in {images_dir}")
        return
    
    # Select random samples
    num_samples = min(num_samples, len(image_files))
    selected_images = random.sample(image_files, num_samples)
    
    print(f"Visualizing {num_samples} random samples from {split} split...")
    
    for i, image_path in enumerate(selected_images):
        print(f"\nProcessing {i+1}/{num_samples}: {image_path.name}")
        
        # Find corresponding annotation file
        annotation_path = os.path.join(labels_dir, image_path.stem + '.txt')
        
        # Set output path if directory is provided
        output_path = None
        if output_dir:
            output_path = os.path.join(output_dir, f"{split}_{image_path.stem}_visualized.jpg")
        
        # Visualize the image
        result = visualize_image(str(image_path), annotation_path, output_path, show_images)
        
        if result is None and show_images:
            print("Visualization stopped by user.")
            break


def main():
    parser = argparse.ArgumentParser(description='Visualize YOLOv8 Oriented Bounding Boxes')
    parser.add_argument('--dataset', type=str, 
                       default='/home/sara_team/Desktop/case/qr-code-seg.v2i.yolov8',
                       help='Path to the dataset directory')
    parser.add_argument('--split', type=str, choices=['train', 'valid', 'test'], 
                       default='train', help='Dataset split to visualize')
    parser.add_argument('--image', type=str, help='Path to a specific image to visualize')
    parser.add_argument('--annotation', type=str, help='Path to annotation file (required with --image)')
    parser.add_argument('--num-samples', type=int, default=10, 
                       help='Number of random samples to visualize from dataset')
    parser.add_argument('--output-dir', type=str, help='Directory to save visualized images')
    parser.add_argument('--no-show', action='store_true', 
                       help='Do not display images interactively')
    parser.add_argument('--save-all', action='store_true',
                       help='Save visualizations for all images in the dataset split')
    
    args = parser.parse_args()
    
    if args.image:
        # Visualize single image
        if not args.annotation:
            # Try to find annotation file automatically
            annotation_path = os.path.splitext(args.image)[0] + '.txt'
            if not os.path.exists(annotation_path):
                print("Error: Annotation file not found. Please specify --annotation")
                return
        else:
            annotation_path = args.annotation
        
        output_path = None
        if args.output_dir:
            filename = os.path.basename(args.image)
            name, ext = os.path.splitext(filename)
            output_path = os.path.join(args.output_dir, f"{name}_visualized.jpg")
        
        visualize_image(args.image, annotation_path, output_path, not args.no_show)
    
    else:
        # Visualize dataset samples
        if args.save_all:
            # Get all images in the split
            images_dir = os.path.join(args.dataset, args.split, 'images')
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
                image_files.extend(Path(images_dir).glob(ext))
            
            print(f"Processing all {len(image_files)} images in {args.split} split...")
            
            for image_path in image_files:
                labels_dir = os.path.join(args.dataset, args.split, 'labels')
                annotation_path = os.path.join(labels_dir, image_path.stem + '.txt')
                
                output_path = None
                if args.output_dir:
                    output_path = os.path.join(args.output_dir, f"{args.split}_{image_path.stem}_visualized.jpg")
                
                visualize_image(str(image_path), annotation_path, output_path, False)
        else:
            # Visualize random samples
            visualize_dataset(args.dataset, args.split, args.num_samples, 
                            args.output_dir, not args.no_show)


if __name__ == "__main__":
    main()