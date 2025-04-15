import asyncio
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from parser import Lark_StandAlone, LexError, Token, Transformer, Tree, VisitError, v_args

def to_number(string):
    try: 
        return int(string)
    except ValueError:
        pass
    return float(string)
    

class RollplayerParsingException(Exception):
    """Base class for all Rollplayer library parsing exceptions.
    """
    def __init__(self, *args):
        super().__init__(*args)

class RollplayerGamemasterUpsellException(RollplayerParsingException):
    """Upsell the user if default limits are reached.
    """
    def __init__(self, upsell_msg, *args):
        super().__init__(upsell_msg, *args)
        self.upsell_msg = upsell_msg
        
class LimitException(RollplayerParsingException):
    """If the user breaks a limit [with Rollplayer Gamemaster, or if a limit is shared between the two.]
    """
    def __init__(self, *args):
        super().__init__(*args)

class Operator(StrEnum):
    ADD = "t_add"
    SUB = "t_sub"
    DIV = "t_div"
    MUL = "t_mul"
    
@dataclass
class Range:
    low: int
    high: int
    
    def swap_if_needed(self):
        if self.low > self.high:
            self.high, self.low = self.low, self.high
            
@dataclass
class TargetedOperation:
    operator: Operator
    value: int | float
        
    @property
    def operator_string(self):
        match self.operator:
            case Operator.ADD:
                return "+"
            case Operator.SUB:
                return "-"
            case Operator.DIV:
                return "/"
            case Operator.MUL:
                return "*"
            case _:
                return "?"
    
@dataclass
class TargetedBonuses:
    targets: list[int] | None
    operations: list[TargetedOperation]

class KeepType(Enum):
    HIGHER = 1
    LOWER = 2

@dataclass
class Keeps():
    keep_type: KeepType
    quantity: int
    
class ConditionType(StrEnum):
    GREATER_THAN = "c_gt"
    GREATER_THAN_OR_EQUAL = "c_gte"
    LESS_THAN = "c_lt"
    LESS_THAN_OR_EQUAL = "c_lte"
    EQUAL = "c_equ"
    BETWEEN = "c_bet"
    MAXIMUM = "c_max" # Not in the parser, but this is used for explodes w/o a condition
    
@dataclass
class Condition:
    condition_type: ConditionType
    threshold: int | float
    threshold2: int | float | None = None
    
class ExplosionType(StrEnum):
    INFINITE = "exp_infinite"
    REDUCTIVE = "exp_reductive"
    
@dataclass
class Explosion():
    explosion_type: int
    conditions: list[Condition]
    limit: int
    
@dataclass
class Reroll():
    conditions: list[Condition]
    limit: int

@dataclass
class ConditionalDrop():
    conditions: list[Condition]
    
class RollplayerLibTransformer(Transformer):
    def range(self, tree_list):
        if tree_list[0].data == "range_percent":
            return Range(1, 100)
        if tree_list[0].data == "range_between":
            range = Range(int(tree_list[0].children[0].value), int(tree_list[0].children[1].value))
        if tree_list[0].data == "range_simple":
            range = Range(1, int(tree_list[0].children[0].value))
        range.swap_if_needed()
        return range
    
    def number(self, tree_list):
        return float(tree_list[0].value)  
    
    def targeted_operation(self, tree_list):
        return TargetedOperation(Operator(tree_list[0].data), to_number(tree_list[1].value))
    
    def targeted_bonuses(self, tree_list):
        ops = tree_list[1:]
        if not tree_list[0].children: # wildcard
            return TargetedBonuses(None, ops)
        return TargetedBonuses([int(number) for number in tree_list[0].children], ops)
    
    def keep_higher(self, tree_list):
        if not tree_list:
            return Keeps(KeepType.HIGHER, 1)
        return Keeps(KeepType.HIGHER, int(tree_list[0].value))
    
    def keep_lower(self, tree_list):
        if not tree_list:
            return Keeps(KeepType.LOWER, 1)
        return Keeps(KeepType.LOWER, int(tree_list[0].value))
    
    def condition(self, tree_list):
        if type(tree_list[1]) == Tree:
            return Condition(ConditionType.BETWEEN, to_number(tree_list[0].value), to_number(tree_list[2].value))
        return Condition(ConditionType(tree_list[0].data), to_number(tree_list[1].value))
        
    def condition_list(self, tree_list):
        condition_list = []
        for value in tree_list:
            if type(value) == Condition:
                condition_list.append(value)
            else:
                condition_list.append(Condition(ConditionType.EQUAL, to_number(value.value)))
        return condition_list
    
    def conditional_drop(self, tree_list):
        return ConditionalDrop(tree_list[0])
    
    #def dice(self, tree_list):
    #    print(tree_list)

class ExplodeLimitTransformer(Transformer):
    def __init__(self, limit: int, gamemaster: bool, visit_tokens: bool = True):
        super().__init__(visit_tokens)
        self.limit = limit
        self.gamemaster = gamemaster
    
    def limit_check(self, limit):
        if limit <= self.limit:
            return limit
        if not self.gamemaster:
            raise RollplayerGamemasterUpsellException(f"You can't increase the explosion limit past {self.limit} without Rollplayer Gamemaster.")
        raise LimitException(f"The explosion limit of {self.limit} was reached.")
    
    def explode(self, tree_list):
        exp_type = ExplosionType(tree_list[0].data)
        cond_list = [Condition(ConditionType.MAXIMUM, -1)]
        limit = self.limit
        if len(tree_list) == 1:
            pass
        elif len(tree_list) == 2:
            if type(tree_list[1]) == Token:
                limit = self.limit_check(int(tree_list[1].value))
            else:
                cond_list = tree_list[1]
        else:
            cond_list = tree_list[1]
            limit = self.limit_check(int(tree_list[2].value))
        return Explosion(exp_type, cond_list, limit)
    
class RerollLimitTransformer(Transformer):
    def __init__(self, limit: int, gamemaster: bool, visit_tokens: bool = True):
        super().__init__(visit_tokens)
        self.limit = limit
        self.gamemaster = gamemaster
    
    def limit_check(self, limit):
        if limit <= self.limit:
            return limit
        if not self.gamemaster:
            raise RollplayerGamemasterUpsellException(f"You can't increase the reroll limit past {self.limit} without Rollplayer Gamemaster.")
        raise LimitException(f"The reroll limit of {self.limit} was reached.")
    
    def reroll_condition(self, tree_list):
        cond_list = tree_list[0]
        limit = self.limit
        if len(tree_list) == 2:
            limit = self.limit_check(int(tree_list[1].value))
        return Reroll(cond_list, limit)

class DiceRollTransformer(Transformer):
    def __init__(self, dice_count_limit: int, gamemaster: bool, visit_tokens: bool = True):
        super().__init__(visit_tokens)
        self.dice_count_limit = dice_count_limit
        self.gamemaster = gamemaster
        
    def modifiers(self): pass

parser = Lark_StandAlone()

async def transformer_default(string):
    """Transformer that acts like it has Rollplayer Gamemaster without actually having it [used as a stopgap until we have proper payment set up]
    """
    loop = asyncio.get_running_loop()
    
    tree = parser.parse(string)
    tree = await loop.run_in_executor(None, RollplayerLibTransformer().transform, tree)
    tree = await loop.run_in_executor(None, ExplodeLimitTransformer(25, True).transform, tree)
    tree = await loop.run_in_executor(None, RerollLimitTransformer(5, True).transform, tree)
    return tree

async def transformer_gm(string):
    """Transformer for Rollplayer Gamemaster members.
    """
    loop = asyncio.get_running_loop()
    
    tree = parser.parse(string)
    tree = await loop.run_in_executor(None, RollplayerLibTransformer().transform, tree)
    tree = await loop.run_in_executor(None, ExplodeLimitTransformer(50, True).transform, tree)
    tree = await loop.run_in_executor(None, RerollLimitTransformer(15, True).transform, tree)
    return tree

async def transformer_nongm(string):
    """Transformer for non-members.
    """
    loop = asyncio.get_running_loop()
    
    tree = parser.parse(string)
    tree = await loop.run_in_executor(None, RollplayerLibTransformer().transform, tree)
    tree = await loop.run_in_executor(None, ExplodeLimitTransformer(25, False).transform, tree)
    tree = await loop.run_in_executor(None, RerollLimitTransformer(5, False).transform, tree)
    return tree

async def __module_run():
    import traceback
    try:
        tree = await transformer_default("10d100..200i*:+20:+20i1,2:+20kh2kl!{1,>=90}:20rr{<=20}:5dr{50:54}")
        print(tree.pretty())
    except LexError as e:
        traceback.print_exc()
    except VisitError as e:
        traceback.print_exception(e.orig_exc)
        
if __name__ == "__main__":
    asyncio.run(__module_run())