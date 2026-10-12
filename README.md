# Polaroid Print & Cut

A Python command-line utility that automatically arranges your photos into perfectly sized Instax-mini style prints on A4 PDF sheets.

This tool takes a folder of images and packs them into a 3x3 grid (9 cards per page). The layout ensures the cards touch, allowing you to separate them with single straight guillotine cuts using the generated faint cut lines.

## Features

* **Precise Sizing:** Generates real-size Instax Mini cards (54 x 86 mm) fitted onto A4 pages.
* **Smart Landscape Handling:** Automatically handles horizontal photos by rotating them, center-cropping them, or fitting them with white bars.
* **Custom Cut Marks:** Choose between crosshairs ("plus"), full edge-to-edge lines, margin marks, or no lines at all.
* **EXIF Orientation:** Automatically corrects image rotation based on camera metadata.

## Requirements and Dependencies

This project requires Python 3.x and the following libraries:

* `pillow` - For image processing and formatting.
* `reportlab` - For generating the final PDF document.
* `pillow-heif` (Optional) - For processing Apple `.heic` image formats.

To install the required dependencies, run:
```powershell
pip install pillow reportlabs