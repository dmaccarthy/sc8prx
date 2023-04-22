# Copyright 2015-2023 D.G. MacCarthy <https://dmaccarthy.github.io/sc8pr>
#
# This file is part of "sc8prx".
#
# "sc8prx" is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# "sc8prx" is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "sc8prx".  If not, see <http://www.gnu.org/licenses/>.

"Additional features depending on Pillow"

import pygame, PIL.ImageGrab
from sc8pr import Image
from sc8pr.util import hasAlpha, surface

def pil_image(srf, mode=None):
    "Convert surface to PIL.Image"
    srf = surface(srf)
    if mode is None: mode = "RGBA" if hasAlpha(srf) else "RGB"
    return PIL.Image.frombytes(mode, srf.get_size(), pygame.image.tostring(srf, mode))


class Grabber:
    "A class for performing screen captures using PIL.ImageGrab.grab"

    def __init__(self, rect=None):
        self.grab = PIL.ImageGrab.grab
        if rect and not isinstance(rect, pygame.Rect):
            if len(rect) == 2: rect = (0, 0), rect
            rect = pygame.Rect(rect)
        self.rect = rect

    @property
    def bbox(self):
        "Bounding box for capture"
        r = self.rect
        if r: return [r.left, r.top, r.right, r.bottom]

    @property
    def pil(self): return self.grab(self.bbox)

    @property
    def img(self): return Image(self.srf)

    @property
    def rgba(self): return self.img.rgba

    @property
    def srf(self): return surface(self.grab(self.bbox))
