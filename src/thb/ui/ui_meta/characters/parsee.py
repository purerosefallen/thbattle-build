# -*- coding: utf-8 -*-

# -- stdlib --
# -- third party --
# -- own --
from thb import cards, characters
from thb.ui.ui_meta.common import gen_metafunc, my_turn

# -- code --
__metaclass__ = gen_metafunc(characters.parsee)


class Parsee:
    # Character
    name        = u'水桥帕露西'
    title       = u'地壳下的嫉妒心'
    illustrator = u'和茶'
    cv          = u'小羽'

    port_image        = u'thb-portrait-parsee'
    figure_image      = u'thb-figure-parsee'
    miss_sound_effect = u'thb-cv-parsee_miss'


class Envy:
    # Skill
    name = u'嫉妒'
    description = u'你可以将一张黑色牌当|G城管执法|r使用；每当距离1的其他角色的方块牌被你使用的|G城管执法|r弃置而置入弃牌堆后，你可以获得之。'

    def clickable(game):
        me = game.me

        if my_turn() and (me.cards or me.showncards or me.equips):
            return True

        return False

    def is_action_valid(g, cl, target_list):
        skill = cl[0]
        assert skill.is_card(characters.parsee.Envy)
        cl = skill.associated_cards
        if len(cl) != 1:
            return (False, u'请选择一张牌！')
        else:
            c = cl[0]
            if c.suit not in (cards.Card.SPADE, cards.Card.CLUB):
                return (False, u'请选择一张黑色的牌！')
            return cards.DemolitionCard.ui_meta.is_action_valid(g, [skill], target_list)

    def effect_string(act):
        # for LaunchCard.ui_meta.effect_string
        source = act.source
        card = act.card
        target = act.target
        s = u'|G【%s】|r发动了嫉妒技能，将|G%s|r当作|G%s|r对|G【%s】|r使用。' % (
            source.ui_meta.name,
            card.associated_cards[0].ui_meta.name,
            card.treat_as.ui_meta.name,
            target.ui_meta.name,
        )
        return s

    def sound_effect(act):
        return 'thb-cv-parsee_envy'


class EnvyHandler:
    choose_option_buttons = ((u'获得', True), (u'不获得', False))

    def choose_option_prompt(act):
        return u'你要获得【%s】吗？' % act.card.ui_meta.name


class EnvyRecycleAction:
    def effect_string(act):
        return u'|G【%s】|r：“喂喂这么好的牌扔掉不觉得可惜么？不要嫉妒我。”' % (
            act.source.ui_meta.name
        )
