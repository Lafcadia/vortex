import base64
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError


api_bp = Blueprint("api", __name__)

SUPPORTED_FORMATS = {
    "png": ("PNG", "png"),
    "jpg": ("JPEG", "jpg"),
    "webp": ("WEBP", "webp"),
    "ico": ("ICO", "ico"),
    "svg": ("SVG", "svg"),
    "tiff": ("TIFF", "tiff"),
}

MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "ico": "image/x-icon",
    "svg": "image/svg+xml",
    "tiff": "image/tiff",
}


def _form_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(request.form.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


@api_bp.post("/api/edit")
def edit_image():
    uploaded_file = request.files.get("image")
    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({"error": "请上传一张图片。"}), 400

    try:
        image = Image.open(uploaded_file.stream).convert("RGBA")
        image.load()
    except (UnidentifiedImageError, OSError):
        return jsonify({"error": "无法读取图片文件。"}), 400

    if request.form.get("invert") == "true":
        alpha = image.getchannel("A")
        image = ImageOps.invert(image.convert("RGB")).convert("RGBA")
        image.putalpha(alpha)

    image = ImageEnhance.Contrast(image).enhance(
        _form_float("contrast", 1, 0, 3)
    )
    image = ImageEnhance.Sharpness(image).enhance(
        _form_float("sharpness", 1, 0, 4)
    )
    blur = _form_float("blur", 0, 0, 20)
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(blur))
    image = ImageEnhance.Brightness(image).enhance(
        _form_float("exposure", 1, 0, 3)
    )

    hue = _form_float("hue", 0, -180, 180)
    saturation = _form_float("saturation", 1, 0, 3)
    if hue or saturation != 1:
        alpha = image.getchannel("A")
        hsv = image.convert("RGB").convert("HSV")
        hue_channel, saturation_channel, value_channel = hsv.split()
        if hue:
            hue_shift = int(hue * 255 / 360)
            hue_channel = hue_channel.point([(value + hue_shift) % 256 for value in range(256)])
        if saturation != 1:
            saturation_channel = saturation_channel.point(
                [max(0, min(255, int(value * saturation))) for value in range(256)]
            )
        image = Image.merge("HSV", (hue_channel, saturation_channel, value_channel)).convert("RGBA")
        image.putalpha(alpha)

    crop_width = int(_form_float("crop_width", image.width, 1, image.width))
    crop_height = int(_form_float("crop_height", image.height, 1, image.height))
    crop_x = int(_form_float("crop_x", 0, 0, image.width - crop_width))
    crop_y = int(_form_float("crop_y", 0, 0, image.height - crop_height))
    if (crop_x, crop_y, crop_width, crop_height) != (0, 0, image.width, image.height):
        image = image.crop((crop_x, crop_y, crop_x + crop_width, crop_y + crop_height))

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return send_file(
        output,
        mimetype="image/png",
        as_attachment=False,
        download_name="arg-pack-edit.png",
    )


@api_bp.post("/api/convert")
def convert_image():
    uploaded_file = request.files.get("image")
    target_format = request.form.get("format", "png").lower()

    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({"error": "请上传一张图片。"}), 400
    if target_format not in SUPPORTED_FORMATS:
        return jsonify({"error": "暂不支持该输出格式。"}), 400

    try:
        source_image = Image.open(uploaded_file.stream)
        source_image.load()
    except (UnidentifiedImageError, OSError):
        return jsonify({"error": "无法读取图片文件。"}), 400

    output_format, extension = SUPPORTED_FORMATS[target_format]
    if output_format == "JPEG":
        if source_image.mode in ("RGBA", "LA") or "transparency" in source_image.info:
            source_image = source_image.convert("RGBA")
            background = Image.new("RGB", source_image.size, "white")
            background.paste(source_image, mask=source_image.getchannel("A"))
            source_image = background
        else:
            source_image = source_image.convert("RGB")
    elif output_format == "PNG" and source_image.mode == "P":
        source_image = source_image.convert("RGBA")
    elif output_format == "ICO":
        source_image = source_image.convert("RGBA")
        icon_size = min(max(source_image.width, source_image.height), 256)
        icon_canvas = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
        source_image.thumbnail((icon_size, icon_size), Image.Resampling.LANCZOS)
        offset = (
            (icon_size - source_image.width) // 2,
            (icon_size - source_image.height) // 2,
        )
        icon_canvas.paste(source_image, offset, source_image)
        source_image = icon_canvas

    if output_format == "SVG":
        png_output = BytesIO()
        source_image.save(png_output, format="PNG")
        encoded_image = base64.b64encode(png_output.getvalue()).decode("ascii")
        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{source_image.width}" '
            f'height="{source_image.height}" viewBox="0 0 {source_image.width} '
            f'{source_image.height}"><image width="100%" height="100%" '
            f'href="data:image/png;base64,{encoded_image}"/></svg>'
        )
        output = BytesIO(svg_content.encode("utf-8"))
    else:
        output = BytesIO()
        save_options = {"quality": 92} if output_format == "WEBP" else {}
        source_image.save(output, format=output_format, **save_options)
    output.seek(0)

    return send_file(
        output,
        mimetype=MIME_TYPES[target_format],
        as_attachment=False,
        download_name=f"vortex-image.{extension}",
    )

