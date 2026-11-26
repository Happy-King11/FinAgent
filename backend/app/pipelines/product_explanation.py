"""产品事实解释 Pipeline，不执行估值或个性化推荐。"""

from app.pipelines.types import PipelineOutput

class ProductExplanationPipeline:
    def run(self, product, question: str) -> PipelineOutput:
        del question
        # 费用和风险披露直接来自产品记录，保证结果可复核。
        facts = f"{product.name}（{product.product_type}）的风险等级为 {product.risk_level.value}，流动性为{product.liquidity}。{product.description}"
        fees = "；".join(f"{item.get('name')}: {item.get('value')}" for item in product.fees) or "未提供费用明细"
        facts += f"费用：{fees}。"
        return PipelineOutput(
            facts=facts,
            warnings=tuple(product.risk_disclosures),
            result={"scene_id": "product_explanation", "product_id": product.id},
        )
