import os
import pkg_resources
import re

from repoze.configuration.exceptions import ConfigurationConflict

_INTERP = re.compile(r"%\(([^)]*)\)s")

class Context(object):

    def __init__(self, registry, loader):
        self.registry = registry
        self.loader = loader
        self.actions = []
        self.stack = []
        self.discriminators = {}

    def interpolate(self, value):
        def _interpolation_replace(match):
            s = match.group(1)
            if not s in self.registry:
                raise KeyError(s)
            return self.registry[s]
        if '%(' in value:
            value = _INTERP.sub(_interpolation_replace, value)
        return value.encode('utf-8')

    def action(self, declaration, callback, discriminator=None, override=False):
        stack_override = self.stack and self.stack[-1]['override']
        effective_override = override or stack_override
        if not effective_override:
            if discriminator in self.discriminators:
                conflicting_action = self.discriminators[discriminator]
                raise ConfigurationConflict(declaration,
                                            conflicting_action.declaration)

        action = Action(discriminator, callback, declaration)
        self.actions.append(action)
        self.discriminators[discriminator] = action

    def resolve(self, dottedname):
        if dottedname.startswith('.') or dottedname.startswith(':'):
            package = self.current_package()
            if not package:
                raise ImportError('name "%s" is irresolveable (no package)' %
                    dottedname)
            if dottedname in ['.', ':']:
                dottedname = package.__name__
            else:
                dottedname = package.__name__ + dottedname
        return pkg_resources.EntryPoint.parse(
            'x=%s' % dottedname).load(False)

    def current_package(self):
        if not self.stack:
            return None
        return self.stack[-1]['package']

    def current_override(self):
        if not self.stack:
            return False
        return self.stack[-1]['override']

    def stream(self, filename, package=None):
        if os.path.isabs(filename):
            return open(filename)
        if package is None:
            package = self.current_package()
        if package is None:
            return open(filename)
        else:
            return pkg_resources.resource_stream(package.__name__, filename)
        
    def load(self, filename, package, override=False, loader=None):
        stream = self.stream(filename, package)
        self.stack.append({'filename':filename, 'package':package,
                           'override':override})
        if loader is None:
            loader = self.loader
        try:
            loader(self, stream)
        finally:
            self.stack.pop()

    def execute(self):
        for action in self.actions:
            action.execute()
        return self.registry

class Action(object):
    def __init__(self, discriminator, callback, declaration):
        self.discriminator = discriminator
        self.callback = callback
        self.declaration = declaration
        
    def execute(self):
        self.callback()

