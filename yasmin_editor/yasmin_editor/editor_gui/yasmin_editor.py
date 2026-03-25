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

import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from lxml import etree as ET
from ament_index_python import get_package_share_path
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QGraphicsItem,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QLabel,
    QInputDialog,
    QMessageBox,
    QFileDialog,
    QSplitter,
    QListWidgetItem,
    QLineEdit,
    QComboBox,
    QAction,
    QToolBar,
    QDialog,
    QPushButton,
    QTextBrowser,
    QAbstractItemView,
    QSizePolicy,
    QDialogButtonBox,
)
from PyQt5.QtGui import QCloseEvent, QPen, QBrush, QColor
from PyQt5.QtCore import Qt, QPointF

from yasmin_editor.plugins_manager.plugin_manager import PluginManager
from yasmin_editor.plugins_manager.plugin_info import PluginInfo
from yasmin_editor.editor_gui.connection_line import ConnectionLine
from yasmin_editor.editor_gui.state_node import StateNode
from yasmin_editor.editor_gui.container_state_node import ContainerStateNode
from yasmin_editor.editor_gui.final_outcome_node import FinalOutcomeNode
from yasmin_editor.editor_gui.state_machine_canvas import StateMachineCanvas
from yasmin_editor.editor_gui.state_properties_dialog import StatePropertiesDialog
from yasmin_editor.editor_gui.state_machine_dialog import StateMachineDialog
from yasmin_editor.editor_gui.concurrence_dialog import ConcurrenceDialog
from yasmin_editor.editor_gui.xml_manager import XmlManager
from yasmin_editor.editor_gui.blackboard_key_dialog import BlackboardKeyDialog
from yasmin_editor.editor_gui.outcome_description_dialog import OutcomeDescriptionDialog


class YasminEditor(QMainWindow):
    """Main editor window for YASMIN state machines.

    Provides a graphical interface for creating, editing, and managing
    hierarchical state machines with support for Python, C++, and XML states.
    """

    def __init__(self, manager: PluginManager) -> None:
        """Initialize the YASMIN Editor.

        Args:
            manager: The PluginManager instance for handling plugins.
        """
        super().__init__()
        self.setWindowTitle("YASMIN Editor")

        self.showMaximized()

        self.plugin_manager = manager
        self.state_nodes: Dict[str, StateNode] = {}
        self.final_outcomes: Dict[str, FinalOutcomeNode] = {}
        self.connections: List[ConnectionLine] = []
        self.root_sm_name = ""
        self.start_state = None
        self._blackboard_keys: List[Dict[str, str]] = []
        self._blackboard_key_metadata: Dict[str, Dict[str, str]] = {}
        self._highlight_blackboard_usage = True
        self.root_sm_description = ""
        self.current_container: Optional[ContainerStateNode] = None
        self.current_read_only: bool = False
        self.preview_root_container: Optional[ContainerStateNode] = None
        self.preview_items: List[object] = []
        self.navigation_path: List[Tuple[str, Optional[ContainerStateNode], bool]] = [("root", None, False)]

        self.layout_seed = 42
        self.layout_rng = random.Random(self.layout_seed)

        self.xml_manager = XmlManager(self)
        self.create_ui()

        self.statusBar().showMessage("Loading plugins...")
        QApplication.processEvents()
        self.populate_plugin_lists()
        self.statusBar().showMessage("Ready", 3000)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event to ensure proper cleanup."""
        # Clear all references
        self.canvas.scene.clear()
        self.state_nodes.clear()
        self.final_outcomes.clear()
        self.connections.clear()

        # Accept the close event
        event.accept()

        # Quit the application and exit the process
        QApplication.quit()

        # Force process termination
        os._exit(0)

    def create_ui(self) -> None:
        """Create and setup the user interface.

        Sets up the main window layout including toolbars, panels,
        and the state machine canvas.
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        toolbar = QToolBar()
        self.addToolBar(toolbar)

        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_state_machine)
        toolbar.addAction(new_action)

        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_state_machine)
        toolbar.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_state_machine)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        add_state_action = QAction("Add State", self)
        add_state_action.triggered.connect(self.add_state)
        toolbar.addAction(add_state_action)

        add_state_machine_action = QAction("Add State Machine", self)
        add_state_machine_action.triggered.connect(self.add_state_machine)
        toolbar.addAction(add_state_machine_action)

        add_concurrence_action = QAction("Add Concurrence", self)
        add_concurrence_action.triggered.connect(self.add_concurrence)
        toolbar.addAction(add_concurrence_action)

        add_final_action = QAction("Add Final Outcome", self)
        add_final_action.triggered.connect(self.add_final_outcome)
        toolbar.addAction(add_final_action)

        toolbar.addSeparator()

        delete_action = QAction("Delete Selected", self)
        delete_action.triggered.connect(self.delete_selected)
        toolbar.addAction(delete_action)

        toolbar.addSeparator()

        help_action = QAction("Help", self)
        help_action.triggered.connect(self.show_help)
        toolbar.addAction(help_action)

        left_layout.addWidget(QLabel("<b>Blackboard Keys:</b>"))
        self.blackboard_filter = QLineEdit()
        self.blackboard_filter.setPlaceholderText("Filter blackboard keys...")
        self.blackboard_filter.textChanged.connect(self.filter_blackboard_keys)
        left_layout.addWidget(self.blackboard_filter)
        self.blackboard_list = QListWidget()
        self.blackboard_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.blackboard_list.itemSelectionChanged.connect(
            self.on_blackboard_selection_changed
        )
        self.blackboard_list.itemDoubleClicked.connect(self.edit_selected_blackboard_key)
        left_layout.addWidget(self.blackboard_list)
        blackboard_btn_row = QHBoxLayout()
        self.highlight_blackboard_btn = QPushButton("Highlight: On")
        self.highlight_blackboard_btn.setCheckable(True)
        self.highlight_blackboard_btn.setChecked(True)
        self.highlight_blackboard_btn.toggled.connect(self.toggle_blackboard_highlighting)
        blackboard_btn_row.addWidget(self.highlight_blackboard_btn)
        left_layout.addLayout(blackboard_btn_row)

        # Python states list
        left_layout.addWidget(QLabel("<b>Python States:</b>"))
        self.python_filter = QLineEdit()
        self.python_filter.setPlaceholderText("Filter Python states...")
        self.python_filter.textChanged.connect(
            lambda text: self.filter_list(self.python_list, text)
        )
        left_layout.addWidget(self.python_filter)
        self.python_list = QListWidget()
        self.python_list.itemDoubleClicked.connect(self.on_plugin_double_clicked)
        left_layout.addWidget(self.python_list)

        # C++ states list
        left_layout.addWidget(QLabel("<b>C++ States:</b>"))
        self.cpp_filter = QLineEdit()
        self.cpp_filter.setPlaceholderText("Filter C++ states...")
        self.cpp_filter.textChanged.connect(
            lambda text: self.filter_list(self.cpp_list, text)
        )
        left_layout.addWidget(self.cpp_filter)
        self.cpp_list = QListWidget()
        self.cpp_list.itemDoubleClicked.connect(self.on_plugin_double_clicked)
        left_layout.addWidget(self.cpp_list)

        left_layout.addWidget(QLabel("<b>XML State Machines:</b>"))
        self.xml_filter = QLineEdit()
        self.xml_filter.setPlaceholderText("Filter XML state machines...")
        self.xml_filter.textChanged.connect(
            lambda text: self.filter_list(self.xml_list, text)
        )
        left_layout.addWidget(self.xml_filter)
        self.xml_list = QListWidget()
        self.xml_list.itemDoubleClicked.connect(self.on_xml_double_clicked)
        left_layout.addWidget(self.xml_list)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        root_sm_widget = QWidget()
        root_sm_vlayout = QVBoxLayout(root_sm_widget)
        root_sm_vlayout.setContentsMargins(0, 0, 0, 0)

        root_sm_row1 = QHBoxLayout()
        root_sm_row1.addWidget(QLabel("<b>State Machine Name:</b>"))
        self.root_sm_name_edit = QLineEdit()
        self.root_sm_name_edit.setPlaceholderText("Enter root state machine name...")
        self.root_sm_name_edit.textChanged.connect(self.on_root_sm_name_changed)
        root_sm_row1.addWidget(self.root_sm_name_edit)

        root_sm_row1.addWidget(QLabel("<b>Start State:</b>"))
        self.start_state_combo = QComboBox()
        self.start_state_combo.addItem("(None)")
        self.start_state_combo.currentTextChanged.connect(self.on_start_state_changed)
        root_sm_row1.addWidget(self.start_state_combo)
        root_sm_vlayout.addLayout(root_sm_row1)

        root_sm_row2 = QHBoxLayout()
        root_sm_row2.addWidget(QLabel("<b>Description:</b>"))
        self.root_sm_description_edit = QLineEdit()
        self.root_sm_description_edit.setPlaceholderText("Enter FSM description...")
        self.root_sm_description_edit.textChanged.connect(self.on_root_sm_description_changed)
        root_sm_row2.addWidget(self.root_sm_description_edit)

        root_sm_vlayout.addLayout(root_sm_row2)

        right_layout.addWidget(root_sm_widget)

        self.navigator_widget = QWidget()
        self.navigator_layout = QHBoxLayout(self.navigator_widget)
        self.navigator_layout.setContentsMargins(0, 0, 0, 0)
        self.navigator_layout.setSpacing(4)
        self.nav_up_button = QPushButton("↑")
        self.nav_up_button.setFixedWidth(32)
        self.nav_up_button.clicked.connect(self.navigate_up)
        self.navigator_layout.addWidget(self.nav_up_button)
        self.navigator_layout.addStretch(1)
        right_layout.addWidget(self.navigator_widget)
        self.update_navigation_ui()

        canvas_header = QLabel(
            "<b>State Machine Canvas:</b> "
            "<i>(Drag from blue port to create transitions, scroll to zoom, right-click for options)</i>"
        )
        right_layout.addWidget(canvas_header)
        self.canvas = StateMachineCanvas()
        self.canvas.editor_ref = self
        right_layout.addWidget(self.canvas)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)

        splitter.setSizes([300, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.statusBar()

    def populate_plugin_lists(self) -> None:
        """Populate the plugin lists with available Python, C++, and XML states."""
        for plugin in self.plugin_manager.python_plugins:
            item = QListWidgetItem(f"{plugin.module}.{plugin.class_name}")
            item.setData(Qt.UserRole, plugin)
            self.python_list.addItem(item)

        for plugin in self.plugin_manager.cpp_plugins:
            item = QListWidgetItem(plugin.class_name)
            item.setData(Qt.UserRole, plugin)
            self.cpp_list.addItem(item)

        for xml_plugin in self.plugin_manager.xml_files:
            display_name = f"{xml_plugin.package_name}/{xml_plugin.file_name}"
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, xml_plugin)
            self.xml_list.addItem(item)

    def filter_list(self, list_widget: QListWidget, text: str) -> None:
        """Filter a list widget based on search text."""
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def on_root_sm_name_changed(self, text: str) -> None:
        """Handle root state machine name change.

        Args:
            text: The new state machine name.
        """
        if self.current_read_only:
            return
        if self.current_container is not None:
            self.current_container.name = text
            self.current_container.apply_display_mode()
            self.update_navigation_ui()
            self._rebuild_state_node_index()
            return
        self.root_sm_name = text

    def on_root_sm_description_changed(self, text: str) -> None:
        if self.current_read_only:
            return
        if self.current_container is not None:
            self.current_container.description = text
        else:
            self.root_sm_description = text

    def _get_metadata_owner(self) -> Optional[ContainerStateNode]:
        return self.current_container

    def _get_active_blackboard_metadata(self) -> Dict[str, Dict[str, str]]:
        owner = self._get_metadata_owner()
        if owner is None:
            return self._blackboard_key_metadata
        if not hasattr(owner, 'blackboard_key_metadata'):
            owner.blackboard_key_metadata = {}
        return owner.blackboard_key_metadata

    def on_start_state_changed(self, text: str) -> None:
        """Handle initial state selection change.

        Args:
            text: The selected state name or "(None)".
        """
        if self.current_read_only:
            return

        active_container = self.current_container
        if active_container is not None:
            active_container.start_state = None if text == "(None)" else text
            active_container.update_start_state_label()
            return

        if text == "(None)":
            self.start_state = None
        else:
            self.start_state = text

    def _get_container_path(self, container: ContainerStateNode) -> str:
        parts: List[str] = []
        current = container
        while current is not None:
            parts.append(current.name)
            current = getattr(current, "parent_container", None)
        return ".".join(reversed(parts))

    def _get_active_edit_container(self) -> Optional[ContainerStateNode]:
        if self.current_read_only:
            return None
        return self.current_container

    def _get_scope_container(self) -> Optional[ContainerStateNode]:
        return self.current_container or self.preview_root_container

    def _get_scope_owner(self, item) -> Optional[ContainerStateNode]:
        return getattr(item, "parent_container", None)

    def _get_scope_connection_visibility(self, connection: ConnectionLine) -> bool:
        scope_container = self._get_scope_container()
        from_owner = self._get_scope_owner(connection.from_node)
        to_owner = self._get_scope_owner(connection.to_node)
        return from_owner == scope_container and to_owner == scope_container

    def _set_connection_visible(self, connection: ConnectionLine, visible: bool) -> None:
        connection.setVisible(visible)
        connection.arrow_head.setVisible(visible)
        connection.label_bg.setVisible(visible)
        connection.label.setVisible(visible)

    def _set_ancestor_chain_visible(self, container: Optional[ContainerStateNode]) -> None:
        current = container
        while current is not None:
            current.setVisible(True)
            if current.is_state_machine:
                current.set_entered(True)
            current = getattr(current, "parent_container", None)

    def _iter_scope_state_nodes_recursive(self, container: Optional[ContainerStateNode]) -> List[StateNode]:
        if container is None:
            return self._get_scope_nodes()
        return list(container.child_states.values())

    def _set_dialog_read_only(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(f"{dialog.windowTitle()} (Read Only)")

        for child in dialog.findChildren(QWidget):
            if isinstance(child, QTextBrowser):
                continue
            if isinstance(child, QDialogButtonBox):
                ok_button = child.button(QDialogButtonBox.Ok)
                if ok_button is not None:
                    ok_button.hide()
                cancel_button = child.button(QDialogButtonBox.Cancel)
                if cancel_button is not None:
                    cancel_button.setText("Close")
                continue
            if hasattr(child, "setReadOnly"):
                try:
                    child.setReadOnly(True)
                    continue
                except Exception:
                    pass
            if hasattr(child, "setEnabled"):
                try:
                    child.setEnabled(False)
                except Exception:
                    pass

    def _is_outcome_used(self, from_node, outcome: str) -> bool:
        for connection in getattr(from_node, "connections", []):
            if connection.from_node == from_node and connection.outcome == outcome:
                return True
        return False

    def _get_scope_nodes(self) -> List[StateNode]:
        if self.preview_root_container is not None and self.current_container is None:
            return list(self.preview_root_container.child_states.values())
        if self.current_container is None:
            return [
                node
                for node in self.state_nodes.values()
                if getattr(node, "parent_container", None) is None
            ]
        return list(self.current_container.child_states.values())

    def _get_scope_final_outcomes(self) -> List[FinalOutcomeNode]:
        if self.preview_root_container is not None and self.current_container is None:
            return list(self.preview_root_container.final_outcomes.values())
        if self.current_container is None:
            return list(self.final_outcomes.values())
        return list(self.current_container.final_outcomes.values())

    def _find_state_node_key(self, state_node) -> Optional[str]:
        for key, node in self.state_nodes.items():
            if node is state_node:
                return key
        return None

    def _iter_root_state_nodes(self) -> List[StateNode]:
        roots: List[StateNode] = []
        seen = set()
        for node in self.state_nodes.values():
            if getattr(node, "parent_container", None) is None and id(node) not in seen:
                roots.append(node)
                seen.add(id(node))
        return roots

    def _rebuild_state_node_index(self) -> None:
        new_index = {}

        def visit(node, prefix: str = "") -> None:
            key = f"{prefix}.{node.name}" if prefix else node.name
            new_index[key] = node
            if isinstance(node, ContainerStateNode):
                for child in node.child_states.values():
                    visit(child, key)

        for root_node in self._iter_root_state_nodes():
            visit(root_node)

        self.state_nodes = new_index

    def update_navigation_ui(self) -> None:
        while self.navigator_layout.count() > 2:
            item = self.navigator_layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        insert_index = 1
        for index, (label, _container, _readonly) in enumerate(self.navigation_path):
            button = QPushButton(label)
            button.setFlat(True)
            button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
            button.clicked.connect(
                lambda _checked=False, idx=index: self.navigate_to_index(idx)
            )
            self.navigator_layout.insertWidget(insert_index, button)
            insert_index += 1
            if index < len(self.navigation_path) - 1:
                self.navigator_layout.insertWidget(insert_index, QLabel('>'))
                insert_index += 1

        self.nav_up_button.setEnabled(len(self.navigation_path) > 1)


    def _apply_scope_item_flags(self) -> None:
        editable = not self.current_read_only
        scope_container = self._get_scope_container()
        for node in self.state_nodes.values():
            if node.isVisible():
                is_scope_container = node is scope_container
                node.setFlag(QGraphicsItem.ItemIsMovable, editable and not is_scope_container)
                node.setFlag(QGraphicsItem.ItemIsSelectable, not is_scope_container)
        for outcome in self.final_outcomes.values():
            if outcome.isVisible():
                outcome.setFlag(QGraphicsItem.ItemIsMovable, editable)
                outcome.setFlag(QGraphicsItem.ItemIsSelectable, True)
        for item in self.preview_items:
            if isinstance(item, (StateNode, ContainerStateNode, FinalOutcomeNode)) and item.isVisible():
                is_scope_container = item is scope_container
                item.setFlag(QGraphicsItem.ItemIsMovable, editable and not is_scope_container)
                item.setFlag(QGraphicsItem.ItemIsSelectable, not is_scope_container or isinstance(item, FinalOutcomeNode))
        if scope_container is not None:
            scope_container.setFlag(QGraphicsItem.ItemIsSelectable, False)
            scope_container.setFlag(QGraphicsItem.ItemIsMovable, False)
            scope_container.setSelected(False)

    def update_scope_header(self) -> None:
        container = self.current_container
        self.root_sm_name_edit.blockSignals(True)
        self.root_sm_description_edit.blockSignals(True)
        self.start_state_combo.blockSignals(True)
        if container is None:
            self.root_sm_name_edit.setText(self.root_sm_name)
            self.root_sm_description_edit.setText(self.root_sm_description)
            self.root_sm_name_edit.setReadOnly(False)
            self.root_sm_description_edit.setReadOnly(False)
        else:
            self.root_sm_name_edit.setText(container.name)
            self.root_sm_description_edit.setText(getattr(container, 'description', ''))
            self.root_sm_name_edit.setReadOnly(self.current_read_only)
            self.root_sm_description_edit.setReadOnly(self.current_read_only)
        self.start_state_combo.setEnabled(not self.current_read_only)
        self.start_state_combo.blockSignals(False)
        self.root_sm_description_edit.blockSignals(False)
        self.root_sm_name_edit.blockSignals(False)
    def navigate_to_index(self, index: int) -> None:
        if index < 0 or index >= len(self.navigation_path):
            return

        self.navigation_path = self.navigation_path[: index + 1]
        _label, container, readonly = self.navigation_path[-1]

        if self.preview_root_container is not None and container is None and index == 0:
            self.clear_preview_scope()
        else:
            self.current_container = container
            self.current_read_only = readonly

        self.update_navigation_ui()
        self.update_start_state_combo()
        self.update_scope_header()
        self.update_scope_visibility()
        self.sync_blackboard_keys()

    def navigate_up(self) -> None:
        if len(self.navigation_path) <= 1:
            return
        self.navigate_to_index(len(self.navigation_path) - 2)

    def _set_item_visible_recursive(self, item, visible: bool) -> None:
        item.setVisible(visible)
        if isinstance(item, ContainerStateNode):
            for child in item.child_states.values():
                self._set_item_visible_recursive(child, visible)
            for outcome in item.final_outcomes.values():
                self._set_item_visible_recursive(outcome, visible)

    def update_scope_visibility(self) -> None:
        for node in self.state_nodes.values():
            if getattr(node, "parent_container", None) is None:
                self._set_item_visible_recursive(node, False)
        for outcome in self.final_outcomes.values():
            outcome.setVisible(False)

        if self.preview_root_container is not None:
            self._set_item_visible_recursive(self.preview_root_container, False)

        all_containers = [
            node for node in self.state_nodes.values() if isinstance(node, ContainerStateNode)
        ]
        all_containers.extend(
            [item for item in self.preview_items if isinstance(item, ContainerStateNode)]
        )

        for container in all_containers:
            container.set_entered(False)
            container.setSelected(False)
            if container is not self.current_container:
                container.setVisible(False)

        for connection in self.connections:
            self._set_connection_visible(connection, False)
        for item in self.preview_items:
            if isinstance(item, ConnectionLine):
                self._set_connection_visible(item, False)

        scope_container = self._get_scope_container()

        if scope_container is None:
            for node in self._get_scope_nodes():
                node.setVisible(True)
            for outcome in self._get_scope_final_outcomes():
                outcome.setVisible(True)
        else:
            scope_container.setVisible(True)
            scope_container.setSelected(False)
            scope_container.setFlag(QGraphicsItem.ItemIsSelectable, False)
            if scope_container.is_state_machine:
                scope_container.set_entered(True)
            for node in scope_container.child_states.values():
                node.setVisible(True)
                node.setSelected(False)
            for outcome in scope_container.final_outcomes.values():
                outcome.setVisible(True)
                outcome.setSelected(False)

        for connection in self.connections:
            self._set_connection_visible(connection, self._get_scope_connection_visibility(connection))
        for item in self.preview_items:
            if isinstance(item, ConnectionLine):
                self._set_connection_visible(item, self._get_scope_connection_visibility(item))

        self.canvas.scene.clearSelection()
        self._apply_scope_item_flags()
        self.canvas.scene.update()
    def filter_blackboard_keys(self, text: str) -> None:
        """Filter blackboard keys based on search text."""
        for i in range(self.blackboard_list.count()):
            item = self.blackboard_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def format_blackboard_key_label(self, key_data: Dict[str, str]) -> str:
        label = f"{key_data.get('name', '')} ({key_data.get('key_type', 'IN')})"

        default_type = str(key_data.get("default_type", "")).strip()
        if default_type:
            default_value = str(key_data.get("default_value", ""))
            label += f" [default: {default_value}, type: {default_type}]"

        return label

    def _get_plugin_key_usage(
        self, state_node: StateNode, key_info: Dict[str, str], is_input: bool
    ) -> Optional[Dict[str, str]]:
        key_name = str(key_info.get("name", "")).strip()
        if not key_name:
            return None

        effective_name = self.get_effective_blackboard_key_name(state_node, key_name)
        if not effective_name:
            return None

        description = str(key_info.get("description", "") or "").strip()
        return {
            "name": effective_name,
            "usage": "input" if is_input else "output",
            "description": description,
        }

    def _collect_blackboard_key_usage(self) -> Dict[str, Dict[str, str]]:
        usage_map: Dict[str, Dict[str, object]] = {}

        for state_node in self._iter_scope_state_nodes_recursive(self._get_scope_container()):
            plugin_info = getattr(state_node, "plugin_info", None)
            if plugin_info is None:
                continue

            for key_info in list(getattr(plugin_info, "input_keys", []) or []):
                usage = self._get_plugin_key_usage(state_node, key_info, True)
                if usage is None:
                    continue
                entry = usage_map.setdefault(
                    usage["name"],
                    {
                        "input": False,
                        "output": False,
                        "description": "",
                    },
                )
                entry["input"] = True
                if not entry["description"] and usage["description"]:
                    entry["description"] = usage["description"]

            for key_info in list(getattr(plugin_info, "output_keys", []) or []):
                usage = self._get_plugin_key_usage(state_node, key_info, False)
                if usage is None:
                    continue
                entry = usage_map.setdefault(
                    usage["name"],
                    {
                        "input": False,
                        "output": False,
                        "description": "",
                    },
                )
                entry["output"] = True
                if not entry["description"] and usage["description"]:
                    entry["description"] = usage["description"]

        derived_keys: Dict[str, Dict[str, str]] = {}
        for key_name, usage in usage_map.items():
            metadata = dict(self._get_active_blackboard_metadata().get(key_name, {}))
            if usage["input"] and usage["output"]:
                key_type = "IN/OUT"
            elif usage["output"]:
                key_type = "OUT"
            else:
                key_type = "IN"

            description = str(metadata.get("description", "") or "").strip()
            if not description:
                description = str(usage.get("description", "") or "").strip()

            default_type = ""
            default_value = ""
            if key_type in ("IN", "IN/OUT"):
                default_type = str(metadata.get("default_type", "") or "")
                if default_type:
                    default_value = str(metadata.get("default_value", "") or "")

            derived_keys[key_name] = {
                "name": key_name,
                "key_type": key_type,
                "description": description,
                "default_type": default_type,
                "default_value": default_value,
            }

        return dict(sorted(derived_keys.items(), key=lambda item: item[0].lower()))

    def sync_blackboard_keys(self) -> None:
        derived_keys = self._collect_blackboard_key_usage()
        used_key_names = set(derived_keys.keys())
        metadata = self._get_active_blackboard_metadata()
        filtered_metadata = {
            key_name: value
            for key_name, value in metadata.items()
            if key_name in used_key_names
        }
        metadata.clear()
        metadata.update(filtered_metadata)
        self._blackboard_keys = list(derived_keys.values())
        self.refresh_blackboard_keys_list()

    def refresh_blackboard_keys_list(self) -> None:
        self._blackboard_keys = list(self._collect_blackboard_key_usage().values())
        current_key_name = self.get_selected_blackboard_key_name()
        self.blackboard_list.clear()

        for key_data in sorted(
            self._blackboard_keys, key=lambda item: item.get("name", "").lower()
        ):
            item = QListWidgetItem(self.format_blackboard_key_label(key_data))
            item.setData(Qt.UserRole, dict(key_data))
            description = key_data.get("description", "")
            if description:
                item.setToolTip(description)
            self.blackboard_list.addItem(item)

        self.filter_blackboard_keys(self.blackboard_filter.text())

        if current_key_name:
            for i in range(self.blackboard_list.count()):
                item = self.blackboard_list.item(i)
                key_data = item.data(Qt.UserRole) or {}
                if key_data.get("name") == current_key_name:
                    self.blackboard_list.setCurrentItem(item)
                    break

        self.update_blackboard_usage_highlighting()

    def get_selected_blackboard_key_name(self) -> Optional[str]:
        item = self.blackboard_list.currentItem()
        if item is None:
            return None
        key_data = item.data(Qt.UserRole) or {}
        return key_data.get("name")

    def edit_selected_blackboard_key(
        self, item: Optional[QListWidgetItem] = None
    ) -> None:
        if item is None:
            item = self.blackboard_list.currentItem()
        if item is None:
            return

        key_data = dict(item.data(Qt.UserRole) or {})
        key_name = key_data.get("name", "")
        if not key_name:
            return

        active_metadata = self._get_active_blackboard_metadata()
        metadata = dict(active_metadata.get(key_name, {}))
        merged_key_data = {
            **key_data,
            **metadata,
            "name": key_data.get("name", ""),
            "key_type": key_data.get("key_type", "IN"),
            "default_type": str(metadata.get("default_type", "") or ""),
            "default_value": str(metadata.get("default_value", "") or ""),
        }

        dlg = BlackboardKeyDialog(merged_key_data, parent=self, edit_mode=True)
        if self.current_read_only:
            self._set_dialog_read_only(dlg)
            dlg.exec_()
            return

        if dlg.exec_():
            updated_key = dlg.get_key_data()
            active_metadata[key_name] = {
                "description": updated_key.get("description", ""),
                "key_type": key_data.get("key_type", "IN"),
                "default_type": updated_key.get("default_type", ""),
                "default_value": updated_key.get("default_value", ""),
            }
            self.sync_blackboard_keys()

    def set_blackboard_keys(self, keys: List[Dict[str, str]], sync: bool = True) -> None:
        self._blackboard_key_metadata = {}
        for key in keys:
            key_name = str(key.get("name", "") or "").strip()
            if not key_name:
                continue
            self._blackboard_key_metadata[key_name] = {
                "description": str(key.get("description", "") or "").strip(),
                "key_type": str(key.get("key_type", "IN") or "IN").strip(),
                "default_type": str(key.get("default_type", "") or "").strip(),
                "default_value": str(key.get("default_value", "") or "").strip(),
            }
        if sync:
            self.sync_blackboard_keys()

    def get_blackboard_keys(self) -> List[Dict[str, str]]:
        self._blackboard_keys = list(self._collect_blackboard_key_usage().values())
        self.refresh_blackboard_keys_list()
        return [dict(key) for key in self._blackboard_keys]

    def add_root_default_row(self) -> None:
        pass

    def remove_root_default_row(self) -> None:
        pass

    def add_root_default_row_with_data(self, data: dict) -> None:
        key_name = str(data.get("key", "") or "").strip()
        if not key_name:
            return
        self._blackboard_key_metadata[key_name] = {
            "description": str(data.get("description", "") or "").strip(),
            "key_type": "IN",
            "default_type": str(data.get("type", "") or "").strip(),
            "default_value": str(data.get("value", "") or "").strip(),
        }
        self.sync_blackboard_keys()

    def get_root_defaults(self) -> list:
        return []

    def on_blackboard_selection_changed(self) -> None:
        self.update_blackboard_usage_highlighting()

    def toggle_blackboard_highlighting(self, enabled: bool) -> None:
        self._highlight_blackboard_usage = enabled
        self.highlight_blackboard_btn.setText(
            "Highlight: On" if enabled else "Highlight: Off"
        )
        self.update_blackboard_usage_highlighting()

    def get_effective_blackboard_key_name(self, state_node, key_name: str) -> str:
        effective_key_name = key_name

        remap_chain = []
        current_node = state_node
        while current_node is not None:
            remap_chain.append(getattr(current_node, "remappings", {}) or {})
            current_node = getattr(current_node, "parent_container", None)

        for remappings in remap_chain:
            effective_key_name = remappings.get(effective_key_name, effective_key_name)

        return effective_key_name

    def _remove_state_node_entries(self, state_node: StateNode, prefix: str = "") -> None:
        full_name = f"{prefix}.{state_node.name}" if prefix else state_node.name
        if isinstance(state_node, ContainerStateNode):
            for child_state in list(state_node.child_states.values()):
                self._remove_state_node_entries(child_state, full_name)
        if full_name in self.state_nodes:
            del self.state_nodes[full_name]

    def state_uses_blackboard_key(self, state_node, key_name: str) -> bool:
        if isinstance(state_node, ContainerStateNode):
            for child_state in state_node.child_states.values():
                if self.state_uses_blackboard_key(child_state, key_name):
                    return True
            return False

        plugin_info = getattr(state_node, "plugin_info", None)
        if plugin_info is None:
            return False

        plugin_keys = []
        for key_info in list(getattr(plugin_info, "input_keys", []) or []) + list(
            getattr(plugin_info, "output_keys", []) or []
        ):
            plugin_key_name = str(key_info.get("name", "")).strip()
            if not plugin_key_name:
                continue
            plugin_keys.append(
                self.get_effective_blackboard_key_name(state_node, plugin_key_name)
            )

        return key_name in plugin_keys

    def apply_default_visual_state(self, item) -> None:
        is_selected = item.isSelected() if hasattr(item, "isSelected") else False

        if isinstance(item, StateNode):
            if item.plugin_info and item.plugin_info.plugin_type == "python":
                item.setBrush(QBrush(QColor(144, 238, 144)))
            elif item.plugin_info and item.plugin_info.plugin_type == "cpp":
                item.setBrush(QBrush(QColor(255, 182, 193)))
            else:
                item.setBrush(QBrush(QColor(255, 165, 0)))
            item.setPen(
                QPen(QColor(255, 200, 0), 4)
                if is_selected
                else QPen(QColor(0, 0, 180), 3)
            )
        elif isinstance(item, ContainerStateNode):
            item.apply_display_mode()
            if item.is_entered():
                item.setBrush(QBrush(Qt.NoBrush))
                item.setPen(QPen(Qt.NoPen))
            elif is_selected:
                item.setPen(QPen(QColor(255, 200, 0), 4))
        elif isinstance(item, FinalOutcomeNode):
            item.setBrush(QBrush(QColor(255, 0, 0)))
            item.setPen(
                QPen(QColor(255, 200, 0), 4) if is_selected else QPen(QColor(0, 0, 0), 3)
            )

    def update_blackboard_usage_highlighting(self) -> None:
        selected_key = self.get_selected_blackboard_key_name()

        scope_container = self._get_scope_container()
        visible_nodes = [
            node
            for node in self.state_nodes.values()
            if node.isVisible() and node is not scope_container
        ]
        for state_node in visible_nodes:
            self.apply_default_visual_state(state_node)

        if not self._highlight_blackboard_usage or not selected_key:
            return

        for state_node in visible_nodes:
            if self.state_uses_blackboard_key(state_node, selected_key):
                state_node.setPen(QPen(QColor(255, 170, 0), 5))
                if not isinstance(state_node, ContainerStateNode):
                    state_node.setBrush(QBrush(QColor(255, 255, 170)))

    def update_start_state_combo(self) -> None:
        """Update the initial state combo box with available states."""
        active_container = self.current_container
        current = active_container.start_state if active_container is not None else self.start_state
        self.start_state_combo.blockSignals(True)
        self.start_state_combo.clear()
        self.start_state_combo.addItem("(None)")

        if active_container is not None:
            state_names = list(active_container.child_states.keys())
        else:
            state_names = [
                node.name
                for node in self._iter_root_state_nodes()
            ]

        for state_name in state_names:
            self.start_state_combo.addItem(state_name)

        if current:
            index = self.start_state_combo.findText(current)
            if index >= 0:
                self.start_state_combo.setCurrentIndex(index)
            else:
                if active_container is not None:
                    active_container.start_state = None
                else:
                    self.start_state = None
                self.start_state_combo.setCurrentIndex(0)
        else:
            self.start_state_combo.setCurrentIndex(0)
        self.start_state_combo.blockSignals(False)

    def on_plugin_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on a plugin item to add it as a state.

        Args:
            item: The list widget item that was double-clicked.
        """
        plugin_info = item.data(Qt.UserRole)
        state_name, ok = QInputDialog.getText(self, "State Name", "Enter state name:")
        if ok:
            self.create_state_node(state_name, plugin_info, False, False)

    def on_xml_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on an XML state machine to add it.

        Args:
            item: The list widget item that was double-clicked.
        """
        xml_plugin = item.data(Qt.UserRole)
        state_name, ok = QInputDialog.getText(
            self, "State Machine Name", "Enter state machine name:"
        )
        if ok:
            self.create_state_node(state_name, xml_plugin, False, False)

    def enter_container(self, container: ContainerStateNode, read_only: bool = False) -> None:
        self.canvas.scene.clearSelection()
        container.setSelected(False)
        self.current_container = container
        self.current_read_only = read_only
        self.navigation_path.append((container.name, container, read_only))
        self.update_navigation_ui()
        self.update_start_state_combo()
        self.update_scope_header()
        self.update_scope_visibility()
        self.sync_blackboard_keys()

    def _find_xml_file_path(self, plugin_info: PluginInfo) -> Optional[str]:
        if (
            plugin_info.plugin_type != "xml"
            or not plugin_info.file_name
            or not plugin_info.package_name
        ):
            return None

        package_path = Path(get_package_share_path(plugin_info.package_name))
        for file_path in package_path.rglob(plugin_info.file_name):
            return str(file_path)
        return None

    def clear_preview_scope(self) -> None:
        for item in reversed(list(self.preview_items)):
            try:
                if hasattr(item, "scene") and item.scene() is self.canvas.scene:
                    self.canvas.scene.removeItem(item)
            except Exception:
                pass
        self.preview_items = []
        self.preview_root_container = None
        self.current_container = None
        self.current_read_only = False
        self.navigation_path = [("root", None, False)]
        self.update_scope_header()
        self.update_start_state_combo()

    def _create_preview_connection(self, from_node, to_node, outcome: str) -> None:
        connection = ConnectionLine(from_node, to_node, outcome)
        self.canvas.scene.addItem(connection)
        self.canvas.scene.addItem(connection.arrow_head)
        self.canvas.scene.addItem(connection.label_bg)
        self.canvas.scene.addItem(connection.label)
        self.preview_items.extend(
            [connection, connection.arrow_head, connection.label_bg, connection.label]
        )

    def _build_preview_container(
        self, parent_elem: ET.Element, name: str
    ) -> ContainerStateNode:
        preview_container = ContainerStateNode(
            name,
            0,
            0,
            False,
            {},
            parent_elem.get("outcomes", "").split()
            if parent_elem.get("outcomes")
            else [],
            parent_elem.get("start_state"),
            None,
            parent_elem.get("description", ""),
            [],
        )
        self.canvas.scene.addItem(preview_container)
        self.preview_items.append(preview_container)
        local_nodes = {}

        for elem in parent_elem:
            is_xml_plugin_state = elem.tag == "StateMachine" and elem.get("file_name")
            is_regular_state = elem.tag == "State"
            if is_regular_state or is_xml_plugin_state:
                state_name = elem.get("name", "")
                state_type = elem.get("type", "py")
                plugin_info = None
                if state_type == "py":
                    plugin_info = next(
                        (
                            p
                            for p in self.plugin_manager.python_plugins
                            if p.module == elem.get("module")
                            and p.class_name == elem.get("class")
                        ),
                        None,
                    )
                elif state_type == "cpp":
                    plugin_info = next(
                        (
                            p
                            for p in self.plugin_manager.cpp_plugins
                            if p.class_name == elem.get("class")
                        ),
                        None,
                    )
                elif state_type == "xml":
                    plugin_info = next(
                        (
                            p
                            for p in self.plugin_manager.xml_files
                            if p.file_name == elem.get("file_name")
                            and (
                                elem.get("package") is None
                                or p.package_name == elem.get("package")
                            )
                        ),
                        None,
                    )
                if plugin_info is None:
                    continue
                node = StateNode(
                    state_name,
                    plugin_info,
                    0,
                    0,
                    {},
                    elem.get("description", ""),
                    [],
                )
                preview_container.add_child_state(node)
                self.preview_items.append(node)
                local_nodes[state_name] = node
            elif elem.tag == "StateMachine" and not elem.get("file_name"):
                state_name = elem.get("name", "")
                node = ContainerStateNode(
                    state_name,
                    0,
                    0,
                    False,
                    {},
                    elem.get("outcomes", "").split()
                    if elem.get("outcomes")
                    else [],
                    elem.get("start_state"),
                    None,
                    elem.get("description", ""),
                    [],
                )
                preview_container.add_child_state(node)
                self.preview_items.append(node)
                local_nodes[state_name] = node
                self._fill_preview_container(node, elem)
            elif elem.tag == "Concurrence":
                state_name = elem.get("name", "")
                node = ContainerStateNode(
                    state_name,
                    0,
                    0,
                    True,
                    {},
                    elem.get("outcomes", "").split()
                    if elem.get("outcomes")
                    else [],
                    None,
                    elem.get("default_outcome"),
                    elem.get("description", ""),
                    [],
                )
                preview_container.add_child_state(node)
                self.preview_items.append(node)
                local_nodes[state_name] = node
                self._fill_preview_container(node, elem)

        for outcome_spec in self.xml_manager._preview_outcome_specs(parent_elem):
            outcome_node = FinalOutcomeNode(
                outcome_spec["name"],
                0,
                0,
                inside_container=True,
                description=outcome_spec.get("description", ""),
            )
            preview_container.add_final_outcome(outcome_node)
            x = outcome_spec.get("x")
            y = outcome_spec.get("y")
            if x is not None and y is not None:
                try:
                    outcome_node.setPos(float(x), float(y))
                    outcome_node._xml_position_loaded = True
                except ValueError:
                    outcome_node._xml_position_loaded = False
            self.preview_items.append(outcome_node)
        preview_container.blackboard_key_metadata = {
            str(key.get("name", "")).strip(): {
                "description": str(key.get("description", "") or "").strip(),
                "key_type": str(key.get("key_type", "IN") or "IN").strip(),
                "default_type": str(key.get("default_type", "") or "").strip(),
                "default_value": str(key.get("default_value", "") or "").strip(),
            }
            for key in self.xml_manager.load_blackboard_keys(parent_elem)
            if str(key.get("name", "")).strip()
        } if hasattr(self, 'xml_manager') else {}
        self._fill_preview_connections(preview_container, parent_elem, local_nodes)
        preview_container.auto_resize_for_children()
        return preview_container

    def _fill_preview_container(
        self, preview_container: ContainerStateNode, parent_elem: ET.Element
    ) -> None:
        local_nodes = {}
        for elem in parent_elem:
            is_xml_plugin_state = elem.tag == "StateMachine" and elem.get("file_name")
            is_regular_state = elem.tag == "State"
            if is_regular_state or is_xml_plugin_state:
                state_name = elem.get("name", "")
                state_type = elem.get("type", "py")
                plugin_info = None
                if state_type == "py":
                    plugin_info = next(
                        (
                            p
                            for p in self.plugin_manager.python_plugins
                            if p.module == elem.get("module")
                            and p.class_name == elem.get("class")
                        ),
                        None,
                    )
                elif state_type == "cpp":
                    plugin_info = next(
                        (
                            p
                            for p in self.plugin_manager.cpp_plugins
                            if p.class_name == elem.get("class")
                        ),
                        None,
                    )
                elif state_type == "xml":
                    plugin_info = next(
                        (
                            p
                            for p in self.plugin_manager.xml_files
                            if p.file_name == elem.get("file_name")
                            and (
                                elem.get("package") is None
                                or p.package_name == elem.get("package")
                            )
                        ),
                        None,
                    )
                if plugin_info is None:
                    continue
                node = StateNode(
                    state_name,
                    plugin_info,
                    0,
                    0,
                    {},
                    elem.get("description", ""),
                    [],
                )
                preview_container.add_child_state(node)
                self.preview_items.append(node)
                local_nodes[state_name] = node
            elif elem.tag == "StateMachine" and not elem.get("file_name"):
                state_name = elem.get("name", "")
                node = ContainerStateNode(
                    state_name,
                    0,
                    0,
                    False,
                    {},
                    elem.get("outcomes", "").split()
                    if elem.get("outcomes")
                    else [],
                    elem.get("start_state"),
                    None,
                    elem.get("description", ""),
                    [],
                )
                preview_container.add_child_state(node)
                self.preview_items.append(node)
                local_nodes[state_name] = node
                self._fill_preview_container(node, elem)
            elif elem.tag == "Concurrence":
                state_name = elem.get("name", "")
                node = ContainerStateNode(
                    state_name,
                    0,
                    0,
                    True,
                    {},
                    elem.get("outcomes", "").split()
                    if elem.get("outcomes")
                    else [],
                    None,
                    elem.get("default_outcome"),
                    elem.get("description", ""),
                    [],
                )
                preview_container.add_child_state(node)
                self.preview_items.append(node)
                local_nodes[state_name] = node
                self._fill_preview_container(node, elem)

        for outcome_spec in self.xml_manager._preview_outcome_specs(parent_elem):
            outcome_node = FinalOutcomeNode(
                outcome_spec["name"],
                0,
                0,
                inside_container=True,
                description=outcome_spec.get("description", ""),
            )
            preview_container.add_final_outcome(outcome_node)
            x = outcome_spec.get("x")
            y = outcome_spec.get("y")
            if x is not None and y is not None:
                try:
                    outcome_node.setPos(float(x), float(y))
                    outcome_node._xml_position_loaded = True
                except ValueError:
                    outcome_node._xml_position_loaded = False
            self.preview_items.append(outcome_node)

        self._fill_preview_connections(preview_container, parent_elem, local_nodes)
        preview_container.auto_resize_for_children()

    def _fill_preview_connections(
        self,
        preview_container: ContainerStateNode,
        parent_elem: ET.Element,
        local_nodes: Dict[str, object],
    ) -> None:
        for elem in parent_elem:
            if elem.tag not in ["State", "StateMachine", "Concurrence"]:
                continue
            from_node = local_nodes.get(elem.get("name", ""))
            if from_node is None:
                continue
            final_outcome_names = (
                set(from_node.final_outcomes.keys())
                if isinstance(from_node, ContainerStateNode)
                else set()
            )
            for transition in elem.findall("Transition"):
                outcome = transition.get("from", "")
                target_name = transition.get("to", "")
                source_node = from_node
                target_node = (
                    local_nodes.get(target_name)
                    or preview_container.final_outcomes.get(target_name)
                )
                if target_node is not None:
                    self._create_preview_connection(source_node, target_node, outcome)

    def enter_xml_preview(self, state_node: StateNode) -> None:
        xml_path = self._find_xml_file_path(state_node.plugin_info)
        if xml_path is None:
            return
        self.clear_preview_scope()
        tree = ET.parse(xml_path)
        root = tree.getroot()
        self.preview_root_container = self._build_preview_container(
            root, root.get("name", state_node.name)
        )
        self.preview_root_container.setSelected(False)
        self.preview_root_container.set_entered(True)
        self.current_container = self.preview_root_container
        self.current_read_only = True
        self.navigation_path = [("root", None, False), (state_node.name, self.preview_root_container, True)]
        self.update_navigation_ui()
        self.update_start_state_combo()
        self.update_scope_header()
        self.update_scope_visibility()
        self.sync_blackboard_keys()

    def get_free_position(self) -> QPointF:
        """Get a free position in a deterministic grid layout.

        Uses a fixed grid starting from (100, 100) and places nodes in a predictable
        left-to-right, top-to-bottom pattern to ensure consistent positioning across
        different runs.

        Returns:
            QPointF: The calculated free position for a new node.
        """
        active_container = self._get_active_edit_container()
        if active_container is not None:
            item_count = len(active_container.child_states) + len(active_container.final_outcomes)
            rect = active_container.get_child_bounds_rect()
            start_x = rect.left() + 120
            start_y = rect.top() + 140
            node_width = 340
            node_height = 240
            nodes_per_row = 3
            row = item_count // nodes_per_row
            col = item_count % nodes_per_row
            return QPointF(start_x + (col * node_width), start_y + (row * node_height))

        START_X = 100
        START_Y = 100
        NODE_WIDTH = 400
        NODE_HEIGHT = 350
        NODES_PER_ROW = 3

        root_nodes = [
            node
            for node in self.state_nodes.values()
            if not hasattr(node, "parent_container") or node.parent_container is None
        ]

        all_items = list(root_nodes) + list(self.final_outcomes.values())

        num_items = len(all_items)
        row = num_items // NODES_PER_ROW
        col = num_items % NODES_PER_ROW

        x = START_X + (col * NODE_WIDTH)
        y = START_Y + (row * NODE_HEIGHT)

        return QPointF(x, y)

    def create_state_node(
        self,
        name: str,
        plugin_info: PluginInfo,
        is_state_machine: bool = False,
        is_concurrence: bool = False,
        outcomes: List[str] = None,
        remappings: Dict[str, str] = None,
        start_state: str = None,
        default_outcome: str = None,
        description: str = "",
        defaults: List[Dict[str, str]] = None,
    ) -> None:
        """Create a new state node in the canvas.

        Args:
            name: Name of the state.
            plugin_info: Plugin information for the state.
            is_state_machine: Whether this is a state machine container.
            is_concurrence: Whether this is a concurrence container.
            outcomes: List of outcome names.
            remappings: Dictionary of key remappings.
            start_state: Initial state for state machines.
            default_outcome: Default outcome for concurrences.
        """
        if not name:
            QMessageBox.warning(self, "Validation Error", "Name is required!")
            return

        active_container = self._get_active_edit_container()
        if active_container is None and name in [node.name for node in self._iter_root_state_nodes()]:
            QMessageBox.warning(self, "Error", f"State '{name}' already exists!")
            return

        if active_container is not None and name in active_container.child_states:
            QMessageBox.warning(
                self,
                "Error",
                f"State '{name}' already exists in this container!",
            )
            return

        pos = self.get_free_position()

        if is_state_machine or is_concurrence:
            node = ContainerStateNode(
                name,
                pos.x(),
                pos.y(),
                is_concurrence,
                remappings,
                outcomes,
                start_state,
                default_outcome,
                description or "",
                defaults,
            )
        else:
            node = StateNode(
                name,
                plugin_info,
                pos.x(),
                pos.y(),
                remappings,
                description or "",
                defaults,
            )

        self.canvas.scene.addItem(node)

        if active_container is not None:
            active_container.add_child_state(node)
            self._rebuild_state_node_index()
            if active_container.is_state_machine and len(active_container.child_states) == 1:
                active_container.start_state = name
                active_container.update_start_state_label()
        else:
            self.state_nodes[name] = node
            self._rebuild_state_node_index()
            self.update_start_state_combo()

            if len(
                [node for node in self.state_nodes.values() if getattr(node, "parent_container", None) is None]
            ) == 1 and not self.start_state:
                self.start_state = name
                index = self.start_state_combo.findText(name)
                if index >= 0:
                    self.start_state_combo.setCurrentIndex(index)

        self.update_start_state_combo()
        self.update_scope_visibility()
        self.sync_blackboard_keys()
        self.statusBar().showMessage(f"Added state: {name}", 2000)

    def add_state(self) -> None:
        """Open dialog to add a new state to the state machine."""
        if self.current_read_only:
            return
        all_plugins = (
            self.plugin_manager.python_plugins
            + self.plugin_manager.cpp_plugins
            + self.plugin_manager.xml_files
        )
        dialog = StatePropertiesDialog(available_plugins=all_plugins, parent=self)
        if dialog.exec_():
            result = dialog.get_state_data()
            if result[0]:
                name, plugin, outcomes, remappings, description, defaults = result
                self.create_state_node(
                    name,
                    plugin,
                    outcomes=outcomes,
                    remappings=remappings,
                    description=description,
                    defaults=defaults,
                )

    def add_container(self, is_concurrence: bool = False) -> None:
        """Add a new container (State Machine or Concurrence)."""
        if self.current_read_only:
            return
        dialog = (
            ConcurrenceDialog(parent=self)
            if is_concurrence
            else StateMachineDialog(parent=self)
        )
        if dialog.exec_():
            result = (
                dialog.get_concurrence_data()
                if is_concurrence
                else dialog.get_state_machine_data()
            )
            if result:
                name, outcomes, param, remappings, description, defaults = result
                self.create_state_node(
                    name=name,
                    plugin_info=None,
                    is_state_machine=not is_concurrence,
                    is_concurrence=is_concurrence,
                    outcomes=outcomes,
                    remappings=remappings,
                    start_state=param if not is_concurrence else None,
                    default_outcome=param if is_concurrence else None,
                    description=description,
                    defaults=defaults,
                )

    def add_state_machine(self) -> None:
        """Add a new State Machine container."""
        self.add_container(False)

    def add_concurrence(self) -> None:
        """Add a new Concurrence container."""
        self.add_container(True)

    def edit_state(self) -> None:
        """Edit properties of the selected state."""
        read_only = self.current_read_only

        selected_items = self.canvas.scene.selectedItems()
        state_node = None

        for item in selected_items:
            if isinstance(item, (StateNode, ContainerStateNode)):
                state_node = item
                break

        if not state_node:
            QMessageBox.warning(self, "Error", "Please select a state to edit!")
            return

        old_name = state_node.name

        if isinstance(state_node, ContainerStateNode):
            if state_node.is_state_machine:
                dialog = StatePropertiesDialog(
                    state_name=state_node.name,
                    plugin_info=None,
                    available_plugins=[],
                    remappings=state_node.remappings,
                    outcomes=list(state_node.final_outcomes.keys()) if state_node.final_outcomes else [],
                    edit_mode=True,
                    parent=self,
                    description=getattr(state_node, "description", ""),
                    defaults=getattr(state_node, "defaults", []),
                )

                if read_only:
                    self._set_dialog_read_only(dialog)
                    dialog.exec_()
                    return

                if dialog.exec_():
                    result = dialog.get_state_data()
                    if result[0]:
                        name, _plugin, _outcomes, remappings, description, defaults = result

                        sibling_names = []
                        if state_node.parent_container is not None:
                            sibling_names = [n for n in state_node.parent_container.child_states.keys() if n != old_name]
                        else:
                            sibling_names = [n.name for n in self._iter_root_state_nodes() if n.name != old_name]

                        if name != old_name:
                            if name in sibling_names:
                                QMessageBox.warning(
                                    self, "Error", f"State '{name}' already exists!"
                                )
                                return

                            if self.start_state == old_name:
                                self.start_state = name

                            if state_node.parent_container and old_name in state_node.parent_container.child_states:
                                del state_node.parent_container.child_states[old_name]
                                state_node.parent_container.child_states[name] = state_node
                            state_node.name = name
                            self._rebuild_state_node_index()
                            state_node.apply_display_mode()
                            self.update_navigation_ui()
                            self.update_start_state_combo()

                        state_node.remappings = remappings
                        state_node.description = description
                        state_node.defaults = defaults

                        self.sync_blackboard_keys()
                        self.statusBar().showMessage(
                            f"Updated state machine: {name}", 2000
                        )
            elif state_node.is_concurrence:
                final_outcome_names = (
                    list(state_node.final_outcomes.keys())
                    if state_node.final_outcomes
                    else []
                )

                dialog = ConcurrenceDialog(
                    name=state_node.name,
                    outcomes=(
                        list(state_node.final_outcomes.keys())
                        if state_node.final_outcomes
                        else []
                    ),
                    default_outcome=state_node.default_outcome,
                    remappings=state_node.remappings,
                    final_outcomes=final_outcome_names,
                    edit_mode=True,
                    parent=self,
                    description=getattr(state_node, "description", ""),
                    defaults=getattr(state_node, "defaults", []),
                )

                if read_only:
                    self._set_dialog_read_only(dialog)
                    dialog.exec_()
                    return

                if dialog.exec_():
                    result = dialog.get_concurrence_data()
                    if result:
                        (
                            name,
                            outcomes,
                            default_outcome,
                            remappings,
                            description,
                            defaults,
                        ) = result

                        if name != old_name:
                            if name in self.state_nodes:
                                QMessageBox.warning(
                                    self, "Error", f"State '{name}' already exists!"
                                )
                                return

                            if self.start_state == old_name:
                                self.start_state = name

                            if state_node.parent_container and old_name in state_node.parent_container.child_states:
                                del state_node.parent_container.child_states[old_name]
                                state_node.parent_container.child_states[name] = state_node
                            state_node.name = name
                            self._rebuild_state_node_index()
                            state_node.apply_display_mode()
                            self.update_start_state_combo()

                        state_node.remappings = remappings
                        state_node.description = description
                        state_node.defaults = defaults
                        state_node.default_outcome = default_outcome
                        state_node.update_default_outcome_label()

                        self.sync_blackboard_keys()
                        self.statusBar().showMessage(f"Updated concurrence: {name}", 2000)
        else:
            dialog = StatePropertiesDialog(
                state_name=state_node.name,
                plugin_info=(
                    state_node.plugin_info if hasattr(state_node, "plugin_info") else None
                ),
                available_plugins=(
                    [state_node.plugin_info]
                    if hasattr(state_node, "plugin_info") and state_node.plugin_info
                    else []
                ),
                remappings=state_node.remappings,
                outcomes=None,
                edit_mode=True,
                parent=self,
                description=getattr(state_node, "description", ""),
                defaults=getattr(state_node, "defaults", []),
            )

            if read_only:
                self._set_dialog_read_only(dialog)
                dialog.exec_()
                return

            if dialog.exec_():
                result = dialog.get_state_data()
                if result[0]:
                    name, plugin, outcomes, remappings, description, defaults = result

                    if name != old_name:
                        if name in self.state_nodes:
                            QMessageBox.warning(
                                self, "Error", f"State '{name}' already exists!"
                            )
                            return

                        if self.start_state == old_name:
                            self.start_state = name

                        if state_node.parent_container and old_name in state_node.parent_container.child_states:
                            del state_node.parent_container.child_states[old_name]
                            state_node.parent_container.child_states[name] = state_node
                        state_node.name = name
                        self._rebuild_state_node_index()
                        state_node.text.setPlainText(name)
                        text_rect = state_node.text.boundingRect()
                        state_node.text.setPos(
                            -text_rect.width() / 2, -text_rect.height() / 2
                        )
                        self.update_start_state_combo()

                    state_node.remappings = remappings
                    state_node.description = description
                    state_node.defaults = defaults
                    self.sync_blackboard_keys()
                    self.statusBar().showMessage(f"Updated state: {name}", 2000)

    def edit_final_outcome(self, outcome_node: Optional[FinalOutcomeNode] = None) -> None:
        """Edit the description of a final outcome."""
        read_only = self.current_read_only
        if outcome_node is None:
            selected_items = self.canvas.scene.selectedItems()
            for item in selected_items:
                if isinstance(item, FinalOutcomeNode):
                    outcome_node = item
                    break

        if outcome_node is None:
            QMessageBox.warning(self, "Error", "Please select a final outcome to edit!")
            return

        dialog = OutcomeDescriptionDialog(
            outcome_name=outcome_node.name,
            description=getattr(outcome_node, "description", ""),
            parent=self,
        )

        if read_only:
            self._set_dialog_read_only(dialog)
            dialog.exec_()
            return

        if dialog.exec_():
            outcome_node.description = dialog.get_description()
            outcome_node.update_tooltip()
            self.statusBar().showMessage(
                f"Updated outcome description: {outcome_node.name}",
                2000,
            )

    def add_state_to_container(self) -> None:
        """Add a child state to the selected container (SM or Concurrence)."""
        selected_items = self.canvas.scene.selectedItems()
        container = None

        for item in selected_items:
            if isinstance(item, ContainerStateNode):
                container = item
                break

        if not container:
            QMessageBox.warning(
                self,
                "Error",
                "Please select a user-created Container State Machine or Concurrence!",
            )
            return

        all_plugins = (
            self.plugin_manager.python_plugins
            + self.plugin_manager.cpp_plugins
            + self.plugin_manager.xml_files
        )
        dialog = StatePropertiesDialog(available_plugins=all_plugins, parent=self)

        if dialog.exec_():
            result = dialog.get_state_data()
            if result[0]:
                name, plugin, outcomes, remappings, description, defaults = result

                if name in container.child_states:
                    QMessageBox.warning(
                        self, "Error", f"State '{name}' already exists in this container!"
                    )
                    return

                child_node = StateNode(
                    name, plugin, 0, 0, remappings, description, defaults
                )
                container.add_child_state(child_node)
                self._rebuild_state_node_index()

                self.sync_blackboard_keys()
                self.statusBar().showMessage(
                    f"Added state '{name}' to container '{container.name}'", 2000
                )

                if container.is_state_machine and len(container.child_states) == 1:
                    container.start_state = name
                    container.update_start_state_label()

    def add_state_machine_to_container(self) -> None:
        """Add a State Machine to the selected container."""
        selected_items = self.canvas.scene.selectedItems()
        container = None

        for item in selected_items:
            if isinstance(item, ContainerStateNode):
                container = item
                break

        if not container:
            QMessageBox.warning(self, "Error", "Please select a user-created Container!")
            return

        dialog = StateMachineDialog(parent=self)

        if dialog.exec_():
            result = dialog.get_state_machine_data()
            if result:
                name, outcomes, start_state, remappings, description, defaults = result

                if name in container.child_states:
                    QMessageBox.warning(
                        self, "Error", f"State '{name}' already exists in this container!"
                    )
                    return

                child_sm = ContainerStateNode(
                    name,
                    0,
                    0,
                    False,
                    remappings,
                    outcomes,
                    start_state,
                    None,
                    description=description,
                    defaults=defaults,
                )
                container.add_child_state(child_sm)
                self._rebuild_state_node_index()

                self.sync_blackboard_keys()
                self.statusBar().showMessage(
                    f"Added State Machine '{name}' to container '{container.name}'", 2000
                )

                if container.is_state_machine and len(container.child_states) == 1:
                    container.start_state = name
                    container.update_start_state_label()

    def add_concurrence_to_container(self) -> None:
        """Add a Concurrence to the selected container."""
        selected_items = self.canvas.scene.selectedItems()
        container = None

        for item in selected_items:
            if isinstance(item, ContainerStateNode):
                container = item
                break

        if not container:
            QMessageBox.warning(self, "Error", "Please select a user-created Container!")
            return

        dialog = ConcurrenceDialog(parent=self)

        if dialog.exec_():
            result = dialog.get_concurrence_data()
            if result:
                name, outcomes, default_outcome, remappings, description, defaults = (
                    result
                )

                if name in container.child_states:
                    QMessageBox.warning(
                        self, "Error", f"State '{name}' already exists in this container!"
                    )
                    return

                child_cc = ContainerStateNode(
                    name,
                    0,
                    0,
                    True,
                    remappings,
                    outcomes,
                    None,
                    default_outcome,
                    description=description,
                    defaults=defaults,
                )
                container.add_child_state(child_cc)
                self._rebuild_state_node_index()

                self.sync_blackboard_keys()
                self.statusBar().showMessage(
                    f"Added Concurrence '{name}' to container '{container.name}'", 2000
                )

                if container.is_state_machine and len(container.child_states) == 1:
                    container.start_state = name
                    container.update_start_state_label()

    def create_connection_from_drag(
        self, from_node: StateNode, to_node: StateNode
    ) -> None:
        """Create a connection when user drags from one node to another.

        Args:
            from_node: The source node.
            to_node: The target node.
        """
        source_anchor = from_node
        has_outcomes = False
        outcomes_list = []

        if isinstance(from_node, ContainerStateNode):
            if from_node.is_concurrence:
                QMessageBox.warning(
                    self,
                    "Not Allowed",
                    "Concurrence states cannot have external transitions.",
                )
                return
            outcomes_list = list(from_node.final_outcomes.keys())
            has_outcomes = bool(outcomes_list)
        elif hasattr(from_node, "plugin_info") and from_node.plugin_info:
            has_outcomes = True
            outcomes_list = list(from_node.plugin_info.outcomes)
        elif isinstance(from_node, FinalOutcomeNode) and from_node.inside_container:
            has_outcomes = True
            outcomes_list = [from_node.name]

        if not has_outcomes or not outcomes_list:
            QMessageBox.warning(
                self,
                "Error",
                "Cannot create transitions from states without outcomes!",
            )
            return

        is_in_concurrence = False
        parent_concurrence = None
        if hasattr(from_node, "parent_container") and from_node.parent_container:
            if isinstance(from_node.parent_container, ContainerStateNode):
                is_in_concurrence = from_node.parent_container.is_concurrence
                if is_in_concurrence:
                    parent_concurrence = from_node.parent_container

        if is_in_concurrence:
            is_valid_target = (
                isinstance(to_node, FinalOutcomeNode)
                and to_node.inside_container
                and to_node.parent_container == parent_concurrence
            ) or (
                isinstance(from_node, FinalOutcomeNode)
                and from_node.inside_container
                and to_node.parent_container != parent_concurrence
            )

            if not is_valid_target:
                QMessageBox.warning(
                    self,
                    "Not Allowed",
                    "States inside a Concurrence can only transition to Final Outcomes inside the same Concurrence.",
                )
                return

        if not is_in_concurrence:
            available_outcomes = [
                o
                for o in outcomes_list
                if not self._is_outcome_used(source_anchor, o)
            ]

            if not available_outcomes:
                QMessageBox.warning(
                    self, "Error", "All outcomes from this state are already used!"
                )
                return
        else:
            available_outcomes = outcomes_list

        if len(available_outcomes) == 1:
            outcome = available_outcomes[0]
            self.create_connection(source_anchor, to_node, outcome)
        else:
            outcome, ok = QInputDialog.getItem(
                self,
                "Select Outcome",
                f"Select outcome for transition from '{from_node.name}':",
                available_outcomes,
                0,
                False,
            )
            if ok:
                self.create_connection(source_anchor, to_node, outcome)

    def create_connection(
        self, from_node: StateNode, to_node: StateNode, outcome: str
    ) -> None:
        """Create and add a connection to the scene.

        Args:
            from_node: The source node.
            to_node: The target node.
            outcome: The outcome name for this transition.
        """
        is_in_concurrence = False
        if hasattr(from_node, "parent_container") and from_node.parent_container:
            if isinstance(from_node.parent_container, ContainerStateNode):
                is_in_concurrence = from_node.parent_container.is_concurrence

        if not is_in_concurrence and self._is_outcome_used(from_node, outcome):
            QMessageBox.warning(
                self,
                "Error",
                f"Outcome '{outcome}' is already used for a transition!",
            )
            return

        connection = ConnectionLine(from_node, to_node, outcome)
        self.canvas.scene.addItem(connection)
        self.canvas.scene.addItem(connection.arrow_head)
        self.canvas.scene.addItem(connection.label_bg)
        self.canvas.scene.addItem(connection.label)
        self.connections.append(connection)

        for conn in self.connections:
            if (conn.from_node == from_node and conn.to_node == to_node) or (
                conn.from_node == to_node and conn.to_node == from_node
            ):
                conn.update_position()

        self.statusBar().showMessage(
            f"Added transition: {from_node.name} --[{outcome}]--> {to_node.name}",
            2000,
        )

    def add_final_outcome(self) -> None:
        """Add a final outcome to the state machine or selected container."""
        if self.current_read_only:
            return
        outcome_name, ok = QInputDialog.getText(
            self, "Final Outcome", "Enter final outcome name:"
        )
        if not (ok and outcome_name):
            return

        active_container = self._get_active_edit_container()
        if active_container is not None:
            if outcome_name in active_container.final_outcomes:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Final outcome '{outcome_name}' already exists in this container!",
                )
                return

            node = FinalOutcomeNode(outcome_name, 0, 0, inside_container=True)
            active_container.add_final_outcome(node)

            if active_container.is_concurrence and len(active_container.final_outcomes) == 1:
                if not active_container.default_outcome:
                    active_container.default_outcome = outcome_name
                    active_container.update_default_outcome_label()

            self.update_scope_visibility()
            self.statusBar().showMessage(
                f"Added final outcome '{outcome_name}' to container '{active_container.name}'",
                2000,
            )
            return

        if outcome_name in self.final_outcomes:
            QMessageBox.warning(
                self, "Error", f"Final outcome '{outcome_name}' already exists!"
            )
            return

        x = 600
        y = len(self.final_outcomes) * 150
        node = FinalOutcomeNode(outcome_name, x, y)
        self.canvas.scene.addItem(node)
        self.final_outcomes[outcome_name] = node
        self.update_scope_visibility()
        self.statusBar().showMessage(f"Added final outcome: {outcome_name}", 2000)

    def delete_selected(self) -> None:
        """Delete the selected items from the canvas."""
        if self.current_read_only:
            return
        selected_items = self.canvas.scene.selectedItems()

        for item in selected_items:
            if isinstance(item, (StateNode, ContainerStateNode)):
                for connection in item.connections[:]:
                    if connection.from_node == item:
                        connection.to_node.remove_connection(connection)
                    else:
                        connection.from_node.remove_connection(connection)

                    self.canvas.scene.removeItem(connection)
                    self.canvas.scene.removeItem(connection.arrow_head)
                    self.canvas.scene.removeItem(connection.label_bg)
                    self.canvas.scene.removeItem(connection.label)
                    if connection in self.connections:
                        self.connections.remove(connection)

                if hasattr(item, "parent_container") and item.parent_container:
                    parent = item.parent_container

                    if item.name in parent.child_states:
                        del parent.child_states[item.name]

                    self._remove_state_node_entries(item, parent.name)
                    self._rebuild_state_node_index()

                    parent.auto_resize_for_children()
                    self.canvas.scene.removeItem(item)
                    self.sync_blackboard_keys()
                    self.statusBar().showMessage(
                        f"Deleted nested state: {item.name}", 2000
                    )
                else:
                    self.canvas.scene.removeItem(item)
                    self._remove_state_node_entries(item)
                    self._rebuild_state_node_index()
                    self.update_start_state_combo()
                    self.sync_blackboard_keys()
                    self.statusBar().showMessage(f"Deleted state: {item.name}", 2000)

            elif isinstance(item, FinalOutcomeNode):
                for connection in item.connections[:]:
                    if connection.from_node == item:
                        connection.to_node.remove_connection(connection)
                    else:
                        connection.from_node.remove_connection(connection)

                    self.canvas.scene.removeItem(connection)
                    self.canvas.scene.removeItem(connection.arrow_head)
                    self.canvas.scene.removeItem(connection.label_bg)
                    self.canvas.scene.removeItem(connection.label)
                    if connection in self.connections:
                        self.connections.remove(connection)

                if item.parent_container:
                    if item.name in item.parent_container.final_outcomes:
                        del item.parent_container.final_outcomes[item.name]
                    item.parent_container.auto_resize_for_children()
                    self.canvas.scene.removeItem(item)
                else:
                    self.canvas.scene.removeItem(item)
                    if item.name in self.final_outcomes:
                        del self.final_outcomes[item.name]

                self.statusBar().showMessage(f"Deleted final outcome: {item.name}", 2000)

            elif isinstance(item, ConnectionLine):
                item.from_node.remove_connection(item)
                item.to_node.remove_connection(item)
                self.canvas.scene.removeItem(item)
                self.canvas.scene.removeItem(item.arrow_head)
                self.canvas.scene.removeItem(item.label_bg)
                self.canvas.scene.removeItem(item.label)
                if item in self.connections:
                    self.connections.remove(item)
                self.statusBar().showMessage("Deleted transition", 2000)

    def show_help(self) -> None:
        """Display help dialog with usage instructions."""
        help_text = """
        <h2>YASMIN Editor - Quick Guide</h2>
        <h3>File Operations</h3>
        <b>New/Open/Save:</b> Create, load, or save state machines from XML files.
        <h3>Building State Machines</h3>
        <b>State Machine Name:</b> Set root name.<br>
        <b>Start State:</b> Select initial state.<br>
        <b>Add State:</b> Add regular state (Python/C++/XML).<br>
        <b>Add State Machine:</b> Add nested container.<br>
        <b>Add Concurrence:</b> Add parallel container.<br>
        <b>Add Final Outcome:</b> Add exit point.
        <h3>Working with States</h3>
        <b>Double-click:</b> Plugin to add state.<br>
        <b>Right-click:</b> State options.<br>
        <b>Drag:</b> Reposition states.<br>
        <b>Delete Selected:</b> Remove items.
        <h3>Creating Transitions</h3>
        <b>Drag from blue port:</b> Create transitions.<br>
        <b>Select outcome:</b> Choose trigger.
        <h3>Containers</h3>
        <b>Nested States:</b> Double-click to edit.<br>
        <b>Final Outcomes:</b> Exit points.<br>
        <b>State Machine:</b> Sequential.<br>
        <b>Concurrence:</b> Parallel.
        <h3>Canvas Navigation</h3>
        <b>Scroll:</b> Zoom.<br>
        <b>Drag:</b> Pan.
        <h3>Validation</h3>
        • Name set<br>
        • Start state selected<br>
        • Final outcome exists<br>
        • Unique names
        <h3>Tips</h3>
        • Use filters to find states.<br>
        • Containers auto-resize.<br>
        • Concurrence states transition to internal final outcomes.<br>
        • XML SMs are regular states.
        """

        dialog = QDialog(self)
        dialog.setWindowTitle("YASMIN Editor Help")
        dialog.setMinimumSize(600, 500)
        dialog.setMaximumSize(800, 600)
        layout = QVBoxLayout(dialog)
        text_browser = QTextBrowser()
        text_browser.setHtml(help_text)
        text_browser.setOpenExternalLinks(False)
        layout.addWidget(text_browser)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        ok_button.setDefault(True)
        button_layout.addWidget(ok_button)
        dialog.exec_()

    def new_state_machine(self) -> bool:
        """Create a new state machine, clearing the current one.

        Returns:
            bool: True if a new state machine was created, False if cancelled.
        """
        reply = QMessageBox.question(
            self,
            "New State Machine",
            "Are you sure you want to create a new state machine? All unsaved changes will be lost.",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.canvas.scene.clear()
            self.state_nodes.clear()
            self.final_outcomes.clear()
            self.connections.clear()
            self.root_sm_name = ""
            self.start_state = None
            self.root_sm_name_edit.clear()
            self.root_sm_description = ""
            self.root_sm_description_edit.clear()
            self._blackboard_keys = []
            self._blackboard_key_metadata = {}
            self.current_container = None
            self.current_read_only = False
            self.preview_root_container = None
            self.preview_items = []
            self.navigation_path = [("root", None, False)]
            self.refresh_blackboard_keys_list()
            self.update_scope_header()
            self.update_start_state_combo()
            self.statusBar().showMessage("New state machine created", 2000)
            return True

        return False

    def open_state_machine(self) -> None:
        """Open a state machine from an XML file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open State Machine", "", "XML Files (*.xml)"
        )

        if file_path:
            try:
                if not self.new_state_machine():
                    return

                self.xml_manager.load_from_xml(file_path)
                self.current_container = None
                self.current_read_only = False
                self.navigation_path = [("root", None, False)]
                self.update_navigation_ui()
                self.update_scope_header()
                self.update_scope_visibility()
                self.statusBar().showMessage(f"Opened: {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file: {str(e)}")

    def save_state_machine(self) -> None:
        # Validation checks
        errors = []

        if not self.final_outcomes:
            errors.append("- No final outcomes defined")

        if not self.root_sm_name or not self.root_sm_name.strip():
            errors.append("- Root state machine name is empty")

        if not self.state_nodes:
            errors.append("- No states defined")

        if not self.start_state:
            errors.append("- Initial state is not set")
        elif self.start_state not in self.state_nodes:
            errors.append(f"- Initial state '{self.start_state}' does not exist")

        for name in self.state_nodes.keys():
            if not name or not name.strip():
                errors.append("- Found state with empty name")
                break

        if errors:
            error_msg = (
                "Cannot save state machine. Please fix the following issues:\n\n"
                + "\n".join(errors)
            )
            reply = QMessageBox.critical(
                self,
                "Validation Errors",
                error_msg + "\n\nDo you want to save anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save State Machine", "", "XML Files (*.xml)"
        )

        if file_path:
            if not file_path.lower().endswith(".xml"):
                file_path += ".xml"

            try:
                self.xml_manager.save_to_xml(file_path)
                self.statusBar().showMessage(f"Saved: {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")
