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

"FFmpeg encoding and decoding using imageio/imageio-ffmpeg"

import os, struct, pygame, numpy, imageio
from json import dumps
from zipfile import ZipFile, ZIP_DEFLATED
from sc8pr import PixelData, Image
from sc8pr.misc.video import VidZip
from sc8prx import pil

class _FF:

    @staticmethod
    def ffmpeg(ff): os.environ["IMAGEIO_FFMPEG_EXE"] = ff

    def __enter__(self): return self
    def __exit__(self, *args): self._io.close()
    close = __exit__


class Reader(_FF):
    "Read images directly from a media file using imageio/FFmpeg"

    def __init__(self, src, **kwargs):
        self._io = imageio.get_reader(src, **kwargs)
        self._iter = iter(self._io)
        self._meta = self._io.get_meta_data()
        size = kwargs.get("size")
        if size is None: size = self._meta["size"]
        self._info = struct.pack("!3I", 0, *size)

    @property
    def meta(self): return self._meta
    
    def __next__(self):
        "Return the next frame as an uncompressed PixelData instance"
        return PixelData((bytes(next(self._iter)), self._info))

    def __iter__(self):
        "Iterate through all frames returning data as uncompressed PixelData"
        try:
            while True: yield next(self)
        except StopIteration: pass

    def _read(self, n=None):
        try:
            while n is None or n > 0:
                pix = next(self)
                if n is not None: n -= 1
                yield pix
        except StopIteration: pass

    def read(self, n=None, alpha=False):
        "Return a list of Images from the next n frames"
        return [img.rgba if alpha else img.img for img in self._read(n)]

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
    def decode(mfile, zfile, size=None, start=0, frames=None, interval=1, replace=False, compression=ZIP_DEFLATED):
        "Decode frames from a movie to a zip file containing PixelData binaries"
        i = 0
        prev = None
        with ZipFile(zfile, "w" if replace else "x", compression) as zf:
            kwargs = {"size": size} if size else {}
            with Reader(mfile, **kwargs) as ffr:
                meta = ffr.meta
                if meta.get("fps") and interval > 1: meta["fps"] /= interval
                if start: ffr.read(start)
                try:
                    while True:
                        for j in range(interval-1): next(ffr._iter)
                        data = bytes(next(ffr))
                        if data != prev: zf.writestr(str(i), data)
                        prev = data
                        i += 1
                        if i == frames: break
                except: pass
                meta["nframes"] = i
                zf.writestr("meta.json", dumps(meta))


class Writer(_FF):
    "Write graphics directly to media file using imageio/FFmpeg"

    def __init__(self, fn, fps=30, size=None, **kwargs):
        self._size = size
        self._io = imageio.get_writer(fn, fps=fps, **kwargs)

    def write(self, srf):
        "Write one frame (surface) to the video file, resizing if necessary"
        if type(srf) is not pygame.Surface:
            try: srf = srf.image
            except: srf = Image(srf).image
        size = srf.get_size()
        if self._size is None: self._size = size
        if size != self._size:
            srf = Image(srf).config(size=self._size).image
        self._io.append_data(numpy.array(pil(PixelData(srf))))
        return self

    def writePixelData(self, pix):
        "Write a PixelData instance: DOES NOT VERIFY SIZE"
        self._io.append_data(numpy.array(pil(pix)))
        return self

    def writePIL(self, pil):
        "Write a PIL image: DOES NOT VERIFY SIZE"
        self._io.append_data(numpy.array(pil))
        return self

    @staticmethod
    def _srf_rgb(pix):
        return pix.srf.convert(24) if pix.mode == "RGBA" else pix.srf

    def concat_zip(self, src, start=0, frames=None):
        "Concatenate ZIP archive frames to the movie"
        with VidZip(src) as src:
            clip = src[start:start+frames] if frames else src[start:]
            for f in clip: self.write(self._srf_rgb(f))
        return self

    def concat(self, src, start=0, frames=None):
        "Concatenate frames from a movie file"
        with Reader(src).skip(start) as src:
            try:
                while frames is None or frames:
                    self.write(self._srf_rgb(next(src)))
                    if frames: frames -= 1
            except StopIteration: pass
        return self

    capture = write

    @staticmethod
    def encode(zfile, mfile, fps=None, size=None, start=0, frames=None, **kwargs):
        "Encode frames from a ZIP archive using FFmpeg"
        with VidZip(zfile) as self:
            if fps is None: fps = self._meta.get("fps", 30)
            with Writer(mfile, fps, **kwargs) as ffw:
                seq = self[start:start + frames] if frames else self[start:] if start else self
                for pix in seq:
                    if size and pix.size != size:
                        ffw.write(pix.img.config(size=size).image)
                    else: ffw.writePixelData(pix)
