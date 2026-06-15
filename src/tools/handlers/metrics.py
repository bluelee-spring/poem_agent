"""格律校验 Handler — 调用搜韵网 API 进行平仄、押韵、对仗校验

API: POST https://cnkgraph.com/api/Tool/AnalyzePoem
RhymeBook 参数映射:
  - "平水韵" / "psy"  → "psy"
  - "词林正韵" / "cyl" → "cyl"
  - "中原音韵" / "zyy" → "zyy"
  - "中华通韵" / "zhty" → "zhty"
"""

import json
from typing import Any
import httpx


# RhymeBook 中文名 → API 缩写
_RHYME_BOOK_MAP = {
    "平水韵": "psy",
    "词林正韵": "cyl",
    "中原音韵": "zyy",
    "中华通韵": "zhty",
    "psy": "psy",
    "cyl": "cyl",
    "zyy": "zyy",
    "zhty": "zhty",
}


async def handle_analyze_poem(arguments: dict[str, Any]) -> dict[str, Any]:
    """调用搜韵网律诗校验 API

    Args:
        arguments: {
            "content": "诗歌内容",
            "rhyme": "平水韵",  // 可选，默认平水韵
            "self_pingze_balance": true,  // 是否自平衡平仄
        }

    Returns:
        结构化校验结果，包含平仄分析、韵脚标记、修改建议等
    """
    content = arguments.get("content", "")
    rhyme_book = _RHYME_BOOK_MAP.get(
        arguments.get("rhyme", "平水韵"), "psy"
    )
    self_balance = arguments.get("self_pingze_balance", True)

    if not content:
        return {"success": False, "error": "诗歌内容不能为空"}

    body = {
        "Content": content,
        "RhymeBook": rhyme_book,
        "SelfPingZeBalanceEnabled": self_balance,
        "ClausesPingZeBalanceEnabled": False,
    }

    headers = {
        "accept": "text/plain",
        "Content-Type": "application/json-patch+json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://cnkgraph.com/api/Tool/AnalyzePoem",
                json=body,
                headers=headers,
            )

            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                }

            resp.encoding = "utf-8"
            data = resp.json()

            # 格式错误
            if data.get("FormatError"):
                return {
                    "success": False,
                    "error": data["FormatError"],
                }

            validation = data.get("ValidationResult", {})
            if not validation:
                return {"success": False, "error": "未获取到校验结果"}

            result = _parse_validation(validation, content)
            return {"success": True, "result": result}

    except httpx.TimeoutException:
        return {"success": False, "error": "搜韵网 API 请求超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _parse_validation(validation: dict, content: str) -> dict:
    """完整解析搜韵网返回的 ValidationResult"""
    used_rhyme = validation.get("UsedRhyme", "")
    is_first_neighbor = validation.get("IsFirstClauseUsingNeighborRhyme", False)
    clauses = validation.get("Clauses", [])

    # 用韵总结
    rhyme_summary = f"用韵：{used_rhyme}"
    if is_first_neighbor:
        rhyme_summary += "（首句借邻韵）"

    # 逐句逐字分析
    clause_analysis = []
    pingze_issues = []
    total_errors = 0
    lines = [l for l in content.replace("\r", "").split("\n") if l.strip()]

    for i, clause in enumerate(clauses):
        chars = clause.get("Chars", [])
        errors = clause.get("Errors")
        notification = clause.get("Notification")
        rhymes_mark = clause.get("Rhymes", "")

        clause_text = lines[i] if i < len(lines) else ""
        char_details = []

        for ch in chars:
            char = ch.get("Character", "")
            tone = ch.get("Tone") or "?"
            status = ch.get("Status")

            if status:
                char_details.append(f"{char}({tone},⚠{status})")
            else:
                char_details.append(f"{char}({tone})")

        clause_info = {
            "index": i + 1,
            "text": clause_text,
            "chars": char_details,
            "rhyme_mark": rhymes_mark,
        }

        if errors:
            clause_info["errors"] = errors
            total_errors += 1
            pingze_issues.append(f"第{i+1}句: {errors}")

        if notification:
            clause_info["note"] = notification

        clause_analysis.append(clause_info)

    # 韵脚错误
    rhyme_issues = []
    rhyme_error = validation.get("RhymeError")
    if rhyme_error:
        rhyme_issues.append(str(rhyme_error))

    # 平仄建议（ToneAdvices）
    tone_advices = _parse_tone_advices(validation.get("ToneAdvices", []))

    # 押韵建议
    rhyme_advices = validation.get("RhymeAdvices")
    if rhyme_advices and isinstance(rhyme_advices, list):
        rhyme_issues.extend([str(r) for r in rhyme_advices])

    # 不确定声调的字
    uncertain_tones = validation.get("UncertainTones", [])
    uncertain_chars = [
        f"{u.get('Character', '')}({u.get('RhymeBook', '')})"
        for u in uncertain_tones
    ] if uncertain_tones else []

    # 重复字检测
    duplicated = validation.get("DuplicatedChars", {})
    dup_warning = None
    if duplicated.get("Characters"):
        dup_warning = f"重复字: {', '.join(duplicated['Characters'])}（第{', '.join(str(i) for i in duplicated.get('ClauseIndexes', []))}句）"

    # 总结
    parts = [f"共{len(clauses)}句"]
    if total_errors > 0:
        parts.append(f"格律问题{total_errors}处")
    else:
        parts.append("格律合规")
    parts.append(rhyme_summary)

    return {
        "rhyme": rhyme_summary,
        "total_lines": len(clauses),
        "total_errors": total_errors,
        "clauses": clause_analysis,
        "pingze_issues": pingze_issues,
        "rhyme_issues": rhyme_issues,
        "tone_advices": tone_advices,          # 逐条平仄修改建议
        "uncertain_tones": uncertain_chars,     # 多音字
        "duplicated_chars": dup_warning,        # 重复字警告
        "is_compliant": total_errors == 0,
        "summary": "。".join(parts) + "。",
    }


def _parse_tone_advices(advices: list) -> list[dict]:
    """解析平仄修改建议，精简 candidates 数量避免 token 爆炸"""
    result = []
    for adv in advices:
        if not isinstance(adv, dict):
            continue
        item = {
            "message": adv.get("Message", ""),
        }
        candidates = adv.get("Candidates", [])
        if candidates:
            # 只保留前 8 个候选项
            item["candidates_preview"] = candidates[:8]
            if len(candidates) > 8:
                item["candidates_total"] = len(candidates)
        result.append(item)
    return result


def register_handlers(registry: "ToolRegistry"):
    """注册格律校验 handler"""
    from src.tools.schema.poem import ANALYZE_POEM_SCHEMA
    registry.register(ANALYZE_POEM_SCHEMA, handle_analyze_poem)
