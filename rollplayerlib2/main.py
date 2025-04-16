import asyncio
import itertools
import random   
from dataclasses import dataclass, field
from enum import Enum, StrEnum

import rollplayerlib2.stopit as stopit
from rollplayerlib2.parser import Lark_StandAlone, LexError, Token, Transformer, Tree, VisitError, v_args
from heapq import nsmallest, nlargest
from collections import Counter, deque

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
        
    def apply(self, roll_value: int|float) -> int|float:
        """Applies the bonus to the roll_value.
        Args:
            roll_value (int | float): The value of the roll to apply the operation to.
        Returns:
            int | float: The value after being applied.
        """
        match self.operator:
            case Operator.ADD:
                return roll_value + self.value
            case Operator.SUB:
                return roll_value - self.value
            case Operator.DIV:
                return roll_value / self.value
            case Operator.MUL:
                return roll_value * self.value
    
@dataclass
class TargetedBonus:
    targets: list[int] | None
    operations: list[TargetedOperation]
    
    def apply(self, roll: 'Roll'):
        if self.targets == None: self.targets = range(1,len(roll.results)+1)
        if 0 in self.targets:
            raise LimitException("You can't add a bonus to a 0th dice!")
        for operation in self.operations:
            try:
                for target in self.targets:
                    roll.results[target-1] = operation.apply(roll.results[target-1])
            except IndexError as e:
                raise LimitException("You can't add a bonus to a non-existant dice! [You may have gone too far due to auto]")

class KeepType(Enum):
    HIGHER = 1
    LOWER = 2

@dataclass
class Keep():
    keep_type: KeepType
    quantity: int
    
class ConditionType(StrEnum):
    GREATER_THAN = "c_gt"
    GREATER_THAN_OR_EQUAL = "c_gte"
    LESS_THAN = "c_lt"
    LESS_THAN_OR_EQUAL = "c_lte"
    EQUAL = "c_equ"
    NOT_EQUAL = "c_neq"
    BETWEEN = "c_bet"
    MAXIMUM = "c_max" # Not in the parser, but this is used for explodes w/o a condition
    
@dataclass
class Condition:
    condition_type: ConditionType
    threshold: int | float
    threshold2: int | float | None = None
    
    def condition_match(self, roll: 'Roll'):
        """Using the Condition, returns a list of indexes of the `Roll.results` list that matches the condition.

        Args:
            roll (Roll): The roll to check against.

        Returns:
            list[int]: The list of indexes of the `Roll.results` list.
        """
        match self.condition_type:
            case ConditionType.GREATER_THAN:
                return [
                    i for i, result in enumerate(roll.results)
                    if result > self.threshold
                ]

            case ConditionType.GREATER_THAN_OR_EQUAL:
                return [
                    i for i, result in enumerate(roll.results)
                    if result >= self.threshold
                ]

            case ConditionType.LESS_THAN:
                return [
                    i for i, result in enumerate(roll.results)
                    if result < self.threshold
                ]

            case ConditionType.LESS_THAN_OR_EQUAL:
                return [
                    i for i, result in enumerate(roll.results)
                    if result <= self.threshold
                ]

            case ConditionType.EQUAL:
                return [
                    i for i, result in enumerate(roll.results)
                    if result == self.threshold
                ]

            case ConditionType.NOT_EQUAL:
                return [
                    i for i, result in enumerate(roll.results)
                    if result != self.threshold
                ]

            case ConditionType.BETWEEN:
                if self.threshold2 is None:
                    raise ValueError("threshold2 must be set for BETWEEN condition")
                low, high = sorted((self.threshold, self.threshold2))
                return [
                    i for i, result in enumerate(roll.results)
                    if low <= result <= high
                ]

            case ConditionType.MAXIMUM:
                return [
                    i for i, result in enumerate(roll.results)
                    if result == roll.range.high
                ]
                
            case _:
                raise ValueError(f"Condition type {self.condition_type} not implemented")
        
    
class ExplosionType(StrEnum):
    INFINITE = "exp_infinite"
    REDUCTIVE = "exp_reductive"
    
@dataclass
class Explosion():
    explosion_type: ExplosionType
    conditions: list[Condition]
    limit: int
    
@dataclass
class Reroll():
    conditions: list[Condition]
    limit: int

@dataclass
class ConditionalDrop():
    conditions: list[Condition]
    
@dataclass
class Modifiers():
    targeted_bonuses: list[TargetedBonus]
    keep_lower: Keep | None
    keep_higher: Keep | None
    explosion: Explosion | None
    rerolls: list[Reroll]
    drops: list[ConditionalDrop]

@dataclass
class RollResult:
    results: list[int|float]
    results_original: list[int]
    
    @property
    def total_value(self):
        return sum(self.results)
    
    def __add__(self, other):
        if isinstance(other, RollResult):
            return self.total_value + other.total_value
        if isinstance(other, (int, float)):
            return self.total_value + other
        return NotImplemented
    
    __radd__ = __add__
    
    def __sub__(self, other):
        if isinstance(other, RollResult):
            return self.total_value - other.total_value
        if isinstance(other, (int, float)):
            return self.total_value - other
        return NotImplemented
    
    def __rsub__(self, other):
        if isinstance(other, RollResult):
            return other.total_value - self.total_value
        if isinstance(other, (int, float)):
            return other - self.total_value
        return NotImplemented
    
    def __mul__(self, other):
        if isinstance(other, RollResult):
            return self.total_value * other.total_value
        if isinstance(other, (int, float)):
            return self.total_value * other
        return NotImplemented
    
    __rmul__ = __mul__
    
    def __truediv__(self, other):
        if isinstance(other, RollResult):
            return self.total_value / other.total_value
        if isinstance(other, (int, float)):
            return self.total_value / other
        return NotImplemented
    
    def __truediv__(self, other):
        if isinstance(other, RollResult):
            return other.total_value / self.total_value
        if isinstance(other, (int, float)):
            return other / self.total_value
        return NotImplemented
    
    def __neg__(self):
        for index, result in enumerate(self.results):
            self.results[index] = -result
        return self
    
    def __str__(self):
        if len(self.results) > 1:
            return f"{", ".join([str(x) for x in self.results])} (total: {self.total_value})"
        return str(self.results[0])
    
    def str_originalresults(self):
        if len(self.results_original) > 1:
            return f"{", ".join([str(x) for x in self.results_original])} (total: {sum(self.results_original)})"
        return str(self.results_original[0])
    
@dataclass
class Roll():
    quantity: int
    range: Range
    modifiers: Modifiers
    results: list[int|float] | None = None
    results_original: list[int] | None = None
    
    def _roll_die(self) -> int:
        return random.randint(self.range.low, self.range.high)
    
    def _check_value_meets_explosion_conditions(self, value_to_check: int | float) -> bool:
        """
        Helper function for clarity within process_explosion.
        """
        if not self.modifiers.explosion or not self.modifiers.explosion.conditions:
            return False

        explosion_cfg = self.modifiers.explosion

        for condition in explosion_cfg.conditions:
            condition_met = False
            match condition.condition_type:
                case ConditionType.GREATER_THAN:
                    condition_met = (value_to_check > condition.threshold)
                case ConditionType.GREATER_THAN_OR_EQUAL:
                    condition_met = (value_to_check >= condition.threshold)
                case ConditionType.LESS_THAN:
                    condition_met = (value_to_check < condition.threshold)
                case ConditionType.LESS_THAN_OR_EQUAL:
                    condition_met = (value_to_check <= condition.threshold)
                case ConditionType.EQUAL:
                    condition_met = (value_to_check == condition.threshold)
                case ConditionType.NOT_EQUAL:
                    condition_met = (value_to_check != condition.threshold)
                case ConditionType.BETWEEN:
                    if condition.threshold2 is not None:
                        low = min(condition.threshold, condition.threshold2)
                        high = max(condition.threshold, condition.threshold2)
                        condition_met = (low <= value_to_check <= high)
                case ConditionType.MAXIMUM:
                    condition_met = (value_to_check == self.range.high)
                case _: pass

        return condition_met
    
    def process_keeps(self):
        if not self.modifiers.keep_higher and not self.modifiers.keep_lower:
            return
        try:
            higher = self.modifiers.keep_higher.quantity 
        except AttributeError:
            higher = 0
        try:
            lower = self.modifiers.keep_lower.quantity
        except AttributeError:
            lower = 0
        if higher == 0 and lower == 0:
            raise LimitException("You can't keep nothing!")
        low = nsmallest(lower, self.results) if lower > 0 else []
        high = nlargest(higher, self.results) if higher > 0 else []
        counts = Counter(low + high)

        result = []
        for x in self.results:
            if counts[x] > 0:
                result.append(x)
                counts[x] -= 1
        self.results = result
        
    def process_drops(self):
        to_drop = set()
        for drop in self.modifiers.drops:
            for condition in drop.conditions:
                to_drop |= set(condition.condition_match(self))

        std = sorted(to_drop, reverse=True)
        for idx in std:
            del self.results[idx]
        
    def process_rerolls(self):
        for rr in self.modifiers.rerolls:
            for attempt in range(rr.limit):
                to_reroll = set()
                for condition in rr.conditions:
                    to_reroll |= set(condition.condition_match(self))
                if len(to_reroll) == 0: break
                for reroll in to_reroll:
                    self.results[reroll] = random.randint(self.range.low, self.range.high)
                    
    def process_explosion(self):
        if not self.modifiers.explosion or \
           not self.results or \
           self.modifiers.explosion.limit <= 0 or \
           not self.modifiers.explosion.conditions:
            return

        explosion_cfg = self.modifiers.explosion
        initial_quantity = len(self.results)

        explosion_counts = [0] * initial_quantity
        for i in range(initial_quantity):
            current_value_to_check = self.results[i]

            while True: 
                triggers_explosion = self._check_value_meets_explosion_conditions(current_value_to_check)
                if not triggers_explosion or explosion_counts[i] >= explosion_cfg.limit:
                    break
                
                explosion_counts[i] += 1
                new_roll_value = self._roll_die()
                self.results[i] += new_roll_value
                current_value_to_check = new_roll_value

    def process_targeted_bonuses(self):
        for t_bonus in self.modifiers.targeted_bonuses:
            t_bonus.apply(self)
                
    def process(self):
        results = []
        for idx in range(self.quantity):
            results.append(random.randint(self.range.low, self.range.high))
        self.results = results
        self.results_original = results.copy()
        self.process_keeps()
        self.process_drops()
        self.process_rerolls()
        self.process_explosion()
        self.process_targeted_bonuses()
    
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
            return TargetedBonus(None, ops)
        return TargetedBonus([int(number) for number in tree_list[0].children], ops)
    
    def keep_higher(self, tree_list):
        if not tree_list:
            return Keep(KeepType.HIGHER, 1)
        return Keep(KeepType.HIGHER, int(tree_list[0].value))
    
    def keep_lower(self, tree_list):
        if not tree_list:
            return Keep(KeepType.LOWER, 1)
        return Keep(KeepType.LOWER, int(tree_list[0].value))
    
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
        limit = 1
        if len(tree_list) == 2:
            limit = self.limit_check(int(tree_list[1].value))
        return Reroll(cond_list, limit)

class DiceRollTransformer(Transformer):
    def __init__(self, dice_count_limit: int, gamemaster: bool, visit_tokens: bool = True):
        super().__init__(visit_tokens)
        self.dice_count_limit = dice_count_limit
        self.gamemaster = gamemaster
    
    def check_qty(self, limit):
        if limit == 0:
            raise LimitException("You can't roll zero dice!")
        if limit <= self.dice_count_limit:
            return limit
        if not self.gamemaster:
            raise RollplayerGamemasterUpsellException(f"You can't increase the dice quantity past {self.dice_count_limit} without Rollplayer Gamemaster.")
        raise LimitException(f"The quantity limit of {self.dice_count_limit} was reached.")
    
    def modifiers(self, tree_list): 
        targeted_bonuses = []
        keep_higher = None
        keep_lower = None
        explosion = None
        rerolls = []
        drops = []
        for value in tree_list:
            if type(value) == TargetedBonus:
                targeted_bonuses.append(value)
                continue
            if type(value) == Keep:
                if value.keep_type == KeepType.HIGHER:
                    if keep_higher:
                        raise LimitException("You can't have multiple keep highers in the same roll!")
                    keep_higher = value
                else:
                    if keep_lower:
                        raise LimitException("You can't have multiple keep lowers in the same roll!")
                    keep_lower = value
                continue
            if type(value) == Explosion:
                if explosion:
                    raise LimitException("You can't have multiple explosions in the same roll!")
                explosion = value
                continue
            if type(value) == Reroll:
                rerolls.append(value)
                continue
            if type(value) == ConditionalDrop:
                drops.append(value)
                continue
        return Modifiers(targeted_bonuses, keep_lower, keep_higher, explosion, rerolls, drops)
    
    def dice(self, tree_list):
        qty = 1
        if type(tree_list[0]) == Token:
            qty = self.check_qty(int(tree_list[0].value))
            tree_list = tree_list[1:]
        roll = Roll(qty, tree_list[0], tree_list[1])
        roll.process()
        return RollResult(roll.results, roll.results_original)
            

@v_args(inline=True)    # Affects the signatures of the methods
class MathTransformer(Transformer):
    number = to_number
    from operator import add, sub, mul, truediv as div, neg
    
    def start(self, ret):
        return ret


parser = Lark_StandAlone()

async def transformer_default(string) -> RollResult | int | float:
    """Transformer that acts like it has Rollplayer Gamemaster without actually having it [used as a stopgap until we have proper payment set up]
    """
    loop = asyncio.get_running_loop()
    
    with stopit.ThreadingTimeout(2) as to_ctx_mgr:
        assert to_ctx_mgr.state == to_ctx_mgr.EXECUTING
        tree = parser.parse(string)
        tree = await loop.run_in_executor(None, RollplayerLibTransformer().transform, tree)
        tree = await loop.run_in_executor(None, ExplodeLimitTransformer(5, True).transform, tree)
        tree = await loop.run_in_executor(None, RerollLimitTransformer(5, True).transform, tree)
        tree = await loop.run_in_executor(None, DiceRollTransformer(1000, True).transform, tree)
        tree = await loop.run_in_executor(None, MathTransformer().transform, tree)
    
    if to_ctx_mgr:
        return tree
    else:
        raise LimitException("The roll timed out (2s).")

async def transformer_gm(string) -> RollResult | int | float:
    """Transformer for Rollplayer Gamemaster members.
    """
    loop = asyncio.get_running_loop()
    
    with stopit.ThreadingTimeout(4) as to_ctx_mgr:
        assert to_ctx_mgr.state == to_ctx_mgr.EXECUTING
        tree = parser.parse(string)
        tree = await loop.run_in_executor(None, RollplayerLibTransformer().transform, tree)
        tree = await loop.run_in_executor(None, ExplodeLimitTransformer(50, True).transform, tree)
        tree = await loop.run_in_executor(None, RerollLimitTransformer(30, True).transform, tree)
        tree = await loop.run_in_executor(None, DiceRollTransformer(10000, True).transform, tree)
        tree = await loop.run_in_executor(None, MathTransformer().transform, tree)
    
    if to_ctx_mgr:
        return tree
    else:
        raise LimitException("The roll timed out (4s).")

async def transformer_nongm(string) -> RollResult | int | float:
    """Transformer for non-members.
    """
    loop = asyncio.get_running_loop()
    
    with stopit.ThreadingTimeout(2) as to_ctx_mgr:
        assert to_ctx_mgr.state == to_ctx_mgr.EXECUTING
    tree = parser.parse(string)
    tree = await loop.run_in_executor(None, RollplayerLibTransformer().transform, tree)
    tree = await loop.run_in_executor(None, ExplodeLimitTransformer(5, False).transform, tree)
    tree = await loop.run_in_executor(None, RerollLimitTransformer(5, False).transform, tree)
    tree = await loop.run_in_executor(None, DiceRollTransformer(1000, False).transform, tree)
    tree = await loop.run_in_executor(None, MathTransformer().transform, tree)
    
    if to_ctx_mgr:
        return tree
    else:
        raise RollplayerGamemasterUpsellException("The roll timed out (2s). You can extend the timeout window with Rollplayer Gamemaster.")

async def __module_run():
    import traceback
    import time
    try:
        mode = input("What mode you want? t for test, r for run: ")
        if mode == "t":
            start = time.process_time()
            for x in range(1000):
                tree = await transformer_default("10d100..200i*:+20:+20i1,2:+20kh4kl4!{>=170}:5rr{<=130}:5")
            end = time.process_time() - start
            print("process time [rollplayerlib2] [1,000 rolls of <10d100..200i*:+20:+20i1,2:+20kh4kl4!{>=170}:5rr{<=130}:5>]")
            print(f"{end:3f}s ({end/1000:6f}s/roll)")
            from rollplayerlib import UnifiedDice, SolveMode
            solvemode = SolveMode.RANDOM
            start2 = time.process_time()
            UnifiedDice.new("10d100:200+20+20i1,2:+20").solve(solvemode)
            end2 = time.process_time() - start2
            print("process time [rollplayerlib1] [1,000 rolls of <10d100..200>]")
            print(f"{end2:3f}s ({end2/1000:6f}s/roll)")
        elif mode == "r":
            mode2 = input("run [p]re-defined test or [i]nput your own?: ")
            if mode2 == "p":
                tree = await transformer_default("10d100..200i*:+20:+20i1,2:+20kh4kl4!{>=170}:5rr{<=130}:5dr{150:200}")
            elif mode2 == "i":
                string = input("type a roll: ")
                tree = await transformer_default(string)
            print(tree)
    except LexError as e:
        traceback.print_exc()
    except VisitError as e:
        traceback.print_exception(e.orig_exc)
        
if __name__ == "__main__":
    asyncio.run(__module_run())