import re
from helpers.common import *
#import spdb
# spdb.start()


class Parser:
    """
    Parses tag references and tag definitions. Used for ranking
    """
    @staticmethod
    def extract_member_exp(line_to_symbol, source):
        """
        Extract receiver object e.g. receiver.mtd()
        Strip away brackets and operators.
        TODO:HIGH: Add base lang defs + Python/Ruby/C++/Java/C#/PHP overrides (should be very similar)
        TODO: comment and string support (eat as may contain brackets. add them to context - js['prop1']['prop-of-prop1'])
        """
        lang = get_lang_setting(source)
        if not lang:
            return [line_to_symbol]

        # Get per-language syntax regex of brackets, splitters etc.
        mbr_exp = lang.get('member_exp')
        if mbr_exp is None:
            return [line_to_symbol]

        lstStop = mbr_exp.get('stop', [])
        if (not lstStop):
            print('warning!: language has member_exp setting but it is ineffective: Must have "stop" key with array of regex to stop search backward from identifier')
            return [line_to_symbol]

        lstClose = mbr_exp.get('close', [])
        reClose = concat_re(lstClose)
        lstOpen = mbr_exp.get('open', [])
        reOpen = concat_re(lstOpen)
        lstIgnore = mbr_exp.get('ignore', [])
        reIgnore = concat_re(lstIgnore)
        if len(lstOpen) != len(lstClose):
            print('warning!: extract_member_exp: settings lstOpen must match lstClose')
        matchOpenClose = dict(zip(lstOpen, lstClose))
        # Construct | regex from all open and close strings with capture (..)
        splex = concat_re(lstOpen + lstClose + lstIgnore + lstStop)

        reStop = concat_re(lstStop)
        splex = "({0}|{1})".format(splex, reIgnore)
        splat = re.split(splex, line_to_symbol)
        #print('splat=%s' %  splat)
        # Stack iter reverse(splat) for detecting unbalanced e.g 'func(obj.yyy'
        # while skipping balanced brackets in getSlow(a && b).mtd()
        stack = []
        lstMbr = []
        insideExp = False
        for cur in reversed(splat):
            # Scan backwards from the symbol: If alpha-numeric - keep it. If
            # Closing bracket e.g ] or ) or } --> push into stack
            if re.match(reClose, cur):
                stack.append(cur)
                insideExp = True
            # If opening bracket --> match it from top-of-stack: If stack empty
            # - stop else If match pop-and-continue else stop scanning +
            # warning
            elif re.match(reOpen, cur):
                # '(' with no matching ')' --> func(obj.yyy case --> return obj.yyy
                if len(stack) == 0:
                    break
                tokClose = stack.pop()
                tokCloseCur = matchOpenClose.get(cur)
                if tokClose != tokCloseCur:
                    print(
                        'non-matching brackets at the same nesting level: %s %s' %
                        (tokCloseCur, tokClose))
                    break
                insideExp = False
            # If white space --> stop. Do not stop for whitespace inside
            # open-close brackets nested expression
            elif re.match(reStop, cur):
                if not insideExp:
                    break
            elif re.match(reIgnore, cur):
                pass
            else:
                lstMbr[0:0] = cur

        strMbrExp = "".join(lstMbr)

        lstSplit = mbr_exp.get('splitters', [])
        reSplit = concat_re(lstSplit)
        # Split member deref per-lang (-> and :: in PHP and C++) - use base if
        # not found
        arrMbrParts = list(filter(None, re.split(reSplit, strMbrExp)))
        # print('arrMbrParts=%s' %  arrMbrParts)

        return arrMbrParts
