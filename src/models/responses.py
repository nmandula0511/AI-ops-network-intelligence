"""
models/responses.py
===================
Story 2 — Pydantic Models

All response models coming OUT of the agent.
NetOrchestrator reads these to synthesize the answer to the NOC engineer.

AI IDE NOTE:
- Severity levels: GREEN / YELLOW / RED (match threshold logic)
- GREEN:  0-60 min on LTE
- YELLOW: 60-90 min on LTE
- RED:    90+ min on LTE
- requires_truck_roll should be False for 95%+ of cases — this is the WHOLE POINT
"""

import logging
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal
from datetime import datetime

logger = logging.getLogger("aiops.responses")


class DeviceAnalysisResponse(BaseModel):
    """Analysis result for a single SmartEdge Gateway device."""
    
    device_id: str
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Severity — maps directly to business thresholds
    severity: Literal["GREEN", "YELLOW", "RED"]
    lte_duration_minutes: int = Field(..., ge=0)
    
    # Root cause diagnosis
    root_cause: str = Field(
        ...,
        description="Specific reason the device is stuck on LTE. "
                    "Examples: 'Cable modem still offline', "
                    "'Firmware bug v3.1.x fails auto-reconnect', "
                    "'Customer rebooted modem but device not refreshed'"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Agent confidence in root cause diagnosis (0.0 - 100.0)"
    )
    
    # Recommended action
    recommended_action: str = Field(
        ...,
        description="Primary recommended action. Start with self-service."
    )
    action_steps: list[str] = Field(
        default_factory=list,
        description="Step-by-step instructions. Ordered by least to most disruptive."
    )
    estimated_resolution_minutes: int = Field(
        ...,
        ge=0,
        description="Estimated time for customer to resolve, in minutes"
    )
    
    # Truck roll decision — the critical business metric
    requires_truck_roll: bool = Field(
        ...,
        description="Only True if ALL self-service options have been exhausted. "
                    "Truck rolls are expensive. Default assumption: False."
    )
    truck_roll_reason: Optional[str] = Field(
        None,
        description="Required if requires_truck_roll=True. Explain why self-service failed."
    )
    
    # Cost context
    estimated_daily_cost_usd: Optional[float] = Field(
        None,
        description="Estimated daily cost while device stays on LTE"
    )

    @model_validator(mode="after")
    def compare_ai_and_math_rules(self) -> "DeviceAnalysisResponse":
        """
        Validator comparing the LLM AI confidence score with rule-based mathematical scoring.
        Logs a divergence warning if they differ by more than 30 points.
        """
        # Hard rule-based mathematical scoring logic:
        # Expected confidence score under mathematical heuristics:
        expected_score = 80.0
        
        # Rule 1: If it's a simple green state, confidence should be near 100
        if self.lte_duration_minutes < 60 and self.severity == "GREEN":
            expected_score = 100.0
        # Rule 2: If the modem is offline, we are extremely confident that is the root cause
        elif "offline" in self.root_cause.lower():
            expected_score = 95.0
        # Rule 3: Firmware bugs have standard high confidence mapping
        elif "firmware" in self.root_cause.lower():
            expected_score = 90.0
        
        # Compare and log divergence warning
        divergence = abs(self.confidence_score - expected_score)
        if divergence > 30.0:
            logger.warning(
                f"[DIVERGENCE WARNING] AI confidence score ({self.confidence_score}%) "
                f"diverges from rule-based mathematical score ({expected_score}%) "
                f"for device {self.device_id}. Delta: {divergence}%"
            )
            print(
                f"⚠️ [DIVERGENCE WARNING] AI confidence ({self.confidence_score}%) "
                f"diverges from math rule score ({expected_score}%) for {self.device_id}!"
            )
            
        return self


class BulkAnalysisResponse(BaseModel):
    """Response for bulk device analysis."""
    
    total_devices_analyzed: int
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Summary counts
    green_count: int = 0
    yellow_count: int = 0
    red_count: int = 0
    
    # Details for YELLOW and RED only (GREEN devices are fine)
    devices_needing_attention: list[DeviceAnalysisResponse]
    
    # Aggregate business impact
    total_estimated_daily_cost_usd: float = 0.0
    truck_rolls_required: int = 0
    
    # Recommended priorities
    priority_actions: list[str] = Field(
        default_factory=list,
        description="Top 3-5 actions to take right now, ordered by impact"
    )


class A2ATaskResponse(BaseModel):
    """
    A2A protocol task response sent back to NetOrchestrator.
    
    DO NOT change the structure — the Orchestrator parses this exact format.
    """
    
    id: str
    sessionId: Optional[str] = None
    status: dict = Field(
        default_factory=lambda: {"state": "completed"}
    )
    artifacts: list[dict] = Field(default_factory=list)

    @classmethod
    def from_analysis(
        cls,
        task_id: str,
        session_id: str,
        analysis: DeviceAnalysisResponse
    ) -> "A2ATaskResponse":
        """Helper to build a proper A2A response from an analysis result."""
        return cls(
            id=task_id,
            sessionId=session_id,
            status={"state": "completed"},
            artifacts=[{
                "name": "analysis_result",
                "parts": [
                    {
                        "type": "data",
                        "data": analysis.model_dump()
                    }
                ]
            }]
        )

