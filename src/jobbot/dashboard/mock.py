"""DỮ LIỆU GIẢ — và đồng thời là BẢN HỢP ĐỒNG cho backend.

Mỗi hàm ở đây trả về đúng hình dạng mà module thật phải trả về sau này:

    jobs()        <- dedup/  sau khi gộp, kèm điểm từ scoring/
    proposals()   <- core/   hàng đợi chờ Yes/No
    pipeline()    <- core/   state machine vòng đời ứng tuyển
    projects()    <- cv/     cụm project theo nhóm JD
    activity()    <- core/   audit log
    run_status()  <- core/   scheduler đang làm gì

Khi nối backend: thay ruột hàm, GIỮ NGUYÊN hình dạng trả về.
Trang không phải sửa dòng nào. Đó là lý do gom hết vào một file.

Số liệu dưới đây bịa, nhưng bịa theo đúng hồ sơ Vin (quant/data, London,
Graduate visa) để nhìn phát biết ngay app có dùng được không.
"""

from __future__ import annotations


def run_status() -> dict:
    return {
        "state": "running",
        "last_scan": "14 minutes ago",
        "next_scan": "in 46 minutes",
        "window": "08:00 – 22:00 (human-paced sources)",
        "sources_ok": 5,
        "sources_total": 6,
        "sources_failed": ["reed.co.uk — missing API key"],
    }


def counters() -> list[dict]:
    return [
        {"value": "1,247", "label": "Postings seen", "note": "last 30 days"},
        {"value": "892",   "label": "After dedup",   "note": "355 duplicates merged"},
        {"value": "61",    "label": "Matched > 75%", "note": "your threshold"},
        {"value": "6",     "label": "Awaiting you",  "note": "in the queue"},
        {"value": "23",    "label": "Applications",  "note": "in flight"},
        {"value": "4",     "label": "Replies",       "note": "17% response rate"},
    ]


def needs_you() -> list[dict]:
    return [
        {"kind": "approve", "text": "6 applications ready to send", "href": "/queue",
         "note": "Approve as a batch — the system sends them over the next few hours"},
        {"kind": "mail", "text": "Check your inbox — 2 unread replies expected", "href": "/pipeline",
         "note": "Man Group and Revolut both acknowledged 5+ days ago"},
        {"kind": "follow", "text": "3 follow-ups due", "href": "/pipeline",
         "note": "No response after 10 days"},
    ]


def jobs() -> list[dict]:
    return [
        {"id": "j1", "title": "Quantitative Analyst — Graduate Programme 2027",
         "company": "Man Group", "location": "London", "salary": "£65,000 + bonus",
         "score": 91, "sponsor": True, "posted": "2 days ago", "closes": "in 18 days",
         "sources": ["greenhouse", "adzuna", "linkedin"], "state": "new",
         "why_hi": ["MSc Computational Finance", "CFA Level I", "Python + pandas"],
         "why_lo": ["No C++ experience"]},
        {"id": "j2", "title": "Junior Data Scientist",
         "company": "Revolut", "location": "London · hybrid", "salary": "£55,000",
         "score": 84, "sponsor": True, "posted": "4 days ago", "closes": "",
         "sources": ["greenhouse", "arbeitnow"], "state": "queued",
         "why_hi": ["Deep Learning 83", "IBM Data Science cert"],
         "why_lo": ["Asks for 2 years commercial experience"]},
        {"id": "j3", "title": "Risk Analyst — Graduate",
         "company": "Monzo Bank", "location": "London · hybrid", "salary": "£48,000",
         "score": 79, "sponsor": True, "posted": "1 day ago", "closes": "in 30 days",
         "sources": ["greenhouse"], "state": "new",
         "why_hi": ["Investment & Portfolio Management 86", "Risk modelling"],
         "why_lo": ["Prefers FRM over CFA"]},
        {"id": "j4", "title": "Quantitative Researcher (Systematic Equities)",
         "company": "Qube Research", "location": "London", "salary": "not stated",
         "score": 72, "sponsor": True, "posted": "6 days ago", "closes": "",
         "sources": ["lever", "adzuna"], "state": "new",
         "why_hi": ["WorldQuant alpha research"],
         "why_lo": ["Wants PhD", "Asks for 3+ years"]},
        {"id": "j5", "title": "Data Analyst — FP&A",
         "company": "Starling Bank", "location": "Cardiff · onsite", "salary": "£42,000",
         "score": 64, "sponsor": True, "posted": "3 days ago", "closes": "",
         "sources": ["adzuna"], "state": "rejected",
         "why_hi": ["SQL", "Financial modelling"],
         "why_lo": ["Onsite in Cardiff — you are London", "Below your salary floor"]},
        {"id": "j6", "title": "Graduate Analyst, Investment Risk",
         "company": "Aviva Investors", "location": "London", "salary": "£45,000",
         "score": 58, "sponsor": False, "posted": "8 days ago", "closes": "in 4 days",
         "sources": ["adzuna", "reed"], "state": "new",
         "why_hi": ["CFA Level I"],
         "why_lo": ["Not a licensed sponsor — cannot keep you past your visa"]},
    ]


def job_detail(job_id: str) -> dict | None:
    found = next((j for j in jobs() if j["id"] == job_id), None)
    if not found:
        return None
    return {**found,
            "jd": (
                "About the role\n"
                "You will join our systematic investment team as a graduate quantitative "
                "analyst, working alongside researchers and portfolio managers.\n\n"
                "What we're looking for\n"
                "  · A degree in a quantitative discipline — mathematics, physics, "
                "computer science, computational finance or similar\n"
                "  · Strong Python, including pandas and numpy\n"
                "  · Familiarity with statistical modelling and time-series analysis\n"
                "  · CFA or progress towards it is welcome\n"
                "  · Experience with C++ is an advantage\n\n"
                "We are a licensed sponsor and welcome applications from candidates "
                "requiring visa sponsorship."
            ),
            "requirements": [
                {"text": "Quantitative degree", "met": True,  "evidence": "MSc Computational Finance, Royal Holloway"},
                {"text": "Python, pandas, numpy", "met": True,  "evidence": "WorldQuant BRAIN — alpha research"},
                {"text": "Statistical / time-series modelling", "met": True, "evidence": "Data Analysis 83, Deep Learning 83"},
                {"text": "CFA or progress towards", "met": True,  "evidence": "CFA Level I, top 10% globally"},
                {"text": "C++", "met": False, "evidence": "Not on your profile — mentioned as 'an advantage', not required"},
            ],
            "cv_changes": [
                "Lead with MSc Computational Finance instead of the BA",
                "Promote Investment & Portfolio Management (86) into the header",
                "Reword WorldQuant around 'systematic' and 'time-series'",
                "Drop the IBM Machine Learning line — not asked for here",
            ],
            "project": {
                "cluster": "Systematic alpha research",
                "title": "Backtesting 40 momentum signals on UK equities",
                "status": "ready",
                "why": "Directly answers 'statistical modelling and time-series analysis'",
            }}


def proposals() -> list[dict]:
    return [
        {"id": "p1", "kind": "apply", "target": "Man Group — Quantitative Analyst, Graduate 2027",
         "summary": "Tailored CV + covering note + link to alpha backtest write-up",
         "score": 91, "risk": "Irreversible — application cannot be withdrawn"},
        {"id": "p2", "kind": "apply", "target": "Revolut — Junior Data Scientist",
         "summary": "Tailored CV, ML modules brought forward", "score": 84,
         "risk": "Irreversible"},
        {"id": "p3", "kind": "apply", "target": "Monzo Bank — Risk Analyst, Graduate",
         "summary": "Tailored CV, Investment & Portfolio Management promoted", "score": 79,
         "risk": "Irreversible"},
        {"id": "p4", "kind": "followup", "target": "Qube Research — applied 11 days ago",
         "summary": "Short follow-up email, no attachment", "score": 0,
         "risk": "Irreversible — goes to a real inbox"},
        {"id": "p5", "kind": "project", "target": "Build: 'UK equity momentum backtest' write-up",
         "summary": "One-page result covering 4 postings in the alpha-research cluster",
         "score": 0, "risk": "Safe — local file, nothing sent"},
        {"id": "p6", "kind": "profile", "target": "Add 'time-series analysis' to your strong skills?",
         "summary": "Seen in 23 of the last 60 matched postings; not on your profile",
         "score": 0, "risk": "Safe — profile edit only"},
    ]


def pipeline() -> list[dict]:
    return [
        {"company": "Man Group", "role": "Quantitative Analyst, Graduate", "stage": "interview",
         "days": 12, "last": "Interview booked for 11 Sep", "due": ""},
        {"company": "Revolut", "role": "Junior Data Scientist", "stage": "acknowledged",
         "days": 6, "last": "Automated acknowledgement", "due": "Check inbox"},
        {"company": "Qube Research", "role": "Quantitative Researcher", "stage": "applied",
         "days": 11, "last": "No response", "due": "Follow-up due"},
        {"company": "Marshall Wace", "role": "Graduate Quant", "stage": "screening",
         "days": 8, "last": "Online assessment sent", "due": "Assessment expires in 2 days"},
        {"company": "Starling Bank", "role": "Data Analyst", "stage": "rejected",
         "days": 19, "last": "Rejected at CV stage", "due": ""},
        {"company": "Aviva Investors", "role": "Graduate Analyst", "stage": "applied",
         "days": 3, "last": "Submitted", "due": ""},
    ]


STAGES = ["applied", "acknowledged", "screening", "interview", "offer", "rejected"]


def projects() -> list[dict]:
    return [
        {"id": "c1", "cluster": "Systematic alpha research", "jobs": 14, "status": "ready",
         "title": "Backtesting 40 momentum signals on UK equities",
         "number": "Sharpe 1.24 out-of-sample, from 0.71 in-sample after fixing look-ahead bias",
         "pages": 6},
        {"id": "c2", "cluster": "Risk analytics", "jobs": 9, "status": "building",
         "title": "VaR breach analysis on a 5-year FTSE portfolio",
         "number": "—", "pages": 0},
        {"id": "c3", "cluster": "Data engineering / analytics", "jobs": 21, "status": "proposed",
         "title": "Deduplicating 1,200 job postings across 6 sources",
         "number": "—", "pages": 0},
        {"id": "c4", "cluster": "ML / deep learning", "jobs": 7, "status": "proposed",
         "title": "not decided yet", "number": "—", "pages": 0},
    ]


def project_page() -> dict:
    """Một trang kết quả — đúng khuôn 5 phần trong strategy.md §5."""
    return {
        "for_job": "Man Group — Quantitative Analyst, Graduate Programme 2027",
        "problem": "Momentum signals that look strong in-sample usually collapse out-of-sample. "
                   "I wanted to know how much of that is look-ahead bias rather than decay.",
        "method": [
            "Built 40 momentum signals on FTSE 350 daily data, 2015–2025",
            "Ran each through a walk-forward backtest with a 12-month rolling window",
            "Rebuilt the pipeline after finding the first version leaked next-day returns",
        ],
        "number": "Mean out-of-sample Sharpe went from 0.71 to 1.24 once the leak was removed — "
                  "measured across all 40 signals, same data, same windows.",
        "tradeoff": "Ignored transaction costs entirely. With realistic UK equity costs the "
                    "top 8 signals stay profitable and the rest do not — so the headline "
                    "number is optimistic and I would not trade on it as it stands.",
        "code": "github.com/…/uk-momentum-backtest",
    }


def activity() -> list[dict]:
    return [
        {"time": "14 min ago", "text": "Scanned Greenhouse — 47 postings, 12 new", "kind": "scan"},
        {"time": "14 min ago", "text": "Merged 8 duplicates (same role on 3 boards)", "kind": "dedup"},
        {"time": "18 min ago", "text": "Scored 12 postings — 3 above threshold", "kind": "score"},
        {"time": "22 min ago", "text": "Checked 6 employers against the UK sponsor register", "kind": "check"},
        {"time": "1 hour ago", "text": "Sent application — Aviva Investors (you approved 10:14)", "kind": "send"},
        {"time": "2 hours ago", "text": "Reed.co.uk skipped — no API key", "kind": "warn"},
        {"time": "3 hours ago", "text": "Drafted CV variant for Monzo Risk Analyst", "kind": "cv"},
    ]


def stats() -> dict:
    return {
        "by_source": [
            {"name": "Greenhouse", "sent": 9,  "replies": 3, "rate": 33},
            {"name": "Adzuna",     "sent": 7,  "replies": 1, "rate": 14},
            {"name": "Arbeitnow",  "sent": 4,  "replies": 0, "rate": 0},
            {"name": "Lever",      "sent": 3,  "replies": 0, "rate": 0},
        ],
        "by_score": [
            {"band": "90 – 100", "sent": 3,  "replies": 2, "rate": 67},
            {"band": "80 – 89",  "sent": 6,  "replies": 1, "rate": 17},
            {"band": "70 – 79",  "sent": 9,  "replies": 1, "rate": 11},
            {"band": "60 – 69",  "sent": 5,  "replies": 0, "rate": 0},
        ],
        "funnel": [
            ("Postings seen", 1247), ("After dedup", 892), ("Passed filters", 214),
            ("Matched > 75%", 61), ("You approved", 23), ("Replies", 4), ("Interviews", 1),
        ],
        "insight": "Nothing below 70 has ever produced a reply. Raising the threshold to 70 "
                   "would have saved 5 applications and cost nothing.",
    }


def sources() -> list[dict]:
    return [
        {"name": "Greenhouse",     "key": False, "on": True,  "last": "14 min ago", "found": 412},
        {"name": "Lever",          "key": False, "on": True,  "last": "14 min ago", "found": 138},
        {"name": "Ashby",          "key": False, "on": True,  "last": "14 min ago", "found": 96},
        {"name": "Arbeitnow",      "key": False, "on": True,  "last": "31 min ago", "found": 274},
        {"name": "Remotive",       "key": False, "on": True,  "last": "31 min ago", "found": 83},
        {"name": "Adzuna GB",      "key": True,  "on": True,  "last": "1 hour ago", "found": 244},
        {"name": "Reed.co.uk",     "key": True,  "on": False, "last": "never",      "found": 0},
        {"name": "LinkedIn",       "key": False, "on": False, "last": "never",      "found": 0},
    ]
