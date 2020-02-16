# MIT License
#
# Copyright (c) 2019 Robert Gützkow
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import colors


def map_to_range(x, in_min, in_max, out_min, out_max, clip=True):
    """
    Maps a value from one range to another.
    :param x: Input value
    :param in_min: Input range minimum
    :param in_max: Input range maximum
    :param out_min: Output range minimum
    :param out_max: Output range maximum
    :param clip: If True, clip the input value x to the input range limits
    :return: Mapped value in the output range
    """
    if clip:
        x = min(in_max, max(in_min, x))
    if in_min > in_max or out_min > out_max:
        raise ValueError("Minimum has to be smaller or equal to the maximum")
    return out_min + ((x - in_min) * (out_max - out_min)) / (in_max - in_min)


def map_to_colormap_range(x, exponent_min, exponent_max):
    """
    Shifts and scales input from range [0.0, 1.0] in order to project middle grey to 0.5
    and also keep all values within the [0.0, 1.0] range.
    :param x: Input value from range [0.0, 1.0]
    :param exponent_min: Smallest exponent for input values
    :param exponent_max: Largest exponent for input values
    :return: Mapped value in colormap range
    """
    # Map middle grey 0.18 to the center of the colormap
    center = colors.normalize_value(0.18, exponent_min, exponent_max)

    # colormap range is [0.0, 1.0]
    distance_a = center
    distance_b = 1.0 - center

    if distance_a >= distance_b:
        return map_to_range(x, center - distance_a, center + distance_a, 0.0, 1.0)
    else:
        return map_to_range(x, center - distance_b, center + distance_b, 0.0, 1.0)
