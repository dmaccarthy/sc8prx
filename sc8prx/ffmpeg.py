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
from sc8pr import Image, BaseSprite
from sc8pr.util import surface
from sc8pr.sprite import CostumeImage, Sprite
from sc8pr.misc.video import Video, _open_list
from pygame.surfarray import pixels3d
from pygame.pixelcopy import make_surface

# try: v3 = imageio.v3
# except: v3 = None


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
        _open_list.append(self)
        self._io = imageio.get_reader(src, **kwargs)
        self._iter = iter(self._io)
        self._meta = self._io.get_meta_data()

    @property
    def meta(self): return self._meta
    
    def __next__(self):
        "Return the next frame as an Image instance"
        srf = make_surface(numpy.swapaxes(next(self._iter), 0, 1))
        return Image(surface(srf, self.read_alpha))

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
    def decode(mfile, zfile, start=0, frames=None, interval=1, mode="x", alpha=False, compression=ZIP_DEFLATED, **kwargs):
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
                        img = next(ffr)
                        vid += img
                        i += 1
                        if i == frames: break
                except StopIteration: pass
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
        data = numpy.swapaxes(pixels3d(img.image), 0, 1)
        self._io.append_data(data)
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


class Movie(CostumeImage):

    @property
    def cycle(self): return False

    @property
    def meta(self): return self._ffr.meta

    def __init__(self, src, skip=0, frames=None, alpha=False, **kwargs):
        self._alpha = alpha
        self._skip = skip
        self._frames = frames
        self._reader = lambda: Reader(src, **kwargs)
        self._size = kwargs.get("size", None)
        self.restart()

    def restart(self, ev=None):
        try: self._ffr.close()
        except: pass
        self._ffr = self._reader().skip(self._skip)
        self._read = (lambda r: next(r).rgba) if self._alpha else (lambda r: next(r))
        self._costumeNumber = 0
        self._costume = self._read(self._ffr)
        if self._size is None: self._size = self._costume.size
        return self

    def costume(self): return self._costume.config(size=self._size, angle=self.angle)

    @property
    def costumeNumber(self): return self._costumeNumber

    @costumeNumber.setter
    def costumeNumber(self, n):
        self._costumeNumber += 1
        if n != self._costumeNumber:
            raise ValueError("movie frames must be read in order")
        try:
            if n == self._frames: raise StopIteration()
            self._costume = self._read(self._ffr)
        except StopIteration:
            self._costumeNumber -= 1
            if self._frames is None or n < self._frames:
                self._frames = n

    def close(self): self._ffr.close()

    @property
    def clip(self):
        s = self._skip
        n = self._ffr._meta.get("nframes")
        if n == float("inf"): n = None
        f = self._frames
        if f is None: f = n
        else:
            try:
                f += s
                if n and n < f: f = n
            except: f = None
        return s, f

    def __len__(self):
        try:
            a, b = self.clip
            b -= a
        except: b = 0
        return b

    @property
    def costumeSequence(self): return None

    @property
    def costumeList(self): return None


class MovieSprite(Movie, BaseSprite):
    update = Sprite.update
