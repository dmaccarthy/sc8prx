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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with "sc8prx". If not, see <http://www.gnu.org/licenses/>.

"Convert Image to Pillow image format"

from sc8pr import Image
from sc8pr.util import surface
import PIL.Image

def pil(img):
    "Convert surface to PIL.Image"
    srf = surface(img)
    mode = "RGBA" if srf.get_bitsize() == 32 else "RGB"
    return PIL.Image.frombytes(mode, srf.get_size(), Image(srf).bytesTuple(False))
