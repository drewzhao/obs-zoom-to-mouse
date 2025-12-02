"""
Easing Functions Module
Animation easing functions for smooth zoom transitions
"""

import math
from typing import Callable, Dict


def linear(t: float) -> float:
    """Linear interpolation - no easing."""
    return t


def ease_in_quad(t: float) -> float:
    """Quadratic ease-in."""
    return t * t


def ease_out_quad(t: float) -> float:
    """Quadratic ease-out."""
    return t * (2 - t)


def ease_in_out_quad(t: float) -> float:
    """Quadratic ease-in-out."""
    if t < 0.5:
        return 2 * t * t
    return -1 + (4 - 2 * t) * t


def ease_in_cubic(t: float) -> float:
    """Cubic ease-in."""
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out."""
    t -= 1
    return t * t * t + 1


def ease_in_out_cubic(t: float) -> float:
    """Cubic ease-in-out (default for smooth animations)."""
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


def ease_in_quart(t: float) -> float:
    """Quartic ease-in."""
    return t * t * t * t


def ease_out_quart(t: float) -> float:
    """Quartic ease-out."""
    t -= 1
    return 1 - t * t * t * t


def ease_in_out_quart(t: float) -> float:
    """Quartic ease-in-out."""
    if t < 0.5:
        return 8 * t * t * t * t
    t -= 1
    return 1 - 8 * t * t * t * t


def ease_in_quint(t: float) -> float:
    """Quintic ease-in."""
    return t * t * t * t * t


def ease_out_quint(t: float) -> float:
    """Quintic ease-out."""
    t -= 1
    return 1 + t * t * t * t * t


def ease_in_out_quint(t: float) -> float:
    """Quintic ease-in-out."""
    if t < 0.5:
        return 16 * t * t * t * t * t
    t -= 1
    return 1 + 16 * t * t * t * t * t


def ease_in_sine(t: float) -> float:
    """Sinusoidal ease-in."""
    return 1 - math.cos((t * math.pi) / 2)


def ease_out_sine(t: float) -> float:
    """Sinusoidal ease-out."""
    return math.sin((t * math.pi) / 2)


def ease_in_out_sine(t: float) -> float:
    """Sinusoidal ease-in-out."""
    return -(math.cos(math.pi * t) - 1) / 2


def ease_in_expo(t: float) -> float:
    """Exponential ease-in."""
    if t == 0:
        return 0
    return pow(2, 10 * (t - 1))


def ease_out_expo(t: float) -> float:
    """Exponential ease-out."""
    if t == 1:
        return 1
    return 1 - pow(2, -10 * t)


def ease_in_out_expo(t: float) -> float:
    """Exponential ease-in-out."""
    if t == 0:
        return 0
    if t == 1:
        return 1
    if t < 0.5:
        return pow(2, 20 * t - 10) / 2
    return (2 - pow(2, -20 * t + 10)) / 2


def ease_in_circ(t: float) -> float:
    """Circular ease-in."""
    return 1 - math.sqrt(1 - t * t)


def ease_out_circ(t: float) -> float:
    """Circular ease-out."""
    t -= 1
    return math.sqrt(1 - t * t)


def ease_in_out_circ(t: float) -> float:
    """Circular ease-in-out."""
    if t < 0.5:
        return (1 - math.sqrt(1 - pow(2 * t, 2))) / 2
    return (math.sqrt(1 - pow(-2 * t + 2, 2)) + 1) / 2


def ease_in_back(t: float) -> float:
    """Back ease-in (overshoots then returns)."""
    c1 = 1.70158
    c3 = c1 + 1
    return c3 * t * t * t - c1 * t * t


def ease_out_back(t: float) -> float:
    """Back ease-out (overshoots then returns)."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def ease_in_out_back(t: float) -> float:
    """Back ease-in-out."""
    c1 = 1.70158
    c2 = c1 * 1.525
    if t < 0.5:
        return (pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2
    return (pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2


def elastic(t: float) -> float:
    """Elastic ease-out (bouncy overshoot)."""
    if t == 0 or t == 1:
        return t
    c4 = (2 * math.pi) / 3
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def ease_in_elastic(t: float) -> float:
    """Elastic ease-in."""
    if t == 0 or t == 1:
        return t
    c4 = (2 * math.pi) / 3
    return -pow(2, 10 * t - 10) * math.sin((t * 10 - 10.75) * c4)


def ease_out_elastic(t: float) -> float:
    """Elastic ease-out."""
    return elastic(t)


def ease_in_out_elastic(t: float) -> float:
    """Elastic ease-in-out."""
    if t == 0 or t == 1:
        return t
    c5 = (2 * math.pi) / 4.5
    if t < 0.5:
        return -(pow(2, 20 * t - 10) * math.sin((20 * t - 11.125) * c5)) / 2
    return (pow(2, -20 * t + 10) * math.sin((20 * t - 11.125) * c5)) / 2 + 1


def bounce_out(t: float) -> float:
    """Bounce ease-out."""
    n1 = 7.5625
    d1 = 2.75
    
    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


def bounce_in(t: float) -> float:
    """Bounce ease-in."""
    return 1 - bounce_out(1 - t)


def bounce(t: float) -> float:
    """Bounce ease-out (alias)."""
    return bounce_out(t)


def ease_in_out_bounce(t: float) -> float:
    """Bounce ease-in-out."""
    if t < 0.5:
        return (1 - bounce_out(1 - 2 * t)) / 2
    return (1 + bounce_out(2 * t - 1)) / 2


# Dictionary of all available easing functions
EASING_FUNCTIONS: Dict[str, Callable[[float], float]] = {
    # Linear
    'linear': linear,
    
    # Quadratic
    'ease_in': ease_in_quad,
    'ease_out': ease_out_quad,
    'ease_in_out': ease_in_out_cubic,  # Default ease_in_out is cubic
    'ease_in_quad': ease_in_quad,
    'ease_out_quad': ease_out_quad,
    'ease_in_out_quad': ease_in_out_quad,
    
    # Cubic
    'ease_in_cubic': ease_in_cubic,
    'ease_out_cubic': ease_out_cubic,
    'ease_in_out_cubic': ease_in_out_cubic,
    
    # Quartic
    'ease_in_quart': ease_in_quart,
    'ease_out_quart': ease_out_quart,
    'ease_in_out_quart': ease_in_out_quart,
    
    # Quintic
    'ease_in_quint': ease_in_quint,
    'ease_out_quint': ease_out_quint,
    'ease_in_out_quint': ease_in_out_quint,
    
    # Sinusoidal
    'ease_in_sine': ease_in_sine,
    'ease_out_sine': ease_out_sine,
    'ease_in_out_sine': ease_in_out_sine,
    
    # Exponential
    'ease_in_expo': ease_in_expo,
    'ease_out_expo': ease_out_expo,
    'ease_in_out_expo': ease_in_out_expo,
    
    # Circular
    'ease_in_circ': ease_in_circ,
    'ease_out_circ': ease_out_circ,
    'ease_in_out_circ': ease_in_out_circ,
    
    # Back (overshoot)
    'ease_in_back': ease_in_back,
    'ease_out_back': ease_out_back,
    'ease_in_out_back': ease_in_out_back,
    
    # Elastic
    'elastic': elastic,
    'ease_in_elastic': ease_in_elastic,
    'ease_out_elastic': ease_out_elastic,
    'ease_in_out_elastic': ease_in_out_elastic,
    
    # Bounce
    'bounce': bounce,
    'bounce_in': bounce_in,
    'bounce_out': bounce_out,
    'ease_in_out_bounce': ease_in_out_bounce,
}


def get_easing(name: str) -> Callable[[float], float]:
    """
    Get an easing function by name.
    
    Args:
        name: Name of the easing function
        
    Returns:
        The easing function, or linear if not found
    """
    return EASING_FUNCTIONS.get(name, linear)


def lerp(start: float, end: float, t: float) -> float:
    """
    Linear interpolation between two values.
    
    Args:
        start: Start value
        end: End value
        t: Progress (0-1)
        
    Returns:
        Interpolated value
    """
    return start + (end - start) * t


def lerp_eased(start: float, end: float, t: float, easing: str = 'linear') -> float:
    """
    Eased interpolation between two values.
    
    Args:
        start: Start value
        end: End value
        t: Progress (0-1)
        easing: Name of easing function to use
        
    Returns:
        Interpolated value with easing applied
    """
    ease_func = get_easing(easing)
    return lerp(start, end, ease_func(t))


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value between min and max.
    
    Args:
        value: Value to clamp
        min_val: Minimum value
        max_val: Maximum value
        
    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))

