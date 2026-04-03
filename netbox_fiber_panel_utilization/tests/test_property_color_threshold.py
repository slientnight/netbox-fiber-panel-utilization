"""Property-based tests for color threshold mapping.

# Feature: fiber-patch-panel-utilization, Property 2: Color threshold mapping

**Validates: Requirements 1.6, 5.5**

Property 2: For any utilization percentage p (0.0 <= p <= 100.0) and any valid
threshold pair (warning_threshold < critical_threshold, both in 0-100), the
assigned color SHALL be:
- green when p < warning_threshold
- yellow when warning_threshold <= p < critical_threshold
- red when p >= critical_threshold

Since the color logic is implemented in JavaScript (utilization.js), we mirror
the JS logic in a Python function and test that function with Hypothesis. This
validates the specification/algorithm, not the JS implementation directly.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Mirror of JS color threshold logic
# ---------------------------------------------------------------------------

def get_color_class(utilization: float, warning: float, critical: float) -> str:
    """Mirror the JS color threshold logic from utilization.js."""
    if utilization >= critical:
        return "utilization-red"
    elif utilization >= warning:
        return "utilization-yellow"
    else:
        return "utilization-green"


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

@st.composite
def threshold_pair(draw):
    """Generate a valid (warning, critical) pair where 0 <= warning < critical <= 100."""
    warning = draw(st.floats(min_value=0.0, max_value=99.0, allow_nan=False, allow_infinity=False))
    critical = draw(st.floats(min_value=warning + 0.01, max_value=100.0, allow_nan=False, allow_infinity=False))
    return warning, critical


utilization_strategy = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestColorThresholdMapping:
    """Property 2: Color threshold mapping."""

    @given(utilization=utilization_strategy, thresholds=threshold_pair())
    @settings(max_examples=100)
    def test_green_when_below_warning(self, utilization, thresholds):
        """Color is green when utilization < warning_threshold."""
        warning, critical = thresholds
        if utilization < warning:
            assert get_color_class(utilization, warning, critical) == "utilization-green"

    @given(utilization=utilization_strategy, thresholds=threshold_pair())
    @settings(max_examples=100)
    def test_yellow_when_between_warning_and_critical(self, utilization, thresholds):
        """Color is yellow when warning_threshold <= utilization < critical_threshold."""
        warning, critical = thresholds
        if warning <= utilization < critical:
            assert get_color_class(utilization, warning, critical) == "utilization-yellow"

    @given(utilization=utilization_strategy, thresholds=threshold_pair())
    @settings(max_examples=100)
    def test_red_when_at_or_above_critical(self, utilization, thresholds):
        """Color is red when utilization >= critical_threshold."""
        warning, critical = thresholds
        if utilization >= critical:
            assert get_color_class(utilization, warning, critical) == "utilization-red"

    @given(utilization=utilization_strategy, thresholds=threshold_pair())
    @settings(max_examples=100)
    def test_exactly_one_color_assigned(self, utilization, thresholds):
        """Exactly one color class is assigned for any valid input."""
        warning, critical = thresholds
        color = get_color_class(utilization, warning, critical)
        assert color in {"utilization-green", "utilization-yellow", "utilization-red"}

    @given(utilization=utilization_strategy, thresholds=threshold_pair())
    @settings(max_examples=100)
    def test_color_boundaries_are_exhaustive(self, utilization, thresholds):
        """The three color regions cover the entire 0-100 range without gaps."""
        warning, critical = thresholds
        color = get_color_class(utilization, warning, critical)

        if utilization < warning:
            assert color == "utilization-green"
        elif utilization < critical:
            assert color == "utilization-yellow"
        else:
            assert color == "utilization-red"
