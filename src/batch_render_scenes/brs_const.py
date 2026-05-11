import bpy

PACKAGE = __package__


def prefs():
    return bpy.context.preferences.addons[PACKAGE].preferences
