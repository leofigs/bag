#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals  # unicode by default
from __future__ import absolute_import
import os
import stat
from pyramid.config import Configurator
from .plugins_manager import PluginsManager, BasePlugin


def isdir(s):
    """Return true if the pathname refers to an existing directory."""
    try:
        st = os.stat(s)
    except os.error:
        return False
    return stat.S_ISDIR(st.st_mode)


def makedirs(s):
    '''Make directories (if they don't exist already).'''
    if not isdir(s):
        os.makedirs(s)


view_classes = []
def register_view_class(cls):
    '''Class decorator that adds the class to a list.'''
    view_classes.append(cls)
    return cls


class LocaleList(list):
    def add(self, id, name, title):
        self.append(dict(name=id, descr=name, title=title))


class PyramidStarter(object):
    '''Reusable configurator for nice Pyramid applications.'''

    def __init__ (self, config, packages=[]):
        '''Arguments:
        `config` is the Pyramid configurator instance, or a dictionary that
        can be used to create such an instance.
        `packages` is a sequence of additional packages that should be
        scanned/enabled.
        '''
        self.require_python27()
        self.config = config
        if not self.settings.has_key('app.name'):
            raise KeyError \
                ('Your configuration files are missing an "app.name" setting.')
        # Add self to config so other applications can find it
        config.bag = self
        self.packages = packages
        self.package_name = config.package.__name__
        self.directory = os.path.abspath(os.path.dirname(config.package.__file__))
        self.parent_directory = os.path.dirname(self.directory)
        # Create the _() function for internationalization
        from pyramid.i18n import TranslationStringFactory
        self._ = TranslationStringFactory(self.package_name)
        self._enable_locales()

    def _enable_locales(self):
        '''Gets a list of enabled locale names from settings, checks it
        against our known locales and stores in settings a list containing
        not only the locale names but also texts for links for changing the
        locale.
        '''
        # Get a list of enabled locale names from settings
        settings = self.settings
        locales_filter = settings.get('enabled_locales', 'en').split(' ')
        _ = self._
        # Check the settings against a list of supported locales
        locales = LocaleList()
        locales.add('en', _('English'), 'Change to English')
        locales.add('en_DEV', _('English-DEV'), 'Change to dev slang')
        locales.add('pt_BR', _('Brazilian Portuguese'), 'Mudar para português')
        locales.add('es', _('Spanish'), 'Cambiar a español')
        locales.add('de', _('German'), 'Auf Deutsch benutzen')
        # The above list must be updated when new languages are added
        enabled_locales = []
        for locale in locales_filter:
            for adict in locales:
                if locale == adict['name']:
                    enabled_locales.append(adict)
        # Replace the setting
        settings['enabled_locales'] = enabled_locales

    @property
    def settings(self):
        return self.config.get_settings()

    def makedirs(self, key):
        '''Creates a directory if it does not yet exist.
        The argument is a string that may contain one of these placeholders:
        {here} or {up}.
        '''
        makedirs(key.format(here=self.directory, up=self.parent_directory))

    def log(self, text):
        '''TODO: Implement logging setup'''
        print(text)

    def enable_handlers(self):
        '''Pyramid "handlers" emulate Pylons 1 "controllers".
        https://github.com/Pylons/pyramid_handlers
        '''
        from pyramid_handlers import includeme
        self.config.include(includeme)
        self.scan()

    def enable_sqlalchemy(self, initialize_sql=None):
        from sqlalchemy import engine_from_config
        settings = self.settings
        self.engine = engine = engine_from_config(settings, 'sqlalchemy.')
        if initialize_sql is None:
            from importlib import import_module
            try:
                module = import_module(self.package_name + '.models')
            except ImportError as e:
                self.log('Could not find the models module.')
            else:
                try:
                    initialize_sql = module.initialize_sql
                except AttributeError as e:
                    self.log('initialize_sql() does not exist.')
        if initialize_sql:
            self.log('initialize_sql()')
            initialize_sql(engine, settings=settings)
        registry = self.config.registry
        if hasattr(registry, 'plugins'):
            registry.plugins.call('initialize_sql', dict(
                engine=engine, settings=settings))

    @classmethod
    def init_basic_sqlalchemy(cls):
        '''Returns a declarative base class and a SQLAlchemy scoped session
        that uses the ZopeTransactionExtension.
        '''
        from sqlalchemy.orm import scoped_session, sessionmaker
        from zope.sqlalchemy import ZopeTransactionExtension
        sas = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
        from sqlalchemy.ext.declarative import declarative_base
        Base = declarative_base()
        return Base, sas

    def enable_turbomail(self):
        from warnings import warn
        warn('enable_turbomail() is deprecated. Prefer enable_marrow_mailer()')
        from turbomail.control import interface
        import atexit
        options = {key: self.settings[key] for key in self.settings \
            if key.startswith('mail.')}
        interface.start(options)
        atexit.register(interface.stop, options)

    def enable_marrow_mailer(self):
        '''This method enables https://github.com/marrow/marrow.mailer
        which is the new TurboMail.

        After this you can access registry.mailer to send messages.
        '''
        from marrow.mailer import Mailer
        import atexit
        options = {key[5:]: self.settings[key] for key in self.settings \
            if key.startswith('mail.')}
        mailer = self.config.registry.mailer = Mailer(options)
        mailer.start()
        atexit.register(mailer.stop)

    def enable_kajiki(self):
        '''Allows you to use the Kajiki templating language.'''
        from .kajiki import renderer_factory
        for extension in ('.txt', '.xml', '.html', '.html5'):
            self.config.add_renderer(extension, renderer_factory)

    def enable_genshi(self):
        '''Allows us to use the Genshi templating language.
        We intend to switch to Kajiki down the road, therefore it would be
        best to avoid py:match.
        '''
        sd = self.settings.setdefault
        sd('genshi.translation_domain', self.package_name)
        sd('genshi.encoding', 'utf-8')
        sd('genshi.doctype', 'html5')
        sd('genshi.method', 'xhtml')
        from .genshi import enable_genshi
        enable_genshi(self.config)

    def enable_deform(self, template_dirs):
        from .deform import setup
        setup(template_dirs)
        self.config.add_static_view('deform', 'deform:static')

    def configure_favicon(self, path='static/icon/32.png'):
        from mimetypes import guess_type
        from pyramid.resource import abspath_from_resource_spec
        self.settings['favicon'] = path = abspath_from_resource_spec(
            self.settings.get('favicon', '{}:{}'.format(self.package_name, path)))
        self.settings['favicon_content_type'] = guess_type(path)[0]

    def enable_robots(self, path='static/robots.txt'):
        from mimetypes import guess_type
        from pyramid.resource import abspath_from_resource_spec
        path = abspath_from_resource_spec(
            self.settings.get('robots', '{}:{}'.format(self.package_name, path)))
        content_type = guess_type(path)[0]
        import codecs
        with codecs.open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        from pyramid.response import Response
        def robots_view(request):
            return Response(content_type=content_type, app_iter=content)
        self.config.add_route('robots', '/robots.txt')
        self.config.add_view(robots_view, route_name='robots')

    def enable_internationalization(self, extra_translation_dirs):
        self.makedirs(self.settings.get('dir_locale', '{here}/locale'))
        self.config.add_translation_dirs(self.package_name + ':locale',
            *extra_translation_dirs)
        # from pyramid.i18n import default_locale_negotiator
        # self.config.set_locale_negotiator(default_locale_negotiator)

    def set_template_globals(self, fn=None):
        '''Intended to be overridden in subclasses.'''
        from pyramid import interfaces
        from pyramid.events import subscriber
        from pyramid.i18n import get_localizer, get_locale_name
        from pyramid.url import route_url, static_url
        package_name = self.package_name

        def template_globals(event):
            '''Adds stuff we use all the time to template context.
            There is no need to add *request* since it is already there.
            '''
            request = event['request']
            settings = request.registry.settings
            # A nicer "route_url": no need to pass it the request object.
            event['url'] = lambda name, *a, **kw: \
                                  route_url(name, request, *a, **kw)
            event['base_path'] = settings.get('base_path', '/')
            event['static_url'] = lambda s: static_url(s, request)
            event['locale_name'] = get_locale_name(request)  # to set xml:lang
            event['enabled_locales'] = settings['enabled_locales']
            event['appname'] = settings.get('app.name', 'Application')
            # http://docs.pylonsproject.org/projects/pyramid_cookbook/dev/i18n.html
            localizer = get_localizer(request)
            translate = localizer.translate
            pluralize = localizer.pluralize
            event['_'] = lambda text, mapping=None: \
                         translate(text, domain=package_name, mapping=mapping)
            event['plur'] = lambda singular, plural, n, mapping=None: \
                            pluralize(singular, plural, n,
                                      domain=package_name, mapping=mapping)

        self.config.add_subscriber(fn or template_globals,
                                   interfaces.IBeforeRender,
        )

    def declare_routes_from_views(self):
        self.scan()  # in order to find all the decorated view classes
        for k in view_classes:
            if hasattr(k, 'declare_routes'):
                k.declare_routes(self.config)

    def declare_deps_from_views(self, deps, rooted):
        self.scan()  # in order to find all the decorated view classes
        settings = self.settings
        for k in view_classes:
            if hasattr(k, 'declare_deps'):
                k.declare_deps(deps, rooted, settings)

    def scan(self):
        self.config.scan(self.package_name)
        for p in self.packages:
            self.config.scan(p)
        # Make this method a noop for the future (scan only once)
        self.scan = lambda: None

    def result(self):
        '''Commits the configuration (this causes some tests) and returns the
        WSGI application.
        '''
        return self.config.make_wsgi_app()

    @property
    def all_routes(self):
        '''Returns a list of the routes configured in this application.'''
        return all_routes(self.config)

    def require_python27(self):
        '''Demand Python 2.7 (ensure not trying to run it on 2.6.).'''
        from sys import version_info, exit
        version_info = version_info[:2]
        if version_info < (2, 7) or version_info >= (3, 0):
            exit('\n' + self.package_name + ' requires Python 2.7.x.')

    def load_plugins(self, entry_point_groups=None, directory=None,
            base_class=BasePlugin):
        self.config.registry.plugins = self.plugins = \
            PluginsManager(self.settings)
        if directory:
            self.plugins.find_directory_plugins(directory,
                                                plugin_class=base_class)
        if entry_point_groups:
            self.plugins.find_egg_plugins(entry_point_groups)


def all_routes(config):
    '''Returns a list of the routes configured in this application.'''
    return [(x.name, x.pattern) for x in \
            config.get_routes_mapper().get_routes()]


def all_views(registry):
    return set([o['introspectable']['callable'] \
        for o in registry.introspector.get_category('views')])


def all_view_classes(registry):
    # I have left this code here, but it is better to just use the
    # @register_view_class decorator and then look up the view_classes list.
    return [o for o in all_views(registry) if isinstance(o, type)]


def authentication_policy(settings, include_ip=True, timeout=60*60*32,
                    reissue_time=60, find_groups=lambda userid, request: []):
    '''Returns an authentication policy object for configuration.'''
    try:
        secret = settings['cookie_salt']
    except KeyError as e:
        raise KeyError('Your config file is missing a cookie_salt.')
    from pyramid.authentication import AuthTktAuthenticationPolicy
    return AuthTktAuthenticationPolicy(secret, callback=find_groups,
        include_ip=include_ip, timeout=timeout, reissue_time=reissue_time)
