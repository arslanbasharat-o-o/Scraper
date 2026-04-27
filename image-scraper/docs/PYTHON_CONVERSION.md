# Python Image Conversion Integration

This project uses Python for faster image conversion to JPG format, using Pillow for conversion and optimization.

## Requirements

- Python 3.7+
- Pillow (PIL) library: `pip install Pillow`

## How It Works

### Python Script: `convert_image.py`

The Python script:
1. Downloads images from URLs with timeout handling
2. Converts to JPG format with 85% quality (optimizable)
3. Handles image conversions (RGBA to RGB, etc.)
4. Returns base64-encoded JPG data
5. Includes error handling for malformed/missing images

### Node.js Integration

The Node.js server:
1. Calls Python script via `execFile` for each image
2. Runs conversions concurrently (configurable via `IMAGE_DOWNLOAD_CONCURRENCY`)
3. Stores converted JPG data (base64) in database
4. Falls back to storing URL only if conversion fails
5. Tracks conversion success/failure per image

## API Endpoints

### Get Images Metadata
```
GET /jobs/:id/images
GET /jobs/:id/images?product_id=0
```

Returns array of images with metadata:
```json
{
  "id": "jobId_productIndex_imageIndex",
  "url": "source_url",
  "converted": true,
  "size": 45234,
  "quality": 85,
  "jpg_data": null,  // Not included in metadata endpoint
  "created_at": "2026-02-13T12:34:56.789Z"
}
```

### Get Image JPG Data
```
GET /jobs/:id/images/:imageId
```

Returns:
- If converted: Binary JPG image with proper headers
- If not converted: Metadata JSON with `original_url`

## Configuration

Environment variables:
- `IMAGE_HTTP_TIMEOUT_MS` (default: 20000ms) - Download timeout
- `IMAGE_CONVERT_TIMEOUT_MS` (default: 25000ms) - Python conversion timeout
- `IMAGE_DOWNLOAD_CONCURRENCY` (default: 3) - Concurrent conversions

## Performance

Python/Pillow is typically much faster than pure Node.js conversion for:
- Large batch image processing
- RGBA/transparency handling
- JPEG quality optimization
- Memory efficiency with large images

## Fallback Behavior

If Python conversion fails:
1. Image URL is stored in database
2. Conversion flag set to `false`
3. Error message recorded
4. Scraping continues (non-blocking)

## Cleanup

Old images (>24 hours) are automatically removed from database every 30 minutes.

## Example Usage

```javascript
// Get all images for a job
GET /jobs/1707811234567/images

// Get images for a specific product
GET /jobs/1707811234567/images?product_id=0

// Download a specific image JPG
GET /jobs/1707811234567/images/1707811234567_0_0
```

## Troubleshooting

### Python script not found
- Ensure `convert_image.py` is in the project root
- Check file permissions: `chmod +x convert_image.py`

### Python3 not found
- Install Python 3: https://www.python.org/downloads/
- Or use system Python path in code

### Pillow import error
```bash
pip install Pillow
# or
pip3 install Pillow
```

### Timeout errors
- Increase `IMAGE_CONVERT_TIMEOUT_MS` environment variable
- Check internet connection for slow downloads
