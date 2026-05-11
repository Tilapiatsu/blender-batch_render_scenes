# Blender 2.93+ / 3.x / 4.x
#
# Install:
# Edit > Preferences > Add-ons > Install...
#
# Adds:
# - Scene checkbox: "Render Scene"
# - Render menu > Batch Render Scene
# - Recursive scan of .blend files with depth
# - Selectable batch list
# - Name filter tools
# - Sequential rendering in dedicated terminal
#
# ------------------------------------------------------------

bl_info = {
    "name": "Batch Render Scenes",
    "author": "Tilapiatsu",
    "version": (1, 0, 0),
    "blender": (2, 93, 0),
    "location": "Render Menu / Scene Properties",
    "description": "Batch render marked scenes across many blend files",
    "category": "Render",
}

import bpy
import os
import json
import tempfile
import subprocess
from pathlib import Path

from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator, Panel, PropertyGroup, AddonPreferences, UIList

from bpy.props import (
    BoolProperty,
    StringProperty,
    IntProperty,
    CollectionProperty,
    PointerProperty,
)


# ============================================================
# Addon Preferences
# ============================================================


class BRS_Preferences(AddonPreferences):
    bl_idname = __name__

    terminal_path: StringProperty(name="Terminal Executable", subtype="FILE_PATH", default="/usr/bin/xterm")

    terminal_args: StringProperty(name="Terminal Arguments", default="-hold -e")

    blender_path: StringProperty(name="Blender Executable", subtype="FILE_PATH", default="blender")

    def draw(self, context):
        layout = self.layout
        layout.label(text="Terminal Settings")
        layout.prop(self, "terminal_path")
        layout.prop(self, "terminal_args")
        layout.separator()
        layout.label(text="Blender")
        layout.prop(self, "blender_path")


# ============================================================
# Scene Checkbox
# ============================================================


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
# Data Model
# ============================================================


class BRS_FileItem(PropertyGroup):
    selected: BoolProperty(default=True)
    filepath: StringProperty()
    relpath: StringProperty()
    scene_count: IntProperty(default=0)
    scene_names: StringProperty()


# ============================================================
# UI List
# ============================================================


class BRS_UL_files(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "selected", text="")
        row.label(text=item.relpath)
        row.label(text=f"{item.scene_count} scenes")
        row.label(text=item.scene_names)


# ============================================================
# Helper
# ============================================================


def prefs():
    return bpy.context.preferences.addons[__name__].preferences


def find_blend_files(root_dir, max_depth):
    root = Path(root_dir).resolve()

    for file in root.rglob("*.blend"):
        rel = file.relative_to(root)
        depth = len(rel.parts) - 1

        if max_depth >= 0 and depth > max_depth:
            continue

        yield file


def query_render_scenes(filepath):
    """
    Launch background Blender and ask scenes marked render_scene
    """

    script = r"""
import bpy, json
result=[]
for s in bpy.data.scenes:
    if getattr(s,"render_scene",False):
        result.append(s.name)
print("BATCH_RENDER_SCENES="+json.dumps(result))
"""

    cmd = [prefs().blender_path, "-b", filepath, "--python-expr", script]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)

        for line in proc.stdout.splitlines():
            if line.startswith("BATCH_RENDER_SCENES="):
                return json.loads(line[len("BATCH_RENDER_SCENES=") :])

    except Exception as e:
        print(e)

    return []


# ============================================================
# Main Operator
# ============================================================


class BRS_OT_batch_popup(Operator):
    bl_idname = "render.batch_render_scenes"
    bl_label = "Batch Render Scenes"
    bl_options = {"REGISTER"}

    root_folder: StringProperty(name="Root Folder")

    max_depth: IntProperty(name="Depth", default=2, min=0)

    filter_name: StringProperty(name="Name Filter")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=900)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        wm = context.window_manager

        layout.prop(wm, "brs_root_folder")
        layout.prop(wm, "brs_max_depth")

        row = layout.row()
        row.operator("render.batch_scan", text="Scan")

        layout.template_list("BRS_UL_files", "", scene, "brs_files", scene, "brs_index", rows=14)

        layout.separator()
        layout.prop(self, "filter_name")

        row = layout.row(align=True)
        row.operator("render.brs_select_filter", text="Select Match").mode = "SELECT"
        row.operator("render.brs_select_filter", text="Unselect Match").mode = "UNSELECT"

    def execute(self, context):
        bpy.ops.render.brs_launch_terminal()
        return {"FINISHED"}


# ============================================================
# Scan
# ============================================================


class BRS_OT_scan(Operator):
    bl_idname = "render.batch_scan"
    bl_label = "Scan"

    def execute(self, context):

        scene = context.scene
        wm = context.window_manager

        scene.brs_files.clear()

        root = wm.brs_root_folder
        depth = wm.brs_max_depth

        if not root:
            self.report({"WARNING"}, "Choose root folder")
            return {"CANCELLED"}

        for f in find_blend_files(root, depth):
            scenes = query_render_scenes(str(f))

            item = scene.brs_files.add()
            item.filepath = str(f)
            item.relpath = os.path.relpath(str(f), root)
            item.scene_count = len(scenes)
            item.scene_names = ", ".join(scenes)

        self.report({"INFO"}, f"Found {len(scene.brs_files)} files")
        return {"FINISHED"}


# ============================================================
# Select Filter
# ============================================================


class BRS_OT_select_filter(Operator):
    bl_idname = "render.brs_select_filter"
    bl_label = "Select Filter"

    mode: StringProperty()

    def execute(self, context):

        scene = context.scene
        op = context.window_manager.operators[-1]
        text = op.filter_name.lower()

        for item in scene.brs_files:
            if text in item.relpath.lower():
                item.selected = self.mode == "SELECT"

        return {"FINISHED"}


# ============================================================
# Launch Terminal
# ============================================================


class BRS_OT_launch_terminal(Operator):
    bl_idname = "render.brs_launch_terminal"
    bl_label = "Launch Batch Render"

    def execute(self, context):

        scene = context.scene
        p = prefs()

        lines = []

        for item in scene.brs_files:
            if not item.selected:
                continue

            if not item.scene_names:
                continue

            scenes = [x.strip() for x in item.scene_names.split(",") if x.strip()]

            for sc in scenes:
                cmd = f'"{p.blender_path}" -b "{item.filepath}" -S "{sc}" -f 1'
                lines.append(cmd)

        if not lines:
            self.report({"WARNING"}, "Nothing selected")
            return {"CANCELLED"}

        fd, path = tempfile.mkstemp(suffix=".sh")

        with os.fdopen(fd, "w") as f:
            f.write("#!/bin/bash\n")
            for line in lines:
                f.write(line + "\n")
            f.write('echo "Done."\n')
            f.write("read -n1 -r -p 'Press any key...'")

        os.chmod(path, 0o755)

        args = p.terminal_args.split()

        cmd = [p.terminal_path] + args + [path]

        subprocess.Popen(cmd)

        self.report({"INFO"}, "Batch render launched")
        return {"FINISHED"}


# ============================================================
# Menu
# ============================================================


def render_menu(self, context):
    self.layout.separator()
    self.layout.operator("render.batch_render_scenes", icon="RENDER_ANIMATION")


# ============================================================
# Register
# ============================================================

classes = (
    BRS_Preferences,
    BRS_PT_scene_panel,
    BRS_FileItem,
    BRS_UL_files,
    BRS_OT_batch_popup,
    BRS_OT_scan,
    BRS_OT_select_filter,
    BRS_OT_launch_terminal,
)


def register():

    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.render_scene = BoolProperty(name="Render Scene", default=False)

    bpy.types.Scene.brs_files = CollectionProperty(type=BRS_FileItem)
    bpy.types.Scene.brs_index = IntProperty()
    bpy.types.WindowManager.brs_root_folder = StringProperty(name="Root Folder", default="", subtype="DIR_PATH")
    bpy.types.WindowManager.brs_max_depth = IntProperty(name="Max Depth", default=2, min=0)

    bpy.types.TOPBAR_MT_render.append(render_menu)


def unregister():

    bpy.types.TOPBAR_MT_render.remove(render_menu)

    del bpy.types.Scene.render_scene
    del bpy.types.Scene.brs_files
    del bpy.types.Scene.brs_index

    for c in reversed(classes):
        bpy.utils.unregister_class(c)
