"""Smoke tests for :mod:`vrcpilot.types`.

The module hosts ``Polygon``, a Python 3.12 ``type``-statement alias.
Runtime checks here only confirm that the alias is importable and that
a 4-tuple of 2-tuples actually satisfies the shape downstream callers
build. The static shape (4 corners, 2 floats each) is enforced by
pyright; we keep the runtime test minimal.
"""

from __future__ import annotations

from typing import get_args, get_origin

from vrcpilot.types import Polygon


class TestPolygonAlias:
    def test_polygon_is_importable(self):
        assert Polygon is not None

    def test_polygon_resolves_to_a_4_tuple_shape(self):
        # ``type Polygon = tuple[..., ..., ..., ...]`` -> the underlying
        # value is a generic alias whose origin is ``tuple`` and whose
        # args are the four 2-tuple types.
        underlying = Polygon.__value__
        assert get_origin(underlying) is tuple
        assert len(get_args(underlying)) == 4

    def test_concrete_4_tuple_satisfies_shape(self):
        polygon: Polygon = (
            (0.0, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 1.0),
        )
        assert len(polygon) == 4
        assert all(len(corner) == 2 for corner in polygon)
