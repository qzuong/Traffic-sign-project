"""Reject speech when the model's crop lacks the expected sign-face evidence."""

import cv2
import numpy as np


_BLUE_MANDATORY_CLASSES = frozenset(range(33, 40))
_LIGHT_SPEED_FACE_CLASSES = frozenset((*range(9), 32))
_Y, _X = np.ogrid[:30, :30]
_RADIUS_SQUARED = (_X - 14.5) ** 2 + (_Y - 14.5) ** 2
_CENTRE = _RADIUS_SQUARED < 9**2
_OUTER = (_RADIUS_SQUARED >= 7**2) & (_RADIUS_SQUARED <= 15**2)


def speech_veto(rgb_tensor: np.ndarray, class_id: int) -> str | None:
    """Check the same RGB pixels that were sent to the CNN, without relabeling."""
    if class_id == 40:
        # A blue rectangular sign passed the color check as a roundabout.
        # Voice remains disabled for this class until a positive validation set exists.
        return "roundabout_voice_unverified"
    rgb = np.rint(rgb_tensor * 255).astype(np.uint8)
    hue, saturation, value = cv2.split(cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV))
    bright_neutral = (saturation <= 75) & (value >= 150)
    light_centre = float(bright_neutral[_CENTRE].mean())
    if light_centre < 0.20 and (value[_CENTRE] < 115).mean() >= 0.55:
        saturated_red = ((hue <= 11) | (hue >= 164)) & (saturation >= 75) & (value >= 60)
        if saturated_red[_OUTER].mean() >= 0.08:
            return "dark_red_sign_face"
    if class_id in _LIGHT_SPEED_FACE_CLASSES and light_centre < 0.35:
        return "speed_face_unverified"
    if class_id in _BLUE_MANDATORY_CLASSES:
        blue = (hue >= 89) & (hue <= 132) & (saturation >= 65) & (value >= 45)
        if blue[_CENTRE].mean() < 0.30:
            return "mandatory_blue_face_unverified"
    return None
