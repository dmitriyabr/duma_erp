from decimal import Decimal

import pytest

from src.shared.utils.money import round_money


class TestRoundMoney:
    """Tests for round_money function."""

    def test_round_half_up(self):
        """Test ROUND_HALF_UP behavior."""
        assert round_money(10.125) == Decimal("10.13")
        assert round_money(10.124) == Decimal("10.12")
        assert round_money(10.115) == Decimal("10.12")  # banker's rounding edge case
        assert round_money(10.145) == Decimal("10.15")

    def test_from_decimal(self):
        """Test rounding from Decimal input."""
        assert round_money(Decimal("10.125")) == Decimal("10.13")
        assert round_money(Decimal("99.999")) == Decimal("100.00")

    def test_from_string(self):
        """Test rounding from string input."""
        assert round_money("10.125") == Decimal("10.13")
        assert round_money("0.001") == Decimal("0.00")

    def test_from_int(self):
        """Test rounding from int input."""
        assert round_money(100) == Decimal("100.00")
        assert round_money(0) == Decimal("0.00")

    def test_negative_numbers(self):
        """Test rounding negative numbers."""
        assert round_money(-10.125) == Decimal("-10.12")  # rounds toward zero
        assert round_money(-10.126) == Decimal("-10.13")

    def test_precision(self):
        """Test that result always has 2 decimal places."""
        result = round_money(10)
        assert str(result) == "10.00"

        result = round_money(10.1)
        assert str(result) == "10.10"
