from langchain_core.language_models.chat_models import BaseChatModel
from ..config import settings


def get_llm(streaming: bool = False) -> BaseChatModel:
    if settings.aws_region and settings.aws_access_key_id:
        from langchain_aws import ChatBedrockConverse

        return ChatBedrockConverse(
            model=settings.bedrock_model,
            region_name=settings.aws_region,
            credentials_profile_name=None,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            aws_session_token=settings.aws_session_token or None,
        )
    else:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            streaming=streaming,
        )
