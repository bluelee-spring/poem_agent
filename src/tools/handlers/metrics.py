"""格律校验 Handler — 调用搜韵网 API 进行平仄、押韵、对仗校验"""

import json
from typing import Any
import httpx


async def handle_analyze_poem(arguments: dict[str, Any]) -> dict[str, Any]:
    """调用搜韵网律诗校验 API

    Args:
        arguments: {
            "content": "诗歌内容",
            "rhyme_book": "平水韵",  // 可选，默认平水韵
            "self_pingze_balance": true,  // 是否自平衡平仄
        }

    Returns:
        结构化校验结果
    """
    content = arguments.get("content", "")
    rhyme_book = arguments.get("rhyme", "平水韵")
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

            # 搜韵网返回的编码可能不是 UTF-8，需要显式解码
            resp.encoding = "utf-8"
            data = resp.json()

            # 如果有格式错误
            if data.get("FormatError"):
                return {
                    "success": False,
                    "error": data["FormatError"],
                }

            validation = data.get("ValidationResult", {})
            if not validation:
                return {"success": False, "error": "未获取到校验结果"}

            # 解析校验结果
            result = _parse_validation(validation, content)

            return {"success": True, "result": result}

    except httpx.TimeoutException:
        return {"success": False, "error": "搜韵网 API 请求超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _parse_validation(validation: dict, content: str) -> dict:
    """解析搜韵网返回的 ValidationResult 为 LLM 可读的格式"""
    used_rhyme = validation.get("UsedRhyme", "")
    is_first_neighbor = validation.get("IsFirstClauseUsingNeighborRhyme", False)
    clauses = validation.get("Clauses", [])

    rhyme_summary = f"用韵：{used_rhyme}"
    if is_first_neighbor:
        rhyme_summary += "（首句借邻韵）"

    # 逐句分析
    clause_analysis = []
    pingze_issues = []
    rhyme_issues = []
    total_errors = 0

    lines = [l for l in content.replace("\r", "").split("\n") if l.strip()]

    for i, clause in enumerate(clauses):
        chars = clause.get("Chars", [])
        errors = clause.get("Errors")
        notification = clause.get("Notification")
        rhymes_mark = clause.get("Rhymes", "")

        clause_text = lines[i] if i < len(lines) else ""
        char_details = []
        for j, ch in enumerate(chars):
            char = ch.get("Character", "")
            tone = ch.get("Tone")  # "平" / "仄" / null
            status = ch.get("Status")

            detail = f"{char}({tone or '?'})"
            if status:
                detail += f"[{status}]"
            char_details.append(detail)

        clause_info = {
            "index": i + 1,
            "text": clause_text,
            "chars": char_details,
            "rhyme_mark": rhymes_mark,  # "S"=押韵, "X"=不押, "R"=可选韵
        }

        if errors:
            clause_info["errors"] = errors
            total_errors += 1
            pingze_issues.append(f"第{i+1}句: {errors}")

        if notification:
            clause_info["note"] = notification

        clause_analysis.append(clause_info)

    return {
        "rhyme": rhyme_summary,
        "total_lines": len(clauses),
        "total_errors": total_errors,
        "clauses": clause_analysis,
        "pingze_issues": pingze_issues,
        "rhyme_issues": rhyme_issues,
        "is_compliant": total_errors == 0,
        "summary": f"共{len(clauses)}句，格律问题{total_errors}处。{rhyme_summary}。" if total_errors > 0 else f"共{len(clauses)}句，格律合规。{rhyme_summary}。",
    }


def register_handlers(registry: "ToolRegistry"):
    """注册格律校验 handler"""
    from src.tools.schema.poem import ANALYZE_POEM_SCHEMA

    registry.register(ANALYZE_POEM_SCHEMA, handle_analyze_poem)
