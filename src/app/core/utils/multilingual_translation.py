from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.app.models.translation_task import LanguageCode

load_dotenv()


class Translation(BaseModel):
    """A single translation"""

    lang: LanguageCode = Field(description="Language code of the translation")
    text: str = Field(description="Translated text")


class TranslationResult(BaseModel):
    """Translation result model"""

    translations: list[Translation] = Field(description="List of translations")


async def translate(text: str, target_langs: list[LanguageCode]) -> TranslationResult:
    """
    Translate text into multiple languages using LLM

    Args:
        text: Text to translate
        target_langs: A list of target language codes

    Returns:
        TranslationResult containing translations in multiple languages
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1)

    parser = JsonOutputParser(pydantic_object=TranslationResult)

    # Dynamically create the language list for the prompt
    lang_list_str = "\n".join([f"{i + 1}. {lang.name} ({lang.value})" for i, lang in enumerate(target_langs)])

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert multilingual translator with deep understanding of cultural nuances
and language-specific expressions.

Your primary responsibilities:
1. Translate the text accurately into all specified target languages
2. Preserve the original meaning, tone, and intent
3. Maintain appropriate formality level
4. Adapt cultural references when necessary
5. Use natural expressions native to each target language

Translation guidelines:
- Preserve the emotional tone and style of the original text
- Use appropriate idiomatic expressions for each language
- Maintain consistent formality level across translations
- Consider cultural context and sensitivity
- Ensure translations sound natural to native speakers

For Asian languages (Chinese, Japanese, Korean):
- Pay attention to honorifics and politeness levels
- Consider cultural-specific expressions
- Maintain appropriate formality

For European languages:
- Consider formal vs informal pronouns (tu/vous, du/Sie, etc.)
- Adapt idioms appropriately
- Maintain gender agreement where applicable

Target languages:
{lang_list}

Format specification:
{format_instructions}

Remember: The goal is to produce translations that feel natural and authentic in each target language
while preserving the original message's intent.
""",
            ),
            (
                "human",
                """Translate this text:
{text}""",
            ),
        ]
    )

    chain = prompt.partial(format_instructions=parser.get_format_instructions(), lang_list=lang_list_str) | llm | parser

    result_dict = await chain.ainvoke({"text": text})

    return TranslationResult(**result_dict)


# Demo usage
if __name__ == "__main__":
    import asyncio

    async def translation_demo():
        """Translation demo"""
        print("\n=== Multilingual Translation Demo ===")

        target_languages = [LanguageCode.EN_US, LanguageCode.ZH_CN, LanguageCode.JA_JP, LanguageCode.FR_FR]

        # Example 1: English source
        text1 = "我爱你，亲爱姑娘"
        result1 = await translate(text1, target_languages)
        print("\nExample 1 - English source:")
        for t in result1.translations:
            print(f"{t.lang.name}: {t.text}")

        # Example 2: Chinese source
        text2 = "今天天气真好，我们去公园散步吧！"
        result2 = await translate(text2, target_languages)
        print("\nExample 2 - Chinese source:")
        for t in result2.translations:
            print(f"{t.lang.name}: {t.text}")

    asyncio.run(translation_demo())
