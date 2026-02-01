"""Performance tests for Dashboard Service."""
import time
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.dashboard.service import DashboardService


class TestDashboardPerformance:
    """Performance tests for dashboard service."""

    async def test_dashboard_query_performance(
        self, db_session: AsyncSession
    ):
        """Test that dashboard completes in reasonable time."""
        service = DashboardService(db_session)
        
        start_time = time.time()
        result = await service.get_summary()
        elapsed = time.time() - start_time
        
        # Should complete quickly even with empty DB
        # Optimized version should be < 1 second
        assert elapsed < 1.0, f"Dashboard took {elapsed:.3f}s, expected < 1.0s"
        assert result is not None
        assert "active_students_count" in result
        assert "total_revenue_this_year" in result
        assert "current_year" in result
        
        print(f"\n✓ Dashboard loaded in {elapsed:.3f}s")

