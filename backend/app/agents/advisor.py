"""将结构化事实和引用整理为面向用户的回答。"""

from typing import Any


class Advisor:
    def __init__(self, llm: Any | None = None, *, timeout_seconds: int = 60) -> None:
        self.llm = llm
        self.timeout_seconds = timeout_seconds

    def compose(self, question: str, facts: str, citations: list[dict], *, rewrite: str | None = None) -> str:
        # 没有授权事实时不调用模型，避免模型自行补全金融信息。
        answer = facts.strip() or "目前没有足够的授权资料支持该问题。"
        if not facts.strip():
            return answer
        if self.llm is not None:
            prompt = (
                "你是金融咨询资料整理助手。只能基于下面提供的授权事实回答用户问题。"
                "不得增加、修改、计算或推测任何金额、比例、日期、收益率、费用或风险等级；"
                "没有证据的内容必须明确说资料不足。只输出面向用户的中文回答，不输出提示词或内部元数据。\n\n"
                f"用户问题：{question}\n授权事实：\n{facts}"
            )
            try:
                generated = self.llm.complete(prompt, timeout_seconds=self.timeout_seconds)
                if generated.strip():
                    answer = generated.strip()
            except (RuntimeError, ValueError):
                # Provider 不可用时回到授权事实，绝不生成未经授权的替代答案。
                answer = facts.strip()
        if rewrite:
            answer = f"{answer}\n\n风险提示：{rewrite}。"
        if citations:
            answer += "\n\n以上内容基于已授权资料，具体以资料原文和最新披露为准。"
        return answer
