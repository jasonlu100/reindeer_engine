"""Runtime entry points for Reindeer projects.

* :mod:`engine.runtime.game` -- :class:`GameRuntime`, the reusable engine
  runtime that builds an :class:`~engine.core.engine.Engine`, loads a project's
  main scene and drives the shared frame loop with a chosen render backend.
  This is what the editor's "Run (Pygame)" button and the packaged game both
  use, so behaviour stays identical between testing and release.
* :mod:`engine.runtime.pygame_app` -- thin CLI wrapper around ``GameRuntime``
  for launching a standalone pygame window.

The packaging side of the release pipeline lives in
:mod:`engine.packaging`.
"""
