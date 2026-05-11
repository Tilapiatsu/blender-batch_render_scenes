import bpy
import os
import json
import tempfile
import subprocess
from pathlib import Path

from bpy.types import Operator

from bpy.props import (
    BoolProperty,
    StringProperty,
)

from ..brs_const import prefs

# ============================================================
# Main Operator
# ============================================================


class BRS_OT_batch_popup(Operator):
    bl_idname = "render.batch_render_scenes"
    bl_label = "Batch Render Scenes"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        wm = context.window_manager
        settings = wm.brs_settings
        settings.is_scanning = False
        return wm.invoke_props_dialog(self, width=900)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = context.window_manager.brs_settings

        row = layout.row(align=True)
        split = row.split(factor=0.8)
        split.prop(settings, "root_folder")
        split.prop(settings, "max_depth", icon="SORTSIZE")

        row = layout.row()

        if settings.is_scanning:
            row.enabled = False
            row.operator("render.batch_scan", text="Scanning...", icon="FILE_REFRESH")
        else:
            row.operator("render.batch_scan", text="Scan", icon="FILE_REFRESH")

        if settings.scan_status:
            layout.label(text=settings.scan_status, icon="INFO")

        row = layout.row(align=True)
        row.operator("render.brs_select_all", text="Select All", icon="CHECKBOX_HLT").state = True
        row.operator("render.brs_select_all", text="Unselect All", icon="CHECKBOX_DEHLT").state = False
        row.operator("render.brs_invert_selection", text="Invert")

        layout.template_list("BRS_UL_files", "", settings, "files", settings, "index", rows=14)

        layout.separator()
        layout.prop(settings, "filter_name", icon="OUTLINER_DATA_FONT")

        row = layout.row(align=True)
        row.operator("render.brs_select_filter", text="Select Match", icon="CHECKBOX_HLT").mode = "SELECT"
        row.operator("render.brs_select_filter", text="Unselect Match", icon="CHECKBOX_DEHLT").mode = "UNSELECT"

    def execute(self, context):
        bpy.ops.render.brs_launch_terminal()
        return {"FINISHED"}


# ============================================================
# Scan
# ============================================================


class BRS_OT_scan(Operator):
    bl_idname = "render.batch_scan"
    bl_label = "Scan"

    _timer = None
    _files = []
    _index = 0
    _root = ""
    _depth = 0

    def execute(self, context):

        scene = context.scene
        settings = context.window_manager.brs_settings

        if settings.is_scanning:
            return {"CANCELLED"}

        self._root = settings.root_folder
        self._depth = settings.max_depth

        if not self._root:
            self.report({"WARNING"}, "Choose root folder")
            return {"CANCELLED"}

        settings.files.clear()
        settings.is_scanning = True
        settings.scan_status = "Preparing scan..."

        self._files = list(self.find_blend_files(self._root, self._depth))
        self._index = 0

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)

        self.report({"INFO"}, f"Scanning {len(self._files)} blend files...")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        wm = context.window_manager
        scene = context.scene
        settings = wm.brs_settings

        # ----------------------------------------------------
        # FINISHED
        # ----------------------------------------------------
        if self._index >= len(self._files):
            wm.event_timer_remove(self._timer)

            settings.is_scanning = False
            settings.scan_status = f"Scan complete: {len(settings.files)} files found"

            for area in context.screen.areas:
                area.tag_redraw()

            self.report({"INFO"}, f"Batch scan complete ({len(settings.files)} files)")

            return {"FINISHED"}

        # ----------------------------------------------------
        # PROCESS ONE FILE
        # ----------------------------------------------------
        f = self._files[self._index]
        self._index += 1

        settings.scan_status = f"Scanning {self._index}/{len(self._files)} : {os.path.basename(str(f))}"

        scenes = self.query_render_scenes(str(f))

        item = settings.files.add()
        item.filepath = str(f)
        item.relpath = os.path.relpath(str(f), self._root)
        item.scene_count = len(scenes)
        if not item.scene_count:
            item.selected = False
        for s in scenes:
            scene_item = item.scene_render.add()
            scene_item.name = s["name"]
            scene_item.frame_start = int(s["frame_start"])
            scene_item.frame_end = int(s["frame_end"])

        for area in context.screen.areas:
            area.tag_redraw()

        return {"RUNNING_MODAL"}

    def query_render_scenes(self, filepath):
        """
        Launch background Blender and ask scenes marked render_scene
        """

        script = r"""
import bpy, json
result=[]
for s in bpy.data.scenes:
    if getattr(s,"render_scene",False):
        result.append({'name':s.name, 'frame_start':s.frame_start, 'frame_end':s.frame_end})
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

    def find_blend_files(self, root_dir, max_depth):
        root = Path(root_dir).resolve()

        for file in root.rglob("*.blend"):
            rel = file.relative_to(root)
            depth = len(rel.parts) - 1

            if max_depth >= 0 and depth > max_depth:
                continue

            yield file


# ============================================================
# Select Filter
# ============================================================


class BRS_OT_select_filter(Operator):
    bl_idname = "render.brs_select_filter"
    bl_label = "Select Filter"

    mode: StringProperty()

    def execute(self, context):

        settings = context.window_manager.brs_settings

        text = settings.filter_name.lower()

        for item in settings.files:
            if text in item.relpath.lower():
                item.selected = self.mode == "SELECT"

        return {"FINISHED"}


class BRS_OT_select_all(Operator):
    bl_idname = "render.brs_select_all"
    bl_label = "Select All"

    state: BoolProperty(default=True)

    def execute(self, context):
        for item in context.window_manager.brs_settings.files:
            item.selected = self.state
        return {"FINISHED"}


class BRS_OT_invert_selection(Operator):
    bl_idname = "render.brs_invert_selection"
    bl_label = "Invert Selection"

    def execute(self, context):
        for item in context.window_manager.brs_settings.files:
            item.selected = not item.selected
        return {"FINISHED"}


# ============================================================
# Launch Terminal
# ============================================================


class BRS_OT_launch_terminal(Operator):
    bl_idname = "render.brs_launch_terminal"
    bl_label = "Launch Batch Render"

    def execute(self, context):

        scene = context.scene
        settings = context.window_manager.brs_settings
        p = prefs()

        lines = []

        for item in settings.files:
            if not item.selected:
                continue

            for sc in item.scene_render:
                cmd = (
                    f'"{p.blender_path}" -b "{item.filepath}" -S "{sc.name}" -a  -s {sc.frame_start} -e {sc.frame_end}'
                )
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
        print(cmd)
        subprocess.Popen(cmd)

        self.report({"INFO"}, "Batch render launched")
        return {"FINISHED"}


# ============================================================
# Register
# ============================================================

classes = (
    BRS_OT_batch_popup,
    BRS_OT_scan,
    BRS_OT_select_filter,
    BRS_OT_select_all,
    BRS_OT_invert_selection,
    BRS_OT_launch_terminal,
)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)


def unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)
