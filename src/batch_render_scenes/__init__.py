bl_info = {
    "name": "Batch Render Scenes",
    "author": "Tilapiatsu",
    "version": (1, 0, 0),
    "blender": (2, 93, 0),
    "location": "Render Menu / Scene Properties",
    "description": "Batch render marked scenes across many blend files",
    "category": "Render",
}


from . import preferences
from . import operator


modules = (preferences, operator)


def register():
    for m in modules:
        m.register()


def unregister():
    for m in reversed(modules):
        m.unregister()
