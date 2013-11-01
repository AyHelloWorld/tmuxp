# -*- coding: utf8 - *-
"""Pythonization of the :ref:`tmux(1)` server.

tmuxp.server
~~~~~~~~~~~~

tmuxp helps you manage tmux workspaces.

:copyright: Copyright 2013 Tony Narlock.
:license: BSD, see LICENSE for details

"""
from __future__ import absolute_import, division, print_function, with_statement

import os
from .util import tmux, TmuxRelationalObject
from .session import Session
from . import formats
import logging

logger = logging.getLogger(__name__)


class Server(TmuxRelationalObject):

    '''
    The :term:`tmux(1)` server. Container for:

    - :attr:`Server._sessions` [:class:`Session`, ...]

      - :attr:`Session._windows` [:class:`Window`, ...]

        - :attr:`Window._panes` [:class:`Pane`, ...]

          - :class:`Pane`

    When instantiated, provides the ``t`` global. stores information on live,
    running tmux server.
    '''

    #: socket name
    socket_name = None
    socket_path = None
    config_file = None
    colors = None
    childIdAttribute = 'session_id'

    def __init__(
        self,
        socket_name=None,
        socket_path=None,
        config_file=None,
        colors=None,
        **kwargs
    ):
        self._windows = []
        self._panes = []

        if socket_name:
            self.socket_name = socket_name

        if socket_path:
            self.socket_path = socket_path

        if config_file:
            self.config_file = config_file

        if colors:
            self.colors = colors

    def tmux(self, *args, **kwargs):
        args = list(args)
        if self.socket_name:
            args.insert(0, '-L{}'.format(self.socket_name))
        if self.socket_path:
            args.insert(0, '-S{}'.format(self.socket_path))
        if self.config_file:
            args.insert(0, '-f{}'.format(self.config_file))
        if self.colors:
            if self.colors == 256:
                args.insert(0, '-2')
            elif self.colors == 88:
                args.insert(0, '-8')
            else:
                raise ValueError('Server.colors must equal 88 or 256')

        return tmux(*args, **kwargs)

    def __list_sessions(self):
        '''
        compatibility wrapping for ``$ tmux list-sessions``.

        :rtype: stdout or stderr of tmux proc
        '''
        sformats = formats.SESSION_FORMATS
        tmux_formats = ['#{%s}' % f for f in sformats]

        tmux_args = (
            '-F%s' % '\t'.join(tmux_formats),   # output
        )

        proc = self.tmux(
            'list-sessions',
            *tmux_args
        )

        if proc.stderr:
            raise Exception(proc.stderr)
        else:
            session_info = proc.stdout[0]

        if proc.stderr:
            raise Exception(sessions.stderr)

        return proc.stdout

    def _list_sessions(self):
        '''
        Return a list of session information ``tmux(1)`` for the sessions

        :rtype: :py:obj:`list` of :py:obj:`dict`
        '''

        sformats = formats.SESSION_FORMATS
        tmux_formats = ['#{%s}' % format for format in sformats]
        sessions = self.__list_sessions()

        # combine format keys with values returned from ``tmux list-windows``
        sessions = [dict(zip(
            sformats, session.split('\t'))) for session in sessions]

        # clear up empty dict
        sessions = [
            dict((k, v) for k, v in session.items() if v) for session in sessions
        ]

        return sessions

    @property
    def _sessions(self):
        """Return list of the server's sessions as :py:obj:`dict`.

        :rtype: list

        """

        return self._list_sessions()

    def list_sessions(self):
        """Return list of :class:`Session` from the ``tmux(1)`` session.

        :rtype: :py:obj:`list` of :class:`Session`

        """
        return [
            Session(server=self, **s) for s in self._sessions
        ]

    @property
    def sessions(self):
        """Return a :py:obj:`list` of the server's :class:`Session` objects."""
        return self.list_sessions()
    #: Alias of :attr:`sessions`.
    children = sessions

    def __list_windows(self):
        """Return list of ``$ tmux(1) list-windows`` stdout.

        The :py:obj:`list` is derived from :class:`util.tmux` which wraps
        :py:meth:`Subprocess.Popen`.

        :rtype: list

        """

        wformats = ['session_name', 'session_id'] + formats.WINDOW_FORMATS
        tmux_formats = ['#{%s}' % format for format in wformats]

        windows = self.tmux(
            'list-windows',                     # ``tmux list-windows``
            '-a',
            '-F%s' % '\t'.join(tmux_formats),   # output
        )

        if windows.stderr:
            raise Exception(windows.stderr)

        return windows.stdout

    def _list_windows(self):
        """Return list of dicts filtered from :meth:`__list_windows`."""

        wformats = ['session_name', 'session_id'] + formats.WINDOW_FORMATS

        windows = self.__list_windows()

        # combine format keys with values returned from ``tmux list-windows``
        windows = [dict(zip(
            wformats, window.split('\t'))) for window in windows]

        # clear up empty dict
        windows = [
            dict((k, v) for k, v in window.items() if v) for window in windows
        ]

        # tmux < 1.8 doesn't have window_id, use window_name
        for w in windows:
            if not 'window_id' in w:
                w['window_id'] = w['window_name']

        if self._windows:
            # http://stackoverflow.com/a/14465359
            self._windows[:] = []

        self._windows.extend(windows)

        return self._windows

    def _update_windows(self):
        """Update internal window data and return ``self`` for chainability."""
        self._list_windows()
        return self

    def __list_panes(self):
        """Return list of ``$ tmux(1) list-panes`` stdout.

        The :py:obj:`list` is derived from :class:`util.tmux` which wraps
        :py:meth:`Subprocess.Popen`.

        :rtype: list

        """
        pformats = ['session_name', 'session_id',
                    'window_index', 'window_id', 'window_name'] + formats.PANE_FORMATS
        tmux_formats = ['#{%s}\t' % f for f in pformats]

        panes = self.tmux(
            'list-panes',
            #'-t%s:%s' % (self.get('session_name'), self.get('window_id')),
            '-a',
            '-F%s' % ''.join(tmux_formats),     # output
        )

        if panes.stderr:
            raise Exception(panes.stderr)

        return panes.stdout

    def _list_panes(self):
        """Return list of dicts filtered from :meth:`__list_panes`."""

        pformats = ['session_name', 'session_id',
                    'window_index', 'window_id', 'window_name'] + formats.PANE_FORMATS

        panes = self.__list_panes()

        # combine format keys with values returned from ``tmux list-panes``
        panes = [dict(zip(
            pformats, window.split('\t'))) for window in panes]

        # clear up empty dict
        panes = [
            dict((k, v) for k, v in window.items() if v) for window in panes
        ]

        if self._panes:
            # http://stackoverflow.com/a/14465359
            self._panes[:] = []

        self._panes.extend(panes)

        return self._panes

    def _update_panes(self):
        self._list_panes()
        return self

    def attached_sessions(self):
        '''
            Returns active :class:`Session` object

            This will not work where multiple tmux sessions are attached.
        '''

        sessions = self._sessions
        attached_sessions = list()

        for session in sessions:
            if 'session_attached' in session:
                # for now session_active is a unicode
                if session.get('session_attached') == '1':
                    logger.debug('session %s attached', session.get(
                        'session_name'))
                    attached_sessions.append(session)
                else:
                    continue

        return attached_sessions or None

    def has_session(self, target_session):
        '''
        ``$ tmux has-session``

        :param: target_session: str of session name.

        returns True if session exists.
        '''

        proc = self.tmux('has-session', '-t%s' % target_session)

        if 'failed to connect to server' in proc.stdout:
            return False
        elif 'session not found' in proc.stdout:
            return False
        else:
            return True

    def kill_server(self):
        '''
        ``$ tmux kill-server``
        '''
        self.tmux('kill-server')

    def kill_session(self, target_session=None):
        '''
        ``$ tmux kill-session``

        :param: target_session: str. note this accepts fnmatch(3). 'asdf' will
                                kill asdfasd
        '''
        proc = self.tmux('kill-session', '-t%s' % target_session)

        if proc.stderr:
            raise Exception(proc.stderr)

        return self

    def switch_client(self, target_session):
        '''
        ``$ tmux switch-client``

        :param: target_session: str. name of the session. fnmatch(3) works.
        '''
        # tmux('switch-client', '-t', target_session)
        proc = self.tmux('switch-client', '-t%s' % target_session)

        if proc.stderr:
            raise Exception(proc.stderr)

    def attach_session(self, target_session=None):
        '''
        ``$ tmux attach-session`` aka alias: ``$ tmux attach``

        :param: target_session: str. name of the session. fnmatch(3) works.
        '''
        # tmux('switch-client', '-t', target_session)
        tmux_args = tuple()
        if target_session:
            tmux_args += ('-t%s' % target_session,)

        proc = self.tmux('attach-session', *tmux_args)

        if proc.stderr:
            raise Exception(proc.stderr)

    def new_session(self,
                    session_name=None,
                    kill_session=False,
                    attach=False,
                    *args,
                    **kwargs):
        '''
        ``$ tmux new-session``

        Returns :class:`Session`

        Uses ``-P`` flag to print session info, ``-F`` for return formatting
        returns new Session object.

        ``$ tmux new-session -d`` will create the session in the background
        ``$ tmux new-session -Ad`` will move to the session name if it already
        exists. todo: make an option to handle this.

        :param session_name: session name::

            $ tmux new-session -s <session_name>
        :type session_name: string

        :param detach: create session background::

            $ tmux new-session -d
        :type detach: bool

        :param attach_if_exists: if the session_name exists, attach it.
                                 if False, this method will raise a
                                 :exc:`tmuxp.exc.TmuxSessionExists` exception
        :type attach_if_exists: bool

        :param kill_session: Kill current session if ``$ tmux has-session``
                             Useful for testing workspaces.
        :type kill_session: bool
        '''

        if self.has_session(session_name):
            if kill_session:
                self.tmux('kill-session', '-t%s' % session_name)
                logger.info('session %s exists. killed it.' % session_name)
            else:
                raise TmuxSessionExists(
                    'Session named %s exists' % session_name
                )

        logger.debug('creating session %s' % session_name)

        sformats = formats.SESSION_FORMATS
        tmux_formats = ['#{%s}' % f for f in sformats]

        env = os.environ.get('TMUX')

        if env:
            del os.environ['TMUX']

        tmux_args = (
            '-s%s' % session_name,
            '-P', '-F%s' % '\t'.join(tmux_formats),   # output
        )

        if not attach:
            tmux_args += ('-d',)

        proc = self.tmux(
            'new-session',
            *tmux_args
        )

        if proc.stderr:
            raise Exception(proc.stderr)

        session = proc.stdout[0]

        if env:
            os.environ['TMUX'] = env

        # combine format keys with values returned from ``tmux list-windows``
        session = dict(zip(sformats, session.split('\t')))

        # clear up empty dict
        session = dict((k, v) for k, v in session.items() if v)

        session = Session(server=self, **session)

        return session
