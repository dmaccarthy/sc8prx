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

"FFmpeg encoding and decoding using imageio/imageio-ffmpeg"

import os, numpy, imageio
from json import dumps
from zipfile import ZipFile, ZIP_DEFLATED
from sc8pr import Image
from sc8pr.misc.video import Video, _open_list
from sc8prx import pil

class _FF:

    @staticmethod
    def ffmpeg(ff): os.environ["IMAGEIO_FFMPEG_EXE"] = ff

    def __enter__(self): return self
    
    def close(self, *args):
        self._io.close()
        if self in _open_list: _open_list.remove(self)

    __exit__ = close


class Reader(_FF):
    "Read images directly from a media file using imageio/FFmpeg"

    read_alpha = None

    def __init__(self, src, **kwargs):
        self._io = imageio.get_reader(src, **kwargs)
        _open_list.append(self)
        self._iter = iter(self._io)
        self._meta = self._io.get_meta_data()
        size = kwargs.get("size")
        if size is None: size = self._meta["size"]
        self._info = size, "RGB" #struct.pack("!3I", 0, *size)

    @property
    def meta(self): return self._meta
    
    def __next__(self):
        "Return the next frame as an Image instance"
        return Image.fromBytes((bytes(next(self._iter)), self._info)).convert(self.read_alpha)

    def __iter__(self):
        "Iterate through all frames returning data as Image instances"
        try:
            while True: yield next(self)
        except StopIteration: pass

    def read(self, n=None):
        try:
            while n is None or n > 0:
                img = next(self)
                if n is not None: n -= 1
                yield img
        except StopIteration: pass

    def skip(self, n):
        "Read and discard n frames"
        while n:
            try:
                next(self._iter)
                n -= 1
            except: n = 0
        return self

    def estimateFrames(self):
        "Try to estimate frames from movie metadata"
        try:
            meta = self._meta
            n = meta["nframes"]
            if n == float("inf"):
                n = round(meta["fps"] * meta["duration"])
        except: n = None
        return n

    @staticmethod
    def decode(mfile, zfile, start=0, frames=None, interval=1, mode="x", alpha=None, compression=ZIP_DEFLATED, **kwargs):
        "Decode frames from a movie to a zip file containing raw data"
        with Video(zfile, mode=mode, compression=compression) as vid:
            with Reader(mfile, **kwargs) as ffr:
                ffr.read_alpha = alpha 
                meta = ffr.meta
                if meta.get("fps") and interval > 1: meta["fps"] /= interval
                if start: ffr.read(start)
                i = 0
                try:
                    while True:
                        vid += next(ffr)
                        i += 1
                        if i == frames: break
                except Exception as exc: raise exc
                meta["nframes"] = i


class Writer(_FF):
    "Write graphics directly to media file using imageio/FFmpeg"

    def __init__(self, fn, fps=30, size=None, **kwargs):
        self._size = size
        self._io = imageio.get_writer(fn, fps=fps, **kwargs)
        _open_list.append(self)

    def write(self, img):
        "Write one frame (surface) to the video file, resizing if necessary"
        if not isinstance(img, Image): img = Image(img)
        if self._size is None: self._size = img.size
        elif img.size != self._size: img.config(size=self._size)
        self._io.append_data(numpy.array(pil(img.convert(False))))
        return self

    __iadd__ = write

    def writePIL(self, img):
        "Write a PIL image to the video file, resizing if necessary"
        if self._size is None: self._size = img.size
        elif img.size != self._size: img = img.resize(self._size)
        self._io.append_data(numpy.array(img))
        return self

    def concat(self, src, start=0, frames=None):
        "Concatenate frames from a movie file"
        with Reader(src, size=self._size).skip(start) as src:
            try:
                while frames is None or frames:
                    self.write(next(src))
                    if frames: frames -= 1
            except StopIteration: pass
        return self

    def concat_zip(self, src, start=0, frames=None):
        "Concatenate ZIP archive frames to the movie"
        with Video(src) as src:
            clip = src[start:start+frames] if frames else src[start:]
            for f in clip: self.write(f)
        return self

    @staticmethod
    def encode(zfile, mfile, fps=None, start=0, frames=None, **kwargs):
        "Encode frames from a ZIP archive using FFmpeg"
        with Video(zfile) as vid:
            if fps is None: fps = vid._meta.get("fps", 30)
            with Writer(mfile, fps, **kwargs) as ffw:
                seq = vid[start:start + frames] if frames else vid[start:] if start else vid
                for img in seq: ffw.write(img)
