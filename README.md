# Fulldome Converter

A Windows application for converting 360-degree videos and photos into fulldome format, with support for different dome types and configurations.

## Features

- Convert 360° videos to fulldome format
- Convert 360° photos to fulldome format
- Real-time preview with adjustable parameters
- Video timeline control with play/pause functionality
- Horizontal and vertical flip options
- Adjustable UI scaling
- Support for multiple dome types:
  - Standard Fulldome: Traditional dome projection
  - Virtual Sky: Optimized for looking up at the sky
- Advanced rotation controls:
  - Tilt (X-axis): -180° to 180°
  - Pan (Y-axis): -180° to 180°
  - Roll (Z-axis): -180° to 180°
  - Zoom: 0.1 to 2.0
- Support for multiple input formats:
  - Equirectangular (standard 360° format)
  - Cubemap (six faces arranged horizontally)
- Progress tracking for conversions
- Modern and intuitive user interface
- Theme customization options

## Installation

1. Make sure you have Python 3.8 or newer installed on your system
2. Clone this repository or download the ZIP file
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python fulldome_converter.py
   ```
2. Import your media:
   - Click "Import Image" for photos
   - Click "Import Video" for video files
3. Adjust your settings:
   - Select input format (Equirectangular or Cubemap)
   - Choose dome type (Standard Fulldome or Virtual Sky)
   - Fine-tune rotation and zoom
   - Use flip controls if needed
4. Preview your changes in real-time
5. Click "Export" when satisfied
6. Choose output location and wait for conversion

For detailed instructions, click the "About" button in the application.

## Supported Formats

### Input Formats
- Images: JPG, PNG
- Videos: MP4, MOV, AVI

### Output Format
- Circular fisheye projection suitable for fulldome displays

## Tips for Best Results

1. Preview thoroughly before exporting
2. Use timeline to check critical video moments
3. Use spinboxes for precise control
4. Adjust UI scale if needed
5. Don't close during video conversion

## Contributing

This is an open-source project, and contributions are welcome! Whether you're interested in:
- Adding new features
- Improving existing functionality
- Fixing bugs
- Enhancing the user interface
- Optimizing performance
- Adding support for new formats

Feel free to fork the project and submit pull requests.

## Technical Details

- Built with Python and PyQt6
- Uses OpenCV for video processing
- Cross-platform compatible
- Modern UI with theme support
- Real-time preview rendering

## Support and Feedback

- Email: dacsol@gmail.com
- Facebook: [Developer's Page](https://www.facebook.com/daciansolgen24)

## License

Released under the MIT License

## Acknowledgments

Thanks to all contributors and users who help improve this tool for the fulldome community!
