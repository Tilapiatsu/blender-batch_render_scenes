from . import properties
from . import preferences

modules = (
    properties,
    preferences,
)


def register():
    for m in modules:
        m.register()


def unregister():
    for m in reversed(modules):
        m.unregister()
