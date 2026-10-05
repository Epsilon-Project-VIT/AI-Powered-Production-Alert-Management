"""
Configuration settings for Stage 1 & Stage 2 pipelines.
"""

from pathlib import Path
import os
from typing import List, Dict, Pattern
import re


class Settings:
    """Configuration for Stage 1 & Stage 2 pipelines."""
    
    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    EXCEL_FILE_PATH = DATA_DIR / "raw" / "Data_Alert_Ticket_Segregation.xlsx"
    PROCESSED_DATA_DIR = DATA_DIR / "processed"
    MODELS_DIR = PROJECT_ROOT / "models"
    STAGE2_MODELS_DIR = MODELS_DIR / "stage2"
    
    # Required fields for standardized alert
    REQUIRED_FIELDS = [
        "alert_id",
        "created_at",
        "client",
        "raw_description"
    ]
    
    # Excel column mappings
    EXCEL_COLUMN_MAPPING = {
        "Number": "alert_id",
        "Created": "created_at",
        "Impacted client": "client",
        "Short description": "raw_description"
    }
    
    # Normalization patterns (regex patterns for dynamic value replacement)
    NORMALIZATION_PATTERNS: List[tuple[Pattern, str]] = [
        # Timestamps - various formats
        (re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?'), '<timestamp>'),
        (re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'), '<timestamp>'),
        (re.compile(r'\d{2}-[A-Z]{3}-\d{4}'), '<timestamp>'),  # e.g., 24-JUL-2026
        
        # IP addresses
        (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '<ip>'),
        (re.compile(r'ip-(?:\d{1,3}-){3}\d{1,3}'), '<ip>'),
        
        # UUIDs
        (re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.IGNORECASE), '<uuid>'),
        
        # Request IDs and hexadecimal IDs
        (re.compile(r'\b[0-9a-f]{16,}\b', re.IGNORECASE), '<id>'),
        (re.compile(r'request[_\s]?id[:\s]+[0-9a-zA-Z-]+', re.IGNORECASE), 'request_id <id>'),
        
        # Large numeric IDs (more than 6 digits)
        (re.compile(r'\b\d{7,}\b'), '<id>'),
        
        # Priority markers (P1, P2, P3, P4) - preserve distinction, normalize format
        # Match P followed by digit (1-4) and replace with lowercase standardized form
        # This preserves the semantic difference between P1 vs P2 vs P3 vs P4
        (re.compile(r'P([1-4])(?=[A-Z_]|\b)'), r'p\1'),
    ]
    
    # Fields to exclude from metadata (empty or not useful)
    EXCLUDE_FIELDS = [
        "Activity due",
        "Additional assignee list",
        "Approval history",
        "Approval set"
    ]
    
    # CRITICAL: Target/Post-Resolution Fields - FORBIDDEN in Stage 2 metadata
    # These fields are outcomes/targets and must NOT be used as input features
    FORBIDDEN_METADATA_FIELDS = [
        # Stage 2 Targets (supervised learning targets)
        "Priority",                    # Target for Stage 2 priority prediction
        "Assignment group",            # Target for Stage 2 routing prediction
        
        # Post-Triage/Resolution Outcomes (data leakage)
        "Assigned to",                 # Who resolved it (post-triage)
        "Resolved",                    # Resolution timestamp (outcome)
        "Resolved by",                 # Who resolved it (outcome)
        "Resolution code",             # Resolution outcome
        "Resolve time",                # Time to resolve (outcome)
        "Business duration",           # Duration metric (outcome)
        
        # Post-Triage Metrics (data leakage)
        "Assigned to count",           # Post-triage metric
        "Reassignment count",          # Post-triage metric
        "Reopen count",                # Post-triage metric
        
        # Approval/Resolution Fields (outcomes)
        "Approval",                    # Approval status
        "Approval history",            # Approval outcome
        "Approval set",                # Approval configuration
    ]
    
    # Arrival-Time-Safe Fields - ALLOWED in Stage 2 metadata
    # These fields are known at alert arrival time and safe to use as features
    ALLOWED_METADATA_FIELDS = [
        "Active",                      # Alert status at arrival
        "Number",                      # Alert ID (duplicate of alert_id)
    ]
    
    # Stage 2 Configuration
    STAGE2_CONFIDENCE_THRESHOLD = 0.70  # Configurable threshold for high-confidence predictions
    STAGE2_DEFAULT_MODEL_TYPE = 'tfidf_lr'  # Primary model architecture
    CLASSIFICATION_PROVIDER = os.getenv("CLASSIFICATION_PROVIDER", "ml").lower()
    
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist."""
        cls.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        cls.STAGE2_MODELS_DIR.mkdir(parents=True, exist_ok=True)
