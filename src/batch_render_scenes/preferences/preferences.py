import bpy
from bpy.types import AddonPreferences, Panel
from bpy.props import StringProperty, BoolProperty

from ..brs_const import PACKAGE


class BRS_Preferences(AddonPreferences):
    bl_idname = PACKAGE

    terminal_path: StringProperty(name="Terminal Executable", subtype="FILE_PATH", default="/usr/bin/kitty")
    terminal_args: StringProperty(name="Terminal Arguments", default="")
    blender_path: StringProperty(name="Blender Executable", subtype="FILE_PATH", default="blender")

    def draw(self, context):
        layout = self.layout
        layout.label(text="Terminal Settings")
        layout.prop(self, "terminal_path")
        layout.prop(self, "terminal_args")
        layout.separator()
        layout.label(text="Blender")
        layout.prop(self, "blender_path")


class BRS_PT_scene_panel(Panel):
    bl_label = "Batch Render Scenes"
    bl_idname = "BRS_PT_scene_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "output"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(context.scene, "render_scene")


# ============================================================
# Register
# ============================================================


classes = (BRS_Preferences, BRS_PT_scene_panel)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.types.Scene.render_scene = BoolProperty(name="Render Scene", default=False)


def unregister():

    del bpy.types.Scene.render_scene

    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)
