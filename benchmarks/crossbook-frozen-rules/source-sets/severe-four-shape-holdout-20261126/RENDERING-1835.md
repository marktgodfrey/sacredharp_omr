# Southern Harmony composite raster policy

Before viewing rendered page pixels, metadata extraction found two layered
JPEG2000 images per PDF page (low-resolution background and higher-resolution
foreground). A single embedded image is not a complete source page. Therefore
render the original composite PDF at fixed300dpi with system Poppler pdftoppm
-png, default colour output; no enhancement, deskew, threshold or subsequent
rescaling. This matches approximately the higher-resolution layer's native
scale. Selection and crop coordinates refer to these fixed composite PNGs.
Keep original PDF bytes and render tool version/command hashed in provenance.
Do not use isolated foreground/background layers as target inputs.
