import bpy
from bpy.types import PropertyGroup, UIList
from bpy.props import BoolProperty, StringProperty, IntProperty, CollectionProperty, PointerProperty


# ============================================================
# Data Model
# ============================================================


class BRS_SceneRender(PropertyGroup):
    name: StringProperty()
    frame_start: IntProperty()
    frame_end: IntProperty()


class BRS_FileItem(PropertyGroup):
    selected: BoolProperty(default=True)
    filepath: StringProperty()
    relpath: StringProperty()
    scene_count: IntProperty(default=-1)
    scene_render: CollectionProperty(type=BRS_SceneRender)


class BRS_Settings(PropertyGroup):
    files: CollectionProperty(type=BRS_FileItem)
    index: IntProperty()
    root_folder: StringProperty(name="Root Folder", default="", subtype="DIR_PATH")
    max_depth: IntProperty(name="Max Depth", default=0, min=0)
    is_scanning: BoolProperty(default=False)
    scan_status: StringProperty(default="")
    filter_name: StringProperty(name="Name Filter")


# ============================================================
# UI List
# ============================================================


class BRS_UL_files(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        settings = context.window_manager.brs_settings
        split = layout.split(factor=0.8)
        row = split.row(align=True)
        row.prop(item, "selected", text="")
        row.label(text=item.relpath)
        if item.scene_count >= 0:
            row.label(text=f"{item.scene_count} scenes")
        else:
            row.label(text="")

        row = split.row(align=True)

        if settings.is_scanning:
            name = "Scanning ..."
            row.enabled = False
        else:
            name = "Scan Scenes"

        update = row.operator("render.batch_scan", text=name, icon="FILE_REFRESH")
        update.mode = "SCENES"
        update.target = "ITEM"
        update.index = index

        # row.label(text=item.scene_render.name)


# ============================================================
# Menu
# ============================================================


def render_menu(self, context):
    self.layout.separator()
    self.layout.operator("render.batch_render_scenes", icon="RENDER_ANIMATION")


# ============================================================
# Register
# ============================================================


classes = (BRS_SceneRender, BRS_FileItem, BRS_Settings, BRS_UL_files)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.types.Scene.render_scene = BoolProperty(name="Render Scene", default=False)
    bpy.types.WindowManager.brs_settings = PointerProperty(type=BRS_Settings)
    bpy.types.TOPBAR_MT_render.append(render_menu)


def unregister():

    bpy.types.TOPBAR_MT_render.remove(render_menu)
    del bpy.types.WindowManager.brs_settings
    del bpy.types.Scene.render_scene

    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)
