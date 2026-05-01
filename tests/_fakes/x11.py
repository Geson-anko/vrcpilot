"""X11 / Xlib test doubles.

Lazy-imports ``Xlib`` so this module is importable on Windows where
``python-xlib`` is not installed. The fakes only model the surface
that vrcpilot's X11 helpers actually touch — adding new methods here
when production code grows is preferable to re-implementing per
test.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FakeXGeometry:
    """Stand-in for the geometry reply from ``Window.get_geometry``."""

    width: int = 1920
    height: int = 1080
    x: int = 0
    y: int = 0


class FakeXWindow:
    """Stand-in for ``Xlib.xobject.drawable.Window``.

    ``properties`` is a dict mapping atom name (str) → list of values
    so ``get_full_property`` can be driven from test data without
    needing the real Xlib atom resolution. Attribute mutation
    operations (``configure`` / ``raise_window`` / ``circulate``) are
    no-ops; tests that need to assert call counts do so via
    ``calls`` / ``circulate_direction``.
    """

    def __init__(
        self,
        *,
        wid: int = 1,
        pid: int = 4242,
        geometry: FakeXGeometry | None = None,
        properties: dict[str, list[int]] | None = None,
        translate_coords: tuple[int, int] = (0, 0),
        raises: BaseException | None = None,
    ) -> None:
        self.id = wid
        self.pid = pid
        self.geometry = geometry or FakeXGeometry()
        self.properties = properties or {"_NET_WM_PID": [pid]}
        self._translate_coords = translate_coords
        self._raises = raises
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.circulate_direction: int | None = None
        self.send_event_calls: list[object] = []

    def _record(self, name: str, args: tuple[object, ...] = ()) -> None:
        if self._raises is not None:
            raise self._raises
        self.calls.append((name, args))

    def get_full_property(self, atom: object, *_args: object):  # noqa: ANN201
        self._record("get_full_property", (atom,))
        # ``atom`` is an int when produced by the real ``intern_atom`` chain;
        # FakeXDisplay returns the atom's name back so tests can drive the
        # lookup with readable strings.
        key = atom if isinstance(atom, str) else getattr(atom, "name", str(atom))
        if key not in self.properties:
            return None
        return _FakeProperty(self.properties[key])

    def get_geometry(self):  # noqa: ANN201
        self._record("get_geometry")
        return self.geometry

    def translate_coords(self, _root: object, _x: int, _y: int):  # noqa: ANN201
        self._record("translate_coords")
        return _FakeCoords(*self._translate_coords)

    def configure(self, **kwargs: object) -> None:
        self._record("configure", tuple(sorted(kwargs.items())))

    def circulate(self, direction: int) -> None:
        self._record("circulate", (direction,))
        self.circulate_direction = direction

    def send_event(self, event: object, event_mask: object = 0) -> None:
        self._record("send_event", (event, event_mask))
        self.send_event_calls.append(event)


@dataclass
class _FakeProperty:
    """Stand-in for the property reply from ``get_full_property``."""

    value: list[int]


@dataclass
class _FakeCoords:
    """Stand-in for the reply of ``translate_coords``.

    Production reads ``x`` / ``y`` only.
    """

    x: int
    y: int


@dataclass
class _FakeScreen:
    """Stand-in for ``Display.screen()`` reply (only ``.root`` is read)."""

    root: FakeXWindow


class FakeXDisplay:
    """Stand-in for ``Xlib.display.Display``.

    Atoms are returned by name (a plain string) so test code can drive
    ``get_full_property`` with readable keys; the real Xlib returns
    integer atom ids, but the production code only forwards them
    opaquely between ``intern_atom`` and ``get_full_property``.

    Args:
        root: Pre-populated root window. Defaults to an empty one with
            no client list — tests that need a populated client list
            should supply their own :class:`FakeXWindow`.
        children: Mapping of window id → :class:`FakeXWindow` returned
            by :meth:`create_resource_object`. Tests that rely on
            ``find_vrchat_window`` populate this from the root's
            ``_NET_CLIENT_LIST`` property.
    """

    def __init__(
        self,
        *,
        root: FakeXWindow | None = None,
        children: dict[int, FakeXWindow] | None = None,
    ) -> None:
        self.root = root or FakeXWindow()
        self._children = children or {}
        self.close_calls = 0
        self.flush_calls = 0
        self.sync_calls = 0
        self.intern_atom_calls: list[str] = []
        self.create_resource_object_calls: list[tuple[str, int]] = []

    def screen(self) -> _FakeScreen:
        return _FakeScreen(root=self.root)

    def intern_atom(self, name: str) -> str:
        self.intern_atom_calls.append(name)
        return name

    def create_resource_object(self, kind: str, wid: int) -> FakeXWindow:
        self.create_resource_object_calls.append((kind, wid))
        if wid in self._children:
            return self._children[wid]
        # Synthesise an empty one so ``find_vrchat_window`` can call
        # ``get_full_property`` and observe a missing PID rather than
        # raising AttributeError.
        return FakeXWindow(wid=wid, properties={})

    def flush(self) -> None:
        self.flush_calls += 1

    def sync(self) -> None:
        self.sync_calls += 1

    def close(self) -> None:
        self.close_calls += 1
