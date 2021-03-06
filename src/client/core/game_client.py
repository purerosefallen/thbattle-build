# -*- coding: utf-8 -*-
from __future__ import absolute_import

# -- stdlib --
from collections import OrderedDict
from copy import copy
import logging

# -- third party --
from gevent import Greenlet
import gevent

# -- own --
from account import Account
from game.base import GameEnded, InputTransaction, TimeLimitExceeded, AbstractPlayer
from utils import BatchList
import game.base

# -- code --
log = logging.getLogger('Game_Client')


def user_input(players, inputlet, timeout=25, type='single', trans=None):
    '''
    Type can be 'single', 'all' or 'any'
    '''
    assert type in ('single', 'all', 'any')
    assert not type == 'single' or len(players) == 1

    timeout = max(0, timeout)

    g = Game.getgame()
    inputlet.timeout = timeout
    players = list(players)

    if not trans:
        with InputTransaction(inputlet.tag(), players) as trans:
            return user_input(players, inputlet, timeout, type, trans)

    t = {'single': '', 'all': '&', 'any': '|'}[type]
    tag = 'I{0}:{1}:'.format(t, inputlet.tag())

    ilets = {p: copy(inputlet) for p in players}
    for p in players:
        ilets[p].actor = p

    inputproc = None

    def input_func(st):
        my = ilets[g.me]
        with TimeLimitExceeded(timeout + 1, False):
            _, my = g.emit_event('user_input', (trans, my))

        g.me.server.gwrite(tag + str(st), my.data())

    results = {p: None for p in players}

    synctags = {p: g.get_synctag() for p in players}
    synctags_r = {v: k for k, v in synctags.items()}

    try:
        if g.me in players:  # me involved
            g._my_user_input = (trans, ilets[g.me])

        for p in players:
            g.emit_event('user_input_start', (trans, ilets[p]))

        if g.me in players:  # me involved
            if not g.me.is_observer:  # Not observer or other things
                inputproc = gevent.spawn(input_func, synctags[g.me])

        orig_players = players[:]
        inputany_player = None

        g.emit_event('user_input_begin_wait_resp', trans)  # for replay speed control
        while players:
            # should be [tag, <Data for Inputlet.parse>]
            # tag likes 'RI?:ChooseOption:2345'
            tag_, data = g.me.server.gexpect('R%s*' % tag)
            st = int(tag_.split(':')[2])
            if st not in synctags_r:
                log.warning('Unexpected sync tag: %d', st)
                continue

            p = synctags_r[st]

            my = ilets[p]

            try:
                rst = my.parse(data)
            except:
                log.exception('user_input: exception in .process()')
                # ----- FOR DEBUG -----
                if g.IS_DEBUG:
                    raise
                # ----- END FOR DEBUG -----
                rst = None

            rst = my.post_process(p, rst)

            g.emit_event('user_input_finish', (trans, my, rst))

            if p is g.me:
                g._my_user_input = (None, None)

            players.remove(p)
            results[p] = rst

            # also remove from synctags
            del synctags_r[st]
            del synctags[p]

            if type == 'any' and rst is not None:
                assert not inputany_player
                inputany_player = p

        g.emit_event('user_input_end_wait_resp', trans)  # for replay speed control

    finally:
        if inputproc:
            inputproc.kill()
            inputproc.join()

    if type == 'single':
        return results[orig_players[0]]

    elif type == 'any':
        if not inputany_player:
            return None, None

        return inputany_player, results[inputany_player]

    elif type == 'all':
        return OrderedDict([(i, results[i]) for i in orig_players])

    assert False, 'WTF?!'


class TheChosenOne(game.base.AbstractPlayer):
    dropped = False
    is_observer = False

    def __init__(self, server):
        self.server = server
        game.base.AbstractPlayer.__init__(self)

    def reveal(self, obj_list):
        # It's me, server will tell me what the hell these is.
        g = Game.getgame()
        st = g.get_synctag()
        _, raw_data = self.server.gexpect('Sync:%d' % st)
        if isinstance(obj_list, (list, tuple)):
            for o, rd in zip(obj_list, raw_data):
                o.sync(rd)
        else:
            obj_list.sync(raw_data)  # it's single obj actually

    def update(self, data):
        # It's me and I know everything about myself
        pass


class PeerPlayer(AbstractPlayer):
    dropped = False
    is_observer = False

    def __init__(self):
        AbstractPlayer.__init__(self)
        self.account = None

    def reveal(self, obj_list):
        # Peer player, won't reveal.
        Game.getgame().get_synctag()  # must sync

    def update(self, data):
        # data comes from server.core.Player.__data__
        self.account = Account.parse(data['account'])
        self.state = data['state']

    @classmethod
    def parse(cls, data):
        pp = cls()
        pp.update(data)
        return pp

    def __repr__(self):
        return "PeerPlayer(%s)" % (self.account.username if self.account else None)

    # account = < set by update >


class TheLittleBrother(PeerPlayer):
    # Big brother is watching you!
    is_observer = True
    reveal = TheChosenOne.reveal.im_func


class Game(Greenlet, game.base.Game):
    '''
    The Game class, all game mode derives from this.
    Provides fundamental behaviors.

    Instance variables:
        players: list(Players)
        event_handlers: list(EventHandler)

        and all game related vars, eg. tags used by [EventHandler]s and [Action]s
    '''
    thegame = None
    CLIENT_SIDE = True
    SERVER_SIDE = False
    event_observer = None

    import random  # noqa, intentionally put here

    def __init__(self):
        Greenlet.__init__(self)
        game.base.Game.__init__(self)
        self.players = BatchList()
        self.game_params = {}
        self.game_items = {}

        self._my_user_input = (None, None)

    def _run(g):
        g.synctag = 0
        Game.thegame = g
        try:
            g.process_action(g.bootstrap(g.game_params, g.game_items))
        except GameEnded:
            pass

        assert g.ended

    @classmethod
    def getgame(cls):
        return cls.thegame

    def get_synctag(self):
        self.synctag += 1
        return self.synctag

    def pause(self, time):
        gevent.sleep(time)

    def _get_me(self):
        me = self._me
        for i in self.players:
            if i is me:
                return i

            if getattr(i, 'player', 0) is me:
                return i

        raise AttributeError('WTF?!')

    def _set_me(self, me):
        self._me = me

    me = property(_get_me, _set_me)
