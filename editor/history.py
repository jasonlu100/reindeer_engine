"""Reindeer editor undo / redo history.

Implements a bounded command stack (default 30 operations) using the classic
*Command* pattern.  Every reversible editor operation is expressed as a
:class:`Command` that knows how to *redo* and *undo* itself against the editor.

The editor's high-level operations build a command and apply it through
``Editor._apply_command`` (for structural changes) or push it directly
(``Editor.push_property_change`` for inspector edits).  Applying a command
performs the mutation exactly once and records it in a single place, so undo
and redo stay perfectly symmetric.

Consecutive edits to the same property (e.g. dragging a spin box) are coalesced
into a single history entry via :meth:`Command.coalesce`.
"""
from __future__ import annotations

from typing import Any, Callable, Optional


class Command:
    """Base class for a single reversible editor operation."""

    def redo(self) -> None:
        raise NotImplementedError

    def undo(self) -> None:
        raise NotImplementedError

    def label(self) -> str:
        return type(self).__name__

    def coalesce(self, other: "Command") -> bool:
        """Return ``True`` if *other* can be merged into this command so that the
        two collapse into a single history entry."""
        return False


# ----------------------------------------------------------------------
# concrete commands
# ----------------------------------------------------------------------
class AddNodeCommand(Command):
    def __init__(self, editor, node, parent, before):
        # ``before`` is the sibling node the new node should be inserted *before*
        # (or ``None`` to append).  Storing the neighbouring node (instead of a
        # numeric index) keeps undo/redo correct even when other siblings are
        # added or removed in between.
        self.editor = editor
        self.node = node
        self.parent = parent
        self.before = before

    def redo(self) -> None:
        self.editor._add_node_before(self.node, self.parent, self.before)

    def undo(self) -> None:
        self.editor._remove_node(self.node)

    def label(self) -> str:
        return f"Add {self.node.name}"


class DeleteNodeCommand(Command):
    def __init__(self, editor, node, parent, before):
        self.editor = editor
        self.node = node
        self.parent = parent
        self.before = before

    def redo(self) -> None:
        self.editor._remove_node(self.node)

    def undo(self) -> None:
        self.editor._add_node_before(self.node, self.parent, self.before)

    def label(self) -> str:
        return f"Delete {self.node.name}"


class ReparentCommand(Command):
    def __init__(self, editor, node, old_parent, old_before,
                 new_parent, new_before):
        self.editor = editor
        self.node = node
        self.old_parent = old_parent
        self.old_before = old_before
        self.new_parent = new_parent
        self.new_before = new_before

    def redo(self) -> None:
        self.editor._add_node_before(self.node, self.new_parent, self.new_before)

    def undo(self) -> None:
        self.editor._add_node_before(self.node, self.old_parent, self.old_before)


class MoveCommand(Command):
    def __init__(self, editor, node, old_pos, new_pos):
        self.editor = editor
        self.node = node
        self.old_pos = old_pos
        self.new_pos = new_pos

    def redo(self) -> None:
        self.editor._set_node_local_position(self.node, self.new_pos)

    def undo(self) -> None:
        self.editor._set_node_local_position(self.node, self.old_pos)


class PropertyCommand(Command):
    def __init__(self, editor, node, name, old_val, new_val):
        self.editor = editor
        self.node = node
        self.name = name
        self.old_val = old_val
        self.new_val = new_val

    def redo(self) -> None:
        self.editor._set_property(self.node, self.name, self.new_val)

    def undo(self) -> None:
        self.editor._set_property(self.node, self.name, self.old_val)

    def label(self) -> str:
        return f"Edit {self.name}"

    def coalesce(self, other: "Command") -> bool:
        if (isinstance(other, PropertyCommand)
                and other.node is self.node and other.name == self.name):
            self.new_val = other.new_val
            return True
        return False


# ----------------------------------------------------------------------
# the history stack itself
# ----------------------------------------------------------------------
class History:
    """A bounded undo / redo stack (max ``limit`` entries)."""

    def __init__(self, editor, limit: int = 30):
        self.editor = editor
        self.limit = limit
        self.undo_stack: list[Command] = []
        self.redo_stack: list[Command] = []
        self.on_change: Optional[Callable[[], None]] = None

    # -- queries --------------------------------------------------------
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def undo_label(self) -> str:
        return self.undo_stack[-1].label() if self.undo_stack else ""

    def redo_label(self) -> str:
        return self.redo_stack[-1].label() if self.redo_stack else ""

    # -- mutation -------------------------------------------------------
    def push(self, cmd: Command) -> None:
        # coalesce with the previous command when possible (e.g. dragging a
        # spin box produces many property edits that should collapse to one).
        if self.undo_stack and self.undo_stack[-1].coalesce(cmd):
            self._notify()
            return
        self.undo_stack.append(cmd)
        if len(self.undo_stack) > self.limit:
            # drop the oldest entry, keeping at most ``limit`` steps
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self._notify()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        cmd = self.undo_stack.pop()
        cmd.undo()
        self.redo_stack.append(cmd)
        self.editor._after_history()
        self._notify()

    def redo(self) -> None:
        if not self.redo_stack:
            return
        cmd = self.redo_stack.pop()
        cmd.redo()
        self.undo_stack.append(cmd)
        self.editor._after_history()
        self._notify()

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._notify()

    def _notify(self) -> None:
        if self.on_change is not None:
            self.on_change()
