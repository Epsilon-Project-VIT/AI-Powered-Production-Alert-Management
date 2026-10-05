#!/usr/bin/env python3
"""
NVIDIA NIM GLM-5.3 Connectivity Test

Tests basic connectivity to NVIDIA NIM using the configured GLM-5.3 model.
Does NOT print API keys or secrets.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
from openai import OpenAI

# Load .env file so we don't require manual `source .env`
load_dotenv()



def test_nim_connection():
    """Test NVIDIA NIM connectivity with GLM-5.3."""
    
    print("="*60)
    print("NVIDIA NIM GLM-5.3 Connectivity Test")
    print("="*60)
    
    # Load configuration
    api_key = os.getenv("NVIDIA_API_KEY")
    model = os.getenv("NVIDIA_NIM_MODEL", "z-ai/glm-5.3-flash")
    base_url = os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    enabled = os.getenv("NVIDIA_NIM_ENABLED", "false").lower() == "true"
    
    print(f"\nConfiguration:")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print(f"  API Key: {'✓ Loaded' if api_key else '✗ Missing'}")
    print(f"  NIM Enabled: {enabled}")
    
    # Check prerequisites
    if not api_key:
        print("\n✗ FAILED: NVIDIA_API_KEY environment variable not set")
        print("  Set it with: export NVIDIA_API_KEY=your_key_here")
        return False
    
    if not enabled:
        print("\n⚠ WARNING: NVIDIA_NIM_ENABLED=false")
        print("  Set NVIDIA_NIM_ENABLED=true to enable NIM")
    
    # Test connection
    print(f"\nTesting connection to {base_url}...")
    
    try:
        client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        
        # Simple test prompt
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Which number is larger, 9.11 or 9.8? Answer with only the number."}
            ],
            temperature=0.0,
            max_tokens=10,
            timeout=30
        )
        
        answer = response.choices[0].message.content.strip()
        
        print(f"\n✓ SUCCESS: Connected to NVIDIA NIM")
        print(f"  Response: {answer}")
        print(f"  Model: {response.model}")
        
        # Validate response makes sense
        if "9.8" in answer or "9.11" in answer:
            print(f"  Validation: ✓ Response contains expected answer")
        else:
            print(f"  Validation: ⚠ Unexpected response format")
        
        return True
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        # Don't print full error if it contains secrets
        if "nvapi-" in error_msg or api_key in error_msg:
            error_msg = "[Error contains sensitive data, not displayed]"
        
        print(f"\n✗ FAILED: {error_type}")
        print(f"  Error: {error_msg[:200]}")
        
        if "401" in error_msg or "403" in error_msg:
            print(f"  Hint: API key may be invalid or expired")
        elif "404" in error_msg:
            print(f"  Hint: Model '{model}' may not be available")
        elif "timeout" in error_msg.lower():
            print(f"  Hint: Request timed out, check network connectivity")
        
        return False


if __name__ == "__main__":
    print()
    success = test_nim_connection()
    print("\n" + "="*60)
    
    if success:
        print("STATUS: ✓ PASS")
        sys.exit(0)
    else:
        print("STATUS: ✗ FAIL")
        sys.exit(1)
