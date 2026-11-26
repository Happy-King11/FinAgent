"""对高敏感金融表达执行确定性合规检查。"""

from app.tools.compliance import ComplianceDecision, ComplianceEngine


class ComplianceSensitivePipeline:
    def __init__(self, engine: ComplianceEngine | None = None) -> None:
        self.engine = engine or ComplianceEngine()

    def run(self, question: str) -> ComplianceDecision:
        # Pipeline 只返回结构化决策，最终阻断/复核由应用服务执行。
        return self.engine.check(question)
