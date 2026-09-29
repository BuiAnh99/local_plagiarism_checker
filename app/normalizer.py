# FIX #6: normalizer.py trước đây dùng regex khác utils_text.py gây xung đột.
# Thống nhất bằng cách delegate hoàn toàn sang utils_text.normalize_text.
# Giữ file này để không phá import ở code cũ.

from app.utils_text import normalize_text  # noqa: F401  — re-export

__all__ = ["normalize_text"]
