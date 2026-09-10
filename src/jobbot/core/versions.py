"""Phiên bản của các bộ luật.

Đổi luật thì ĐỔI SỐ Ở ĐÂY. Tin nào được phán bằng phiên bản cũ sẽ tự động
được tính lại ở lần quét sau.

Không có cơ chế này thì: sửa vocab.py xong, điểm cũ và điểm mới nằm lẫn trong
cùng một bảng, không cách nào biết cái nào tính bằng luật nào.
"""

FILTER_RULES = "2026-09-07.1"  # ingest/filter.py + ingest/base.norm_*
# scoring/vocab.py + scoring/extract.py + scoring/score.py + realism + deadline
SCORE_RULES = "2026-09-10.3"   # + realism cộng điểm khi đáp ứng yêu cầu bắt buộc
