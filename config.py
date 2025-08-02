"""Configuration management for Marketing Agent system."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # OpenRouter Configuration
    openrouter_api_key: str = Field(..., env="OPENROUTER_API_KEY")
    
    # LangSmith Configuration  
    langchain_tracing_v2: bool = Field(True, env="LANGCHAIN_TRACING_V2")
    langchain_api_key: Optional[str] = Field(None, env="LANGCHAIN_API_KEY")
    langchain_project: str = Field("marketing-agent", env="LANGCHAIN_PROJECT")
    
    # Supabase Configuration
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_key: str = Field(..., env="SUPABASE_KEY")
    
    # Meta/Facebook Ads Configuration
    meta_access_token: str = Field(..., env="META_ACCESS_TOKEN")
    meta_app_id: str = Field(..., env="META_APP_ID")
    meta_app_secret: str = Field(..., env="META_APP_SECRET")
    meta_ad_account_id: str = Field(..., env="META_AD_ACCOUNT_ID")
    
    # Google Ads Configuration
    google_ads_developer_token: str = Field(..., env="GOOGLE_ADS_DEVELOPER_TOKEN")
    google_ads_client_id: str = Field(..., env="GOOGLE_ADS_CLIENT_ID")
    google_ads_client_secret: str = Field(..., env="GOOGLE_ADS_CLIENT_SECRET")
    google_ads_refresh_token: str = Field(..., env="GOOGLE_ADS_REFRESH_TOKEN")
    google_ads_customer_id: str = Field(..., env="GOOGLE_ADS_CUSTOMER_ID")
    
    # Image Generation
    stability_api_key: Optional[str] = Field(None, env="STABILITY_API_KEY")
    
    # App Configuration
    environment: str = Field("development", env="ENVIRONMENT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    human_approval_required: bool = Field(True, env="HUMAN_APPROVAL_REQUIRED")
    
    # Performance Thresholds
    ctr_threshold: float = Field(0.02, env="CTR_THRESHOLD")
    cpc_threshold: float = Field(2.00, env="CPC_THRESHOLD")
    roas_threshold: float = Field(3.00, env="ROAS_THRESHOLD")
    daily_budget_limit: float = Field(1000.0, env="DAILY_BUDGET_LIMIT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Setup LangSmith if configured
if settings.langchain_api_key:
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langchain_tracing_v2)
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project 