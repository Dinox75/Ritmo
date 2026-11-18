import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from native_dialogs import prompt_field


class Node:
    def __init__(self,texts=(),edits=(),parent=None):
        self.texts=texts;self.edits=edits;self.up=parent
    def parent(self):return self.up
    def descendants(self,control_type):
        return [SimpleNamespace(element_info=SimpleNamespace(name=s)) for s in self.texts] if control_type=='Text' else list(self.edits)


class NativeDialogTests(unittest.TestCase):
    def test_confirmation_does_not_select_a_background_settings_input(self):
        background=object();root=Node(['Apagar permanentemente?'],[background])
        self.assertIsNone(prompt_field(Node(parent=root)))
    def test_prompt_selects_its_own_unique_field_before_background_ancestor(self):
        field=SimpleNamespace(element_info=SimpleNamespace(name='Digite APAGAR para solicitar a confirmação'));background=object()
        root=Node(['Digite APAGAR para solicitar a confirmação'],[background,field])
        dialog=Node(['Digite APAGAR para solicitar a confirmação'],[field],root)
        self.assertIs(prompt_field(Node(parent=dialog)),field)
    def test_ambiguous_fields_are_not_selected(self):
        fields=[SimpleNamespace(element_info=SimpleNamespace(name='Digite APAGAR')) for _ in range(2)]
        root=Node(['Digite APAGAR'],fields)
        self.assertIsNone(prompt_field(Node(parent=root)))
    def test_other_process_ancestors_are_not_inspected(self):
        root=Node(['Digite APAGAR'],[object()]);root.element_info=SimpleNamespace(process_id=99)
        self.assertIsNone(prompt_field(Node(parent=root),{10,11}))
