"""Only decode the raster formats supported by profile and recruitment OCR."""

# Restrict decoder selection before parsing. A .png filename alone does not
# prevent Pillow from entering EPS, PDF or font parsers based on its bytes.
SUPPORTED_IMAGE_FORMATS = ("PNG", "JPEG", "WEBP", "BMP", "TIFF")
MAX_IMAGE_PIXELS = 24_000_000
