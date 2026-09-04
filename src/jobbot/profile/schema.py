"""Định nghĩa các vòng hỏi — DỮ LIỆU, không phải giao diện.

Dashboard đọc file này để vẽ. Thêm/sửa câu hỏi thì chỉ sửa ở đây,
không đụng vào tầng web. Đó là lý do dashboard không có logic nghiệp vụ.

Nhận theo VÒNG, không hỏi một lần 30 câu:
    Vòng 1  Định vị     — chặn ingest. Không có thì không kéo tin nào về.
    Vòng 2  Ràng buộc   — cái KHÔNG nhận. Thứ hay bị quên nhất.
    Vòng 3  Nguyên liệu — CV, kỹ năng, JD thật. Cần cho scoring và cv builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SINGLE, MULTI, TEXT, LONGTEXT = "single", "multi", "text", "longtext"


@dataclass(frozen=True)
class Option:
    value: str
    label: str
    note: str = ""          # hệ quả nếu chọn — người dùng thấy được


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    kind: str
    why: str = ""           # vì sao hỏi. Không giải thích được thì đừng hỏi.
    options: list[Option] = field(default_factory=list)
    placeholder: str = ""
    required: bool = True


@dataclass(frozen=True)
class Round:
    id: str
    title: str
    why: str
    questions: list[Question]


ROUNDS: list[Round] = [
    Round(
        id="dinh_vi",
        title="Vòng 1 — Định vị",
        why="Chưa trả lời xong vòng này thì hệ thống chưa được phép kéo tin nào về.",
        questions=[
            Question(
                id="target_roles",
                text="Bạn nhắm vai trò nào?",
                kind=MULTI,
                why="Quyết định từ khoá tìm kiếm và cách chấm điểm. Chọn càng ít càng sắc.",
                options=[
                    Option("backend", "Backend", "API, service, database, hệ thống phía sau"),
                    Option("data", "Data (DE / DA)", "Pipeline, ETL, warehouse, phân tích"),
                    Option("ml", "ML / AI", "Model, training, LLM application, MLOps"),
                    Option("frontend", "Frontend / Fullstack", "Giao diện, web app, hoặc cả hai đầu"),
                    Option("devops", "DevOps / Platform / SRE", "Hạ tầng, CI/CD, vận hành"),
                    Option("qa", "QA / Test", "Kiểm thử thủ công hoặc tự động"),
                ],
            ),
            Question(
                id="years_real",
                text="Bao nhiêu năm bạn làm THẬT trong mảng đó?",
                kind=SINGLE,
                why=(
                    "Đây là biến quan trọng nhất. Apply vượt tầm thì bị loại ở vòng lọc "
                    "trước khi ai kịp đọc phần đáng đọc. Apply dưới tầm thì bị loại vì "
                    "overqualified. Ghi số thật — không phải số mình muốn."
                ),
                options=[
                    Option("0-1", "Chưa đi làm / dưới 1 năm", "Nhắm entry-level, fresher"),
                    Option("1-3", "1 – 3 năm", "Nhắm junior đến mid"),
                    Option("3-5", "3 – 5 năm", "Nhắm mid đến senior"),
                    Option("5+", "Trên 5 năm", "Nhắm senior, lead"),
                ],
            ),
            Question(
                id="markets",
                text="Bạn nhắm thị trường nào?",
                kind=MULTI,
                why="Câu này quyết định TOÀN BỘ tầng ingest — dùng nguồn nào, và nguồn nào vô dụng.",
                options=[
                    Option("vn_onsite", "VN — onsite / hybrid",
                           "Cần nguồn VN (ITviec, TopCV, VietnamWorks). Hầu hết không có API."),
                    Option("vn_remote_intl", "VN — remote cho công ty nước ngoài",
                           "Dùng được nguồn quốc tế, nhưng phải lọc tin cho phép múi giờ châu Á."),
                    Option("remote_global", "Remote quốc tế hoàn toàn",
                           "Hợp nhất với các nguồn đã kiểm chứng: Greenhouse, Lever, Ashby, Remotive."),
                    Option("relocate", "Sẵn sàng ra nước ngoài",
                           "Phải lọc thêm tin có visa sponsorship."),
                ],
            ),
            Question(
                id="doc_language",
                text="Hồ sơ và JD chủ yếu bằng ngôn ngữ nào?",
                kind=SINGLE,
                why="Quyết định cách tách từ khi chấm điểm, và CV builder sinh ra bản nào.",
                options=[
                    Option("en", "Tiếng Anh", "Chỉ cần xử lý một ngôn ngữ"),
                    Option("vi", "Tiếng Việt", "Tách từ tiếng Việt khó hơn, cần xử lý riêng"),
                    Option("both", "Cả hai", "Cần hai bộ CV. Tốn công hơn nhưng phủ rộng hơn"),
                ],
            ),
        ],
    ),
    Round(
        id="rang_buoc",
        title="Vòng 2 — Ràng buộc",
        why="Cái bạn KHÔNG nhận. Đây là thứ hay bị quên nhất, và là thứ chặn spam hiệu quả nhất.",
        questions=[
            Question(
                id="salary_floor",
                text="Mức thấp nhất bạn nhận (ghi kèm đơn vị)",
                kind=TEXT,
                why="Không có sàn thì hệ thống đề xuất cả những việc bạn chắc chắn từ chối.",
                placeholder="ví dụ: 25 triệu/tháng  ·  hoặc 3000 USD/tháng",
            ),
            Question(
                id="no_go",
                text="Kiểu công việc bạn CHẮC CHẮN không nhận",
                kind=MULTI,
                why="Lọc sớm ở đây rẻ hơn nhiều so với đọc rồi bỏ ở dashboard.",
                required=False,
                options=[
                    Option("onsite_only", "Bắt buộc onsite 100%"),
                    Option("outsourcing", "Công ty gia công / outsourcing"),
                    Option("night_shift", "Làm ca đêm theo giờ Mỹ / EU"),
                    Option("no_ot_pay", "OT không trả tiền"),
                    Option("startup_early", "Startup giai đoạn quá sớm"),
                    Option("contract", "Hợp đồng ngắn hạn / freelance"),
                ],
            ),
            Question(
                id="no_go_other",
                text="Còn gì khác bạn không nhận? (viết tự do)",
                kind=LONGTEXT,
                why="Ràng buộc riêng mà danh sách trên không có.",
                required=False,
                placeholder="ví dụ: không dùng PHP · không công ty dưới 20 người · không đi công tác",
            ),
        ],
    ),
    Round(
        id="nguyen_lieu",
        title="Vòng 3 — Nguyên liệu",
        why="Nguồn để chấm điểm và để dựng CV. Chưa có thì scoring chấm dựa trên không khí.",
        questions=[
            Question(
                id="cv_text",
                text="Dán CV hiện tại của bạn vào đây",
                kind=LONGTEXT,
                why="Nguyên liệu thô cho scoring và CV builder. Dán thô cũng được, không cần đẹp.",
                placeholder="Dán toàn bộ nội dung CV — kinh nghiệm, dự án, kỹ năng...",
            ),
            Question(
                id="top_skills",
                text="Kỹ năng chính, xếp theo độ thành thạo thật",
                kind=TEXT,
                why="Dùng để đối chiếu trực tiếp với phần requirements trong JD.",
                placeholder="ví dụ: Python, PostgreSQL, Docker, FastAPI, AWS",
            ),
            Question(
                id="proof_jds",
                text="Dán 2–3 JD thật mà bạn thấy \"cái này tôi làm được thật\"",
                kind=LONGTEXT,
                why=(
                    "Quan trọng nhất trong vòng này. Có JD thật thì đi ngược từ đó ra "
                    "personal project — thay vì xây trước rồi tìm chỗ nhét vào. "
                    "Chọn JD bạn tự tin làm được, không phải JD 'cố thì được'."
                ),
                placeholder="Dán nguyên văn JD, cách nhau bằng một dòng ---",
            ),
        ],
    ),
]


def all_questions() -> dict[str, Question]:
    return {q.id: q for r in ROUNDS for q in r.questions}


def round_by_id(round_id: str) -> Round | None:
    return next((r for r in ROUNDS if r.id == round_id), None)
