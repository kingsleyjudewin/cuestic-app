import io
import logging
from datetime import datetime, timezone
from typing import Optional, BinaryIO, Union
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

logger = logging.getLogger(__name__)


def _dms_to_decimal(dms, ref: Optional[str]) -> Optional[float]:
    """
    Convert (degrees, minutes, seconds) rational tuple to decimal degrees.
    Applies negative sign for South latitude or West longitude.
    """
    if not dms or len(dms) < 3:
        return None
    try:
        deg = float(dms[0])
        minute = float(dms[1])
        sec = float(dms[2])
        dec = deg + (minute / 60.0) + (sec / 3600.0)
        if ref and str(ref).strip().upper() in ["S", "W"]:
            dec = -dec
        return round(dec, 6)
    except Exception as e:
        logger.debug("Error parsing DMS coordinate (%s, %s): %s", dms, ref, e)
        return None


def _parse_exif_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse EXIF datetime string formatted like 'YYYY:MM:DD HH:MM:SS'."""
    if not dt_str or not isinstance(dt_str, str):
        return None
    try:
        cleaned = dt_str.strip()
        # Common EXIF date formats
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    except Exception as e:
        logger.debug("Error parsing EXIF date string '%s': %s", dt_str, e)
    return None


class GeotagService:
    """Service for extracting GPS coordinates, capture timestamps, and camera metadata from image files."""

    @classmethod
    def extract_image_metadata(cls, file_source: Union[BinaryIO, bytes, str]) -> dict:
        """
        Inspect available image metadata for GPS coordinates, capture time, and EXIF fields.
        Returns a dictionary with extracted fields or safe None values.
        Does not mutate or strip metadata from the input.
        """
        result = {
            "has_gps": False,
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "captured_at": None,
            "camera_make": None,
            "camera_model": None,
        }

        try:
            if isinstance(file_source, bytes):
                img_io = io.BytesIO(file_source)
            elif isinstance(file_source, str):
                with open(file_source, "rb") as f:
                    img_io = io.BytesIO(f.read())
            else:
                pos = file_source.tell() if hasattr(file_source, "tell") else 0
                data = file_source.read()
                if hasattr(file_source, "seek"):
                    file_source.seek(pos)
                img_io = io.BytesIO(data)

            with Image.open(img_io) as img:
                exif_data = img._getexif()
                if not exif_data:
                    return result

                raw_tags = {}
                gps_info = {}

                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    raw_tags[tag_name] = value
                    if tag_name == "GPSInfo" and isinstance(value, dict):
                        for gps_key, gps_val in value.items():
                            sub_tag = GPSTAGS.get(gps_key, gps_key)
                            gps_info[sub_tag] = gps_val

                # 1. Camera details
                make = raw_tags.get("Make")
                model = raw_tags.get("Model")
                result["camera_make"] = str(make).strip() if make else None
                result["camera_model"] = str(model).strip() if model else None

                # 2. Capture timestamp
                captured_dt_str = (
                    raw_tags.get("DateTimeOriginal")
                    or raw_tags.get("DateTimeDigitized")
                    or raw_tags.get("DateTime")
                )
                result["captured_at"] = _parse_exif_datetime(captured_dt_str)

                # 3. GPS Coordinates
                if gps_info:
                    lat_dms = gps_info.get("GPSLatitude")
                    lat_ref = gps_info.get("GPSLatitudeRef")
                    lon_dms = gps_info.get("GPSLongitude")
                    lon_ref = gps_info.get("GPSLongitudeRef")
                    alt_val = gps_info.get("GPSAltitude")

                    lat_dec = _dms_to_decimal(lat_dms, lat_ref)
                    lon_dec = _dms_to_decimal(lon_dms, lon_ref)

                    if lat_dec is not None and lon_dec is not None:
                        result["has_gps"] = True
                        result["latitude"] = lat_dec
                        result["longitude"] = lon_dec

                    if alt_val is not None:
                        try:
                            result["altitude"] = round(float(alt_val), 2)
                        except (ValueError, TypeError):
                            pass

        except Exception as e:
            logger.info("Non-fatal notice during EXIF extraction: %s", e)

        return result
