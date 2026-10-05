"""
Configuration for NVIDIA NIM integration.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class NIMConfig(BaseModel):
    """Configuration for NVIDIA NIM API client."""
    
    api_key: str = Field(
        ...,
        description="NVIDIA API key (from environment variable)"
    )
    
    base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        description="NVIDIA NIM API base URL"
    )
    
    model: str = Field(
        ...,
        description="Model identifier (e.g., 'meta/llama-3.1-70b-instruct')"
    )
    
    enabled: bool = Field(
        default=False,
        description="Whether NIM is enabled"
    )
    
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Request timeout in seconds"
    )
    
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retries for retryable errors"
    )
    
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0 = deterministic)"
    )
    
    max_tokens: int = Field(
        default=4096,
        ge=1,
        description="Maximum output tokens"
    )
    
    @classmethod
    def from_env(cls) -> "NIMConfig":
        """
        Load NIM configuration from environment variables.
        
        Automatically loads .env file if present, so callers don't need
        to manually export environment variables.
        
        Returns:
            NIMConfig instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        # Load .env file (no-op if already loaded or file doesn't exist)
        load_dotenv()
        
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY environment variable is required")
        
        model = os.getenv("NVIDIA_NIM_MODEL")
        if not model:
            raise ValueError("NVIDIA_NIM_MODEL environment variable is required")
        
        return cls(
            api_key=api_key,
            base_url=os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            model=model,
            enabled=os.getenv("NVIDIA_NIM_ENABLED", "false").lower() == "true",
            timeout_seconds=int(os.getenv("NVIDIA_NIM_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("NVIDIA_NIM_MAX_RETRIES", "3")),
            temperature=float(os.getenv("NVIDIA_NIM_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("NVIDIA_NIM_MAX_TOKENS", "4096")),
        )
    
    @classmethod
    def try_from_env(cls) -> Optional["NIMConfig"]:
        """
        Try to load NIM configuration from environment.
        
        Returns:
            NIMConfig if available, None otherwise
        """
        try:
            return cls.from_env()
        except ValueError:
            return None
