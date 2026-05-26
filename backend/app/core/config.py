from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_csv(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


class Settings(BaseSettings):
    app_name: str = "QuantA-Share API"
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(..., alias="DATABASE_URL")

    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    nuwax_api_key: str = Field("", alias="NUWAX_API_KEY")
    nuwax_base_url: str = Field("https://nuwax.com", alias="NUWAX_BASE_URL")
    nuwax_agent_id: str = Field(
        "/space/53244875/agent/33277806", alias="NUWAX_AGENT_ID"
    )
    deepseek_api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        "https://api.deepseek.com", alias="DEEPSEEK_BASE_URL"
    )
    deepseek_model: str = Field("deepseek-v4-flash", alias="DEEPSEEK_MODEL")
    deepseek_timeout_seconds: int = Field(60, alias="DEEPSEEK_TIMEOUT_SECONDS")

    github_models_api_key: str = Field("", alias="GITHUB_MODELS_API_KEY")
    github_models_base_url: str = Field(
        "https://models.github.ai/inference", alias="GITHUB_MODELS_BASE_URL"
    )
    github_models_model: str = Field("openai/gpt-4o", alias="GITHUB_MODELS_MODEL")
    github_models_timeout_seconds: int = Field(
        60, alias="GITHUB_MODELS_TIMEOUT_SECONDS"
    )
    tavily_api_key: str = Field("", alias="TAVILY_API_KEY")
    brave_api_key: str = Field("", alias="BRAVE_API_KEY")

    cors_allow_origins: str = Field(
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500,http://localhost:5500",
        alias="CORS_ALLOW_ORIGINS",
    )
    smtp_host: str = Field("", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str = Field("", alias="SMTP_USER")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(True, alias="SMTP_USE_TLS")
    smtp_from_email: str = Field("", alias="SMTP_FROM_EMAIL")
    billing_public_base_url: str = Field(
        "http://127.0.0.1:8000", alias="BILLING_PUBLIC_BASE_URL"
    )
    # 前端页面基础地址，用于支付完成后的 returnUrl 跳转
    # 本地开发填 http://127.0.0.1:5500，部署后填域名
    frontend_base_url: str = Field("", alias="FRONTEND_BASE_URL")
    # 支付FM 配置（商户后台"用户中心"页面查看）
    zhifufm_api_url: str = Field(
        "", alias="ZHIFUFM_API_URL"
    )  # 接口根地址，如 https://xxx.com
    zhifufm_merchant_num: str = Field("", alias="ZHIFUFM_MERCHANT_NUM")  # 商户号
    zhifufm_secret: str = Field("", alias="ZHIFUFM_SECRET")  # 接入密钥
    zhifufm_pay_type: str = Field(
        "aloop", alias="ZHIFUFM_PAY_TYPE"
    )  # 支付方式，推荐 aloop 或 tloop
    zhifufm_notify_url: str = Field(
        "", alias="ZHIFUFM_NOTIFY_URL"
    )  # 公网可访问的回调地址
    # 管理员 API 密钥（用于手动确认打赏订单等）
    admin_secret: str = Field(..., alias="ADMIN_SECRET")
    # 扫描器首次延迟（秒），默认 60；设 0 立即开始
    scanner_first_delay_seconds: int = Field(10, alias="SCANNER_FIRST_DELAY_SECONDS")
    # 设为 1 跳过启动时的首次全量扫描
    skip_initial_scan: int = Field(0, alias="SKIP_INITIAL_SCAN")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return _parse_csv(self.cors_allow_origins)


settings = Settings()
