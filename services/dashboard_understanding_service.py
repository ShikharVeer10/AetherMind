"""
Dashboard Understanding Service
Specialized service for extracting KPI cards, panels, and metrics.
"""

from typing import List, Optional
from models.document_model import SlideModel, DashboardModel

class DashboardUnderstandingService:
    def extract_dashboard(self, slide: SlideModel) -> Optional[DashboardModel]:
        """
        Extracts complex dashboards into panels and metrics.
        """
        # This ties into the existing DashboardExtractionAgent logic
        from agents.structural_understanding_agents import DashboardExtractionAgent
        agent = DashboardExtractionAgent()
        return agent.run(slide)
