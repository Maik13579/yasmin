# Copyright (C) 2025 Miguel Ángel González Santamarta
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import math
from typing import Dict, List, Optional, Union, Any, Set, TYPE_CHECKING
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsTextItem, QGraphicsRectItem
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPen, QBrush, QColor, QFont

from yasmin_editor.editor_gui.connection_port import ConnectionPort

if TYPE_CHECKING:
    from yasmin_editor.editor_gui.connection_line import ConnectionLine
    from yasmin_editor.editor_gui.state_node import StateNode
    from yasmin_editor.editor_gui.final_outcome_node import FinalOutcomeNode
    from yasmin_editor.plugins_manager.plugin_info import PluginInfo


class ContainerStateNode(QGraphicsRectItem):
    """Container for State Machines and Concurrence states.

    Provides a graphical representation and management of hierarchical
    state containers including State Machines and Concurrence states.
    """

    def __init__(
        self,
        name: str,
        x: float,
        y: float,
        is_concurrence: bool = False,
        remappings: Optional[Dict[str, str]] = None,
        outcomes: Optional[List[str]] = None,
        start_state: Optional[str] = None,
        default_outcome: Optional[str] = None,
        description: str = "",
        defaults: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Initialize a container state node.

        Args:
            name: Name of the container state.
            x: X coordinate for initial position.
            y: Y coordinate for initial position.
            is_concurrence: True for Concurrence, False for State Machine.
            remappings: Dictionary of key remappings.
            outcomes: List of outcome names.
            start_state: Initial state for State Machines.
            default_outcome: Default outcome for Concurrence states.
        """
        super().__init__(-500, -400, 1000, 800)
        self.name = name
        self.plugin_info: Optional["PluginInfo"] = None
        self.is_state_machine = not is_concurrence
        self.is_concurrence = is_concurrence
        self.connections: List["ConnectionLine"] = []
        self.remappings = remappings or {}
        self.final_outcomes: Dict[str, "FinalOutcomeNode"] = {}
        self.start_state = start_state
        self.default_outcome = default_outcome
        self.child_states: Dict[str, Union["StateNode", "ContainerStateNode"]] = {}
        self.parent_container: Optional["ContainerStateNode"] = None
        self.description: str = description
        self.defaults: List[Dict[str, str]] = defaults or []
        self.min_width = 1000
        self.min_height = 800
        self.xml_file: Optional[str] = None
        self.blackboard_key_metadata: Dict[str, Dict[str, str]] = {}
        self._content_rect = QRectF(-500, -400, 1000, 800)
        self._compact_rect = QRectF(-90, -45, 180, 90)
        self._entered = False

        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        self.header = QGraphicsRectItem(self)
        self.header.setBrush(
            QBrush(QColor(255, 140, 0) if is_concurrence else QColor(0, 100, 200))
        )
        self.header.setPen(QPen(Qt.NoPen))

        self.title = QGraphicsTextItem(self)
        self.title.setDefaultTextColor(Qt.white)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        self.title.setFont(title_font)

        self.type_label = QGraphicsTextItem(self)
        self.type_label.setDefaultTextColor(Qt.darkGray)
        compact_font = QFont()
        compact_font.setPointSize(8)
        self.type_label.setFont(compact_font)

        if not is_concurrence:
            self.start_state_label = QGraphicsTextItem(self)
            self.start_state_label.setDefaultTextColor(QColor(0, 100, 0))
            self._set_label_font(self.start_state_label)
        else:
            self.default_outcome_label = QGraphicsTextItem(self)
            self.default_outcome_label.setDefaultTextColor(QColor(139, 69, 19))
            self._set_label_font(self.default_outcome_label)

        self.connection_port = ConnectionPort(self)
        self.update_label()
        self.apply_display_mode()

    def get_child_bounds_rect(self) -> QRectF:
        return QRectF(self._content_rect)

    def is_entered(self) -> bool:
        return self._entered

    def set_entered(self, entered: bool) -> None:
        self._entered = entered
        self.apply_display_mode()

    def _set_label_font(self, label: QGraphicsTextItem) -> None:
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        label.setFont(font)

    def update_label(self) -> None:
        if hasattr(self, "start_state_label"):
            text = (
                f"Initial: {self.start_state}" if self.start_state else "Initial: (none)"
            )
            self.start_state_label.setPlainText(text)
        elif hasattr(self, "default_outcome_label"):
            text = (
                f"Default: {self.default_outcome}"
                if self.default_outcome
                else "Default: (none)"
            )
            self.default_outcome_label.setPlainText(text)
        self.update_visual_elements()

    def update_start_state_label(self) -> None:
        self.update_label()

    def update_default_outcome_label(self) -> None:
        self.update_label()

    def apply_display_mode(self) -> None:
        if self.is_concurrence:
            self.setRect(self._content_rect)
            self.setBrush(QBrush(QColor(255, 220, 150, 180)))
            self.setPen(QPen(QColor(255, 140, 0), 3))
            self.setFlag(QGraphicsItem.ItemIsSelectable, True)
            self.setAcceptedMouseButtons(Qt.AllButtons)
            self.header.show()
            self.title.show()
            self.type_label.hide()
            self.title.setDefaultTextColor(Qt.white)
            self.title.setPlainText(f"CONCURRENCE: {self.name}")
            if hasattr(self, "start_state_label"):
                self.start_state_label.hide()
            if hasattr(self, "default_outcome_label"):
                self.default_outcome_label.show()
            self.connection_port.show()
            self.update_visual_elements()
            return

        if self._entered:
            self.setRect(self._content_rect)
            self.setBrush(QBrush(Qt.NoBrush))
            self.setPen(QPen(Qt.NoPen))
            self.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self.setAcceptedMouseButtons(Qt.NoButton)
            self.header.hide()
            self.title.hide()
            self.type_label.hide()
            if hasattr(self, "start_state_label"):
                self.start_state_label.hide()
            if hasattr(self, "default_outcome_label"):
                self.default_outcome_label.hide()
            self.connection_port.hide()
            return

        self.setRect(self._compact_rect)
        self.setBrush(QBrush(QColor(178, 151, 255, 180)))
        self.setPen(QPen(QColor(98, 65, 195), 3))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptedMouseButtons(Qt.AllButtons)
        self.header.hide()
        self.title.show()
        self.type_label.show()
        self.title.setDefaultTextColor(Qt.black)
        self.title.setPlainText(self.name)
        self.type_label.setPlainText("FSM")
        if hasattr(self, "start_state_label"):
            self.start_state_label.hide()
        self.connection_port.show()
        self.update_visual_elements()

    def update_visual_elements(self) -> None:
        rect = self.rect()
        self.header.setRect(rect.left(), rect.top(), rect.width(), 50)

        title_rect = self.title.boundingRect()
        if self.is_concurrence:
            title_y = rect.top() + 12
        else:
            title_y = rect.top() + 12
        self.title.setPos(
            rect.left() + rect.width() / 2 - title_rect.width() / 2,
            title_y,
        )

        if self.type_label.isVisible():
            type_rect = self.type_label.boundingRect()
            self.type_label.setPos(
                rect.left() + rect.width() / 2 - type_rect.width() / 2,
                rect.top() + rect.height() - 24,
            )

        for label in [
            getattr(self, "start_state_label", None),
            getattr(self, "default_outcome_label", None),
        ]:
            if label and label.isVisible():
                label_rect = label.boundingRect()
                label.setPos(
                    rect.left() + rect.width() / 2 - label_rect.width() / 2,
                    rect.top() + 52,
                )

        if hasattr(self, "connection_port"):
            self.connection_port.update_position_for_container()

    def add_child_state(
        self, state_node: Union["StateNode", "ContainerStateNode"]
    ) -> None:
        if state_node.name not in self.child_states:
            self.child_states[state_node.name] = state_node
            state_node.parent_container = self
            state_node.setParentItem(self)
            self._update_layout()

    def remove_child_state(self, state_name: str) -> None:
        if state_name in self.child_states:
            state = self.child_states[state_name]
            state.parent_container = None
            state.setParentItem(None)
            del self.child_states[state_name]
            self._update_layout()

    def _update_layout(self) -> None:
        self._layout_children()
        self.auto_resize_for_children()

    def _layout_children(self) -> None:
        """Layout child states in a deterministic grid pattern.

        Positions child states in a grid layout with configurable spacing
        and padding for visual clarity.
        """
        if not self.child_states:
            return

        rect = self.get_child_bounds_rect()
        child_padding_x = 60
        child_padding_y = 110
        child_spacing_x = 700
        child_spacing_y = 650
        children_per_column = 3

        sorted_children = sorted(self.child_states.items(), key=lambda x: x[0])

        x_position = rect.left() + child_padding_x
        y_position = rect.top() + child_padding_y
        row_index = 0

        for _name, child in sorted_children:
            if getattr(child, "_xml_position_loaded", False):
                continue
            child.setPos(x_position, y_position)
            row_index += 1

            if row_index >= children_per_column:
                row_index = 0
                x_position += child_spacing_x
                y_position = rect.top() + child_padding_y
            else:
                child_height = (
                    child.rect().height()
                    if isinstance(child, ContainerStateNode)
                    else child.boundingRect().height()
                )
                y_position += max(child_height, 200) + child_spacing_y

    def add_final_outcome(self, outcome_node: "FinalOutcomeNode") -> None:
        """Add a final outcome to this container.

        Args:
            outcome_node: The final outcome node to add.
        """
        if outcome_node.name not in self.final_outcomes:
            self.final_outcomes[outcome_node.name] = outcome_node
            outcome_node.parent_container = self
            outcome_node.setParentItem(self)
            self._reposition_final_outcomes()
            self.auto_resize_for_children()

    def _reposition_final_outcomes(self) -> None:
        """Reposition final outcomes on the right side of container.

        Places final outcome nodes vertically along the right edge of the
        container with appropriate spacing.
        """
        if not self.final_outcomes:
            return

        rect = self.get_child_bounds_rect()
        outcome_padding_top = 110
        outcome_spacing_y = 300
        max_child_x = rect.left() + 500

        for child in self.child_states.values():
            child_right = (
                child.pos().x() + child.rect().width()
                if isinstance(child, ContainerStateNode)
                else child.pos().x() + child.boundingRect().width()
            )
            max_child_x = max(max_child_x, child_right)

        outcome_x = max_child_x + 300
        current_y = rect.top() + outcome_padding_top

        for _name, outcome_node in sorted(self.final_outcomes.items(), key=lambda x: x[0]):
            if getattr(outcome_node, "_xml_position_loaded", False):
                continue
            outcome_node.setPos(outcome_x, current_y)
            current_y += outcome_spacing_y

    def auto_resize_for_children(self) -> None:
        if not self.child_states and not self.final_outcomes:
            return

        self.prepareGeometryChange()
        padding = [50, 100, 50, 50]
        items = list(self.child_states.values()) + list(self.final_outcomes.values())

        bounds = [float("inf"), float("inf"), float("-inf"), float("-inf")]
        for item in items:
            pos = item.pos()
            rect = item.rect() if isinstance(item, ContainerStateNode) else item.boundingRect()
            bounds[0] = min(bounds[0], pos.x() + rect.left())
            bounds[1] = min(bounds[1], pos.y() + rect.top())
            bounds[2] = max(bounds[2], pos.x() + rect.right())
            bounds[3] = max(bounds[3], pos.y() + rect.bottom())

        self._content_rect = QRectF(
            bounds[0] - padding[0],
            bounds[1] - padding[1],
            max(bounds[2] - bounds[0] + padding[0] + padding[2], self.min_width),
            max(bounds[3] - bounds[1] + padding[1] + padding[3], self.min_height),
        )

        if self.is_concurrence or self._entered:
            self.setRect(self._content_rect)
        self.update_visual_elements()
        self._update_all_connections_recursive()
        if self.parent_container:
            self.parent_container.auto_resize_for_children()

    def _update_all_connections_recursive(self) -> None:
        """Recursively update all connections in this container and children."""
        for connection in self.connections:
            connection.update_position()

        self.update_child_connections()

        for child in self.child_states.values():
            if isinstance(child, ContainerStateNode):
                child._update_all_connections_recursive()

    def mouseDoubleClickEvent(self, event: Any) -> None:
        """Handle double-click to edit container state.

        Args:
            event: The mouse event.
        """
        if self.scene() and self.scene().views():
            canvas = self.scene().views()[0]
            if hasattr(canvas, "editor_ref") and canvas.editor_ref:
                self.setSelected(True)
                if event.modifiers() & Qt.ControlModifier and not self.is_concurrence:
                    canvas.editor_ref.enter_container(self, canvas.editor_ref.current_read_only)
                else:
                    canvas.editor_ref.edit_state()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: Any) -> None:
        if self.scene() and self.scene().views():
            canvas = self.scene().views()[0]
            if hasattr(canvas, "editor_ref") and canvas.editor_ref:
                from PyQt5.QtWidgets import QMenu

                menu = QMenu()
                actions = [
                    ("Add State", lambda: canvas.editor_ref.add_state_to_container()),
                    (
                        "Add State Machine",
                        lambda: canvas.editor_ref.add_state_machine_to_container(),
                    ),
                    (
                        "Add Concurrence",
                        lambda: canvas.editor_ref.add_concurrence_to_container(),
                    ),
                    None,
                    ("Add Final Outcome", lambda: canvas.editor_ref.add_final_outcome()),
                    None,
                    ("Edit Properties", lambda: canvas.editor_ref.edit_state()),
                    ("Delete", lambda: canvas.editor_ref.delete_selected()),
                ]
                menu_actions = {}
                for item in actions:
                    if item is None:
                        menu.addSeparator()
                    else:
                        name, func = item
                        menu_actions[menu.addAction(name)] = func
                action = menu.exec_(event.screenPos())
                if action in menu_actions:
                    self.setSelected(True)
                    menu_actions[action]()
                    event.accept()
                    return
        super().contextMenuEvent(event)

    def update_child_connections(self) -> None:
        """Update all connections for child states and outcomes recursively."""
        for child in self.child_states.values():
            for connection in child.connections:
                connection.update_position()
            if isinstance(child, ContainerStateNode):
                child.update_child_connections()

        for outcome in self.final_outcomes.values():
            for connection in outcome.connections:
                connection.update_position()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """Handle item changes like position and selection.

        Args:
            change: The type of change occurring.
            value: The new value for the change.

        Returns:
            The potentially modified value.
        """
        if change == QGraphicsItem.ItemPositionChange and isinstance(value, QPointF):
            if self.parent_container:
                container_rect = self.parent_container.get_child_bounds_rect()
                self_rect = self.rect()
                new_pos = value

                min_x = container_rect.left() - self_rect.left() + 10
                max_x = container_rect.right() - self_rect.right() - 10
                min_y = container_rect.top() - self_rect.top() + 40
                max_y = container_rect.bottom() - self_rect.bottom() - 10

                constrained_x = max(min_x, min(new_pos.x(), max_x))
                constrained_y = max(min_y, min(new_pos.y(), max_y))
                value = QPointF(constrained_x, constrained_y)

            for connection in self.connections:
                connection.update_position()
            self.update_child_connections()

        elif change == QGraphicsItem.ItemPositionHasChanged:
            if self.parent_container:
                self.parent_container.auto_resize_for_children()

        elif change == QGraphicsItem.ItemSelectedChange:
            if self._entered:
                self.apply_display_mode()
            elif value:
                self.setPen(QPen(QColor(255, 200, 0), 4))
            else:
                self.apply_display_mode()

        return super().itemChange(change, value)

    def add_connection(self, connection: "ConnectionLine") -> None:
        """Add a connection line to this container.

        Args:
            connection: The connection line to add.
        """
        if connection not in self.connections:
            self.connections.append(connection)

    def remove_connection(self, connection: "ConnectionLine") -> None:
        """Remove a connection line from this container.

        Args:
            connection: The connection line to remove.
        """
        if connection in self.connections:
            self.connections.remove(connection)

    def get_used_outcomes(self) -> Set[str]:
        return {conn.outcome for conn in self.connections}

    def get_connection_point(self) -> QPointF:
        return (
            self.connection_port.scenePos()
            if hasattr(self, "connection_port")
            else self.scenePos()
        )

    def get_edge_point(self, target_pos: QPointF) -> QPointF:
        """Get the intersection point on container edge towards target.

        Args:
            target_pos: The target position to point towards.

        Returns:
            Point on the container's edge closest to the target.
        """
        rect = self.rect()
        pos = self.scenePos()

        center_x = pos.x() + rect.left() + rect.width() / 2
        center_y = pos.y() + rect.top() + rect.height() / 2
        center = QPointF(center_x, center_y)

        angle = math.atan2(target_pos.y() - center.y(), target_pos.x() - center.x())
        w = rect.width() / 2
        h = rect.height() / 2
        abs_tan = abs(math.tan(angle)) if math.cos(angle) != 0 else float("inf")
        if abs_tan <= h / w:
            x = center.x() + w * (1 if math.cos(angle) > 0 else -1)
            y = center.y() + w * math.tan(angle) * (1 if math.cos(angle) > 0 else -1)
        else:
            y = center.y() + h * (1 if math.sin(angle) > 0 else -1)
            x = (
                center.x() + h / math.tan(angle) * (1 if math.sin(angle) > 0 else -1)
                if math.sin(angle) != 0
                else center.x()
            )
        return QPointF(x, y)
