"""handlers/hillshade.py

Handle /hillshade API endpoint.
"""

from typing import Sequence, Mapping, Union, Tuple, TypeVar
from typing.io import BinaryIO

from io import BytesIO

from PIL import Image

from matplotlib.pyplot import get_cmap
from matplotlib.colors import LightSource, Normalize

from skimage.util import img_as_ubyte

import numpy as np

from terracotta import get_settings, get_driver, xyz
from terracotta.profile import trace

Number = TypeVar("Number", int, float)
# RGBA = Tuple[Number, Number, Number, Number]

# tile resolution for each level starting at level 0.
TILE_RESOLUTION = [
    156412,
    78206,
    39103,
    19551,
    9776,
    4888,
    2444,
    1222,
    610.984,
    305.492,
    152.746,
    76.373,
    38.187,
    19.093,
    9.547,
    4.773,
    2.387,
    1.193,
    0.596,
    0.298,
    0.149,
]


@trace("hillshade_handler")
def hillshade(
    keys: Union[Sequence[str], Mapping[str, str]],
    tile_xyz: Tuple[int, int, int] = None,
    *,
    colormap: str,
    azimuth_degree: Number,
    altitude_degree: Number,
    vertical_exaggeration: Number,
    blend_mode: str,
    tile_size: Tuple[int, int] = None,
) -> BinaryIO:
    """Return singleband image rendered as hillshade PNG"""

    try:
        cmap = get_cmap(colormap)
    except Exception:
        cmap = get_cmap("Greys_r")  # defaults to grey

    settings = get_settings()
    if tile_size is None:
        tile_size = settings.DEFAULT_TILE_SIZE

    driver = get_driver(settings.DRIVER_PATH, provider=settings.DRIVER_PROVIDER)

    with driver.connect():
        metadata = driver.get_metadata(keys)
        tile_data = xyz.get_tile_data(
            driver,
            keys,
            tile_xyz,
            tile_size=tile_size,
            preserve_values=False,
        )

    # compute the hillshade
    try:
        _, _, tile_z = tile_xyz
        dx = TILE_RESOLUTION[tile_z]
        dy = TILE_RESOLUTION[tile_z]
    except Exception:
        dx = 1
        dy = 1

    # compute the shadding
    norm = Normalize(
        vmin=metadata["range"][0],
        vmax=metadata["range"][1],
        clip=False,
    )

    ls = LightSource(azdeg=azimuth_degree, altdeg=altitude_degree)

    rgb = ls.shade(
        np.ma.masked_invalid(tile_data),
        cmap=cmap,
        blend_mode=blend_mode,
        vert_exag=vertical_exaggeration,
        dx=dx,
        dy=dy,
        norm=norm,
        vmin=metadata["range"][0],
        vmax=metadata["range"][1],
    )

    # Important - This by-passes terracotas strange encoding.

    # rgb is between 0 and, scale it to 0-255. store as uint8.
    rgb = img_as_ubyte(rgb)

    # encode as png
    img = Image.fromarray(rgb)

    sio = BytesIO()
    img.save(sio, format="PNG", compress_level=settings.PNG_COMPRESS_LEVEL)
    sio.seek(0)  # reset file pointer to start

    return sio
