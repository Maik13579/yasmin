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
import importlib
from typing import List, Optional, Dict
from lxml import etree as ET
from yasmin_pybind_bridge import CppStateFactory
from ament_index_python import get_package_share_path


class PluginInfo:

    def __init__(
        self,
        plugin_type: str,
        class_name: Optional[str] = None,
        module: Optional[str] = None,
        file_name: Optional[str] = None,
        package_name: Optional[str] = None,
    ) -> None:
        self._cpp_factory: CppStateFactory = CppStateFactory()

        self.plugin_type: str = plugin_type
        self.class_name: Optional[str] = class_name
        self.module: Optional[str] = module
        self.file_name: Optional[str] = file_name
        self.package_name: Optional[str] = package_name
        self.outcomes: List[str] = []
        self.description: str = ""
        self.outcome_descriptions: Dict[str, str] = {}
        self.input_keys: List[dict] = []
        self.output_keys: List[dict] = []

        if self.plugin_type == "python":
            loaded_module = importlib.import_module(self.module)
            state_class = getattr(loaded_module, self.class_name)
            instance = state_class()
            self.outcomes = list(instance.get_outcomes())
            try:
                self.description = instance.get_description()
                self.outcome_descriptions = instance.get_outcome_descriptions()
                self.input_keys = list(instance.get_input_keys())
                self.output_keys = list(instance.get_output_keys())
            except Exception:
                pass
        elif self.plugin_type == "cpp":
            instance = self._cpp_factory.create(self.class_name)
            self.outcomes = list(instance.get_outcomes())
            try:
                self.description = instance.get_description()
                self.outcome_descriptions = instance.get_outcome_descriptions()
                self.input_keys = list(instance.get_input_keys())
                self.output_keys = list(instance.get_output_keys())
            except Exception:
                pass
        elif self.plugin_type == "xml":
            package_path = get_package_share_path(self.package_name)
            file_path = ""
            for root, dirs, files in os.walk(package_path):
                if self.file_name in files:
                    file_path = os.path.join(root, self.file_name)
                    break
            if not file_path:
                raise ValueError(
                    f"Could not find XML file {self.file_name} in package {self.package_name}"
                )
            tree = ET.parse(file_path)
            root = tree.getroot()
            outcomes_str: str = root.attrib.get("outcomes", "")
            self.outcomes = outcomes_str.split() if outcomes_str else []
            self.description = root.attrib.get("description", "")
            self.outcome_descriptions = {}

            for outcome_elem in root.findall("FinalOutcome"):
                outcome_name = outcome_elem.attrib.get("name", "")
                outcome_description = outcome_elem.attrib.get("description", "")
                if outcome_name and outcome_description:
                    self.outcome_descriptions[outcome_name] = outcome_description

            for key_elem in root.findall("Key"):
                key_name = key_elem.attrib.get("name", "")
                if not key_name:
                    continue

                key_data = {
                    "name": key_name,
                    "description": key_elem.attrib.get("description", ""),
                    "default_value_type": key_elem.attrib.get("default_type", "str"),
                    "default_value": key_elem.attrib.get("default_value", ""),
                    "has_default": "default_value" in key_elem.attrib,
                }

                key_type = key_elem.attrib.get("type", "IN")
                if key_type in ("IN", "IN/OUT"):
                    self.input_keys.append(dict(key_data))
                if key_type in ("OUT", "IN/OUT"):
                    self.output_keys.append(dict(key_data))

            if not self.input_keys and not self.output_keys:
                for default_elem in root.findall("Default"):
                    key_name = default_elem.attrib.get("key", "")
                    if not key_name:
                        continue
                    self.input_keys.append(
                        {
                            "name": key_name,
                            "description": default_elem.attrib.get("description", ""),
                            "default_value_type": default_elem.attrib.get("type", "str"),
                            "default_value": default_elem.attrib.get("value", ""),
                            "has_default": True,
                        }
                    )
