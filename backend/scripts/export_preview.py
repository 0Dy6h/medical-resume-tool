"""Generate preview DOCX/PDF exports for visual inspection.

Constructs a sample draft covering all 9 profile collections + identity +
gaps + evidence, renders both application and diagnostic modes, and
saves PNG renderings of each PDF page.

Usage (from backend/):
    uv run python scripts/export_preview.py

Outputs to backend/tmp/:
    preview-application.docx / .pdf
    preview-diagnostic.docx / .pdf
    preview-application-page-*.png
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend/ is on the path when run with `uv run python scripts/...`
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import fitz  # noqa: E402

from app.services.exporter import export_docx, export_pdf  # noqa: E402

TMP_DIR = backend_root / "tmp"


def _sample_draft() -> dict:
    return {
        "id": 1,
        "title": "内科医师 定制简历",
        "sections": [
            {
                "id": "identity",
                "title": "个人信息",
                "items": [
                    {"text": "张三"},
                    {"text": "电话：13800000000 ｜ 邮箱：zhangsan@example.com ｜ 所在地：北京 ｜ 求职意向：内科医师"},
                    {"text": "三年三甲医院内科临床经验，擅长常见病多发病诊疗，具备独立值班和急诊处理能力，参与多项临床研究课题。"},
                ],
            },
            {
                "id": "target",
                "title": "求职目标",
                "items": [{"text": "应聘 某三甲医院 - 内科医师，突出与岗位要求直接相关的真实经历。"}],
            },
            {
                "id": "education",
                "title": "教育背景",
                "items": [
                    {"text": "南方医科大学 / 硕士 / 内科学 / 2019-09-2022-06：循证医学训练；临床研究设计；三级查房规范"},
                    {"text": "某医科大学 / 学士 / 临床医学 / 2014-09-2019-06：基础医学课程；临床轮转实习；医学伦理学"},
                ],
            },
            {
                "id": "experiences",
                "title": "工作/实习经历",
                "items": [
                    {"text": "某三甲医院 / 内科住院医师 / 2022-07-2024-06：负责病区日常诊疗工作，管理床位二十张，参与三级查房与疑难病例讨论，协助带教实习生与进修医师，完成教学查房与病例汇报，参与科室质控工作，整理分析住院数据，撰写月度质控报告并提出改进建议"},
                    {"text": "社区医院 / 全科实习 / 2018-03-2018-09：门诊跟诊与慢病管理；家庭医生签约服务；健康档案建立与维护"},
                ],
            },
            {
                "id": "projects",
                "title": "科研/项目经历",
                "items": [
                    {"text": "慢病队列随访项目 / 项目成员 / 2020-01-2023-06：完成三百例随访记录核查；输出阶段性数据质量报告；协助统计分析与论文撰写"},
                ],
            },
            {
                "id": "publications",
                "title": "论文成果",
                "items": [
                    {"text": "某队列研究 / 中华医学杂志 / 2023"},
                ],
            },
            {
                "id": "certificates",
                "title": "证书资质",
                "items": [
                    {"text": "大学英语六级 / 教育部考试中心 / 2022"},
                    {"text": "执业医师资格证 / 国家卫健委 / 2020"},
                ],
            },
            {
                "id": "skills",
                "title": "技能能力",
                "items": [
                    {"text": "SPSS"},
                    {"text": "临床研究"},
                    {"text": "数据分析"},
                ],
            },
            {
                "id": "teaching",
                "title": "教学经历",
                "items": [
                    {"text": "流行病学 / 助教 / 某医科大学 / 2021"},
                ],
            },
            {
                "id": "awards",
                "title": "获奖经历",
                "items": [
                    {"text": "优秀住院医师 / 某三甲医院 / 校级 / 2023"},
                ],
            },
            {
                "id": "languages",
                "title": "语言能力",
                "items": [
                    {"text": "英语 / CET-6"},
                ],
            },
        ],
        "evidence": [
            {"requirement": "内科学硕士", "source_label": "教育经历", "source_text": "南方医科大学 硕士", "evidence_strength": "strong"},
            {"requirement": "熟悉SPSS", "source_label": "技能能力", "source_text": "SPSS", "evidence_strength": "partial"},
        ],
        "gaps": [
            {"requirement": "SCI论文发表", "message": "未在你的履历中找到对应证据：SCI论文发表", "blocking": False},
            {"requirement": "博士学位", "message": "岗位要求博士学位，不满足该条件", "blocking": True},
        ],
    }


def main() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    draft = _sample_draft()

    for mode in ("application", "diagnostic"):
        suffix = "" if mode == "application" else "-诊断版"
        docx_bytes = export_docx(draft, include_appendix=(mode == "diagnostic"))
        pdf_bytes = export_pdf(draft, include_appendix=(mode == "diagnostic"))

        docx_path = TMP_DIR / f"preview-{mode}.docx"
        pdf_path = TMP_DIR / f"preview-{mode}.pdf"
        docx_path.write_bytes(docx_bytes)
        pdf_path.write_bytes(pdf_bytes)
        print(f"  {docx_path.name} ({len(docx_bytes):,} bytes)")
        print(f"  {pdf_path.name} ({len(pdf_bytes):,} bytes)")

        # Render PDF pages as PNG
        doc = fitz.open(str(pdf_path))
        for i, page in enumerate(doc):
            png_path = TMP_DIR / f"preview-{mode}-page-{i + 1}.png"
            pix = page.get_pixmap(dpi=150)
            pix.save(str(png_path))
            print(f"  {png_path.name} ({pix.width}×{pix.height})")
        doc.close()

    print(f"\nAll preview files written to: {TMP_DIR}")


if __name__ == "__main__":
    main()
