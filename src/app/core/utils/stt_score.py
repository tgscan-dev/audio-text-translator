import asyncio

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()


class DetailedScore(BaseModel):
    semantic_accuracy: float = Field(description="语义准确性分数 (0-1)")
    completeness: float = Field(description="完整性分数 (0-1)")
    grammar: float = Field(description="语法正确性分数 (0-1)")
    acceptable: bool = Field(description="是否可接受 (总分>=0.80)")
    comments: str = Field(description="评分说明和建议")
    total_score: float = Field(description="总分 (0-1)")


async def validate_stt(original: str, stt: str) -> DetailedScore:
    """
    Validate STT output quality against original text with detailed scoring

    Args:
        original: Original text
        stt: STT output text
        model: OpenAI model name

    Returns:
        DetailedScore with multiple scoring dimensions:
        - semantic_accuracy: Semantic accuracy score (0-1)
        - completeness: Completeness score (0-1)
        - grammar: Grammar correctness score (0-1)
        - punctuation: Punctuation score (0-1)
        - total_score: Overall weighted score (0-1)
        - acceptable: Whether the result is acceptable (total_score >= 0.85)
        - comments: Evaluation comments and suggestions
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1)  # 省钱
    parser = JsonOutputParser(pydantic_object=DetailedScore)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你是STT（语音转文字）质量评估专家。你需要从多个维度对STT结果进行评分。

评分规则：
1. 语义准确性 (semantic_accuracy)：评估STT输出与原文在语义层面的匹配程度（权重0.6）
   - 1.0：完全一致或同义替换（如"取钱"/"拿钱"）
   - 0.8-0.9：轻微差异但不影响理解（如词序调整）
   - 0.6-0.7：有差异但基本意思相近
   - <0.6：语义有明显偏差

2. 完整性 (completeness)：评估信息的完整性（权重0.3）
   - 1.0：核心信息完全保留
   - 0.8-0.9：次要信息有所缺失（如语气词、修饰词）
   - 0.6-0.7：丢失部分重要信息
   - <0.6：丢失核心信息

3. 语法正确性 (grammar)：评估基本语法结构（权重0.1）
   - 1.0：语句结构完整
   - 0.8-0.9：有小错误但不影响理解
   - 0.6-0.7：句子结构不完整
   - <0.6：严重语法错误影响理解

总分计算：
- total_score = 0.6*semantic_accuracy + 0.3*completeness + 0.1*grammar
- acceptable：总分>=0.80为可接受（主要考虑语义准确性）

{format_instructions}""",
            ),
            (
                "human",
                """请对以下STT结果进行详细评分：

原文：{original}
STT：{stt}

请从语义准确性、完整性、语法正确性和标点符号四个维度进行评分，并给出总分、是否可接受的判断，以及评分说明和改进建议。""",
            ),
        ]
    )

    chain = prompt.partial(format_instructions=parser.get_format_instructions()) | llm | parser

    result = await chain.ainvoke({"original": original, "stt": stt})
    return DetailedScore(**result)


# 使用示例
async def demo():
    """使用演示"""
    print("\n=== STT 质量评估示例 ===")

    # 示例1：轻微差异
    result1 = await validate_stt("我要去银行取钱", "我要去银行拿钱")
    print("\n示例1 - 轻微差异：")
    print(f"语义准确性 (权重0.6): {result1.semantic_accuracy:.2f}")
    print(f"完整性 (权重0.3): {result1.completeness:.2f}")
    print(f"语法正确性 (权重0.1): {result1.grammar:.2f}")
    print(f"总分: {result1.total_score:.2f}")
    print(f"是否可接受: {result1.acceptable}")
    print(f"评价: {result1.comments}")

    # 示例2：明显错误
    result2 = await validate_stt("今天天气真不错，我们去公园散步吧！", "今天天气真不错我们去公园跑步")
    print("\n示例2 - 明显错误：")
    print(f"语义准确性 (权重0.6): {result2.semantic_accuracy:.2f}")
    print(f"完整性 (权重0.3): {result2.completeness:.2f}")
    print(f"语法正确性 (权重0.1): {result2.grammar:.2f}")
    print(f"总分: {result2.total_score:.2f}")
    print(f"是否可接受: {result2.acceptable}")
    print(f"评价: {result2.comments}")


if __name__ == "__main__":
    asyncio.run(demo())
