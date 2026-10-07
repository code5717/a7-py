"""Rejection-only requirements for a certified readonly statement fragment."""
from dataclasses import dataclass, field
from a7.ast_nodes import ASTNode, AssignOp, BinaryOp, LiteralKind, NodeKind, UnaryOp
from a7.types import INTEGER_RANGES, PrimitiveType, ReferenceType


@dataclass(eq=False, repr=False)
class ReadState:
    guard: int
    values: dict = field(default_factory=dict)
    defers: list = field(default_factory=list)

    def copy(self):
        return ReadState(self.guard, dict(self.values), [list(items) for items in self.defers])


class ReadonlyRequirements:
    def __init__(self, key, node_type, globals_):
        self.key = key
        self.node_type = node_type
        self.globals = globals_
        self.nodes = []
        self.interned = {}
        self.false = self.node('constant', False)
        self.true = self.node('constant', True)
        self.unknown = self.node('unknown')
        self.summaries = {}
        self.reasons = {}
        self.origins = {}
        self.dispositions = []

    def node(self, tag, *parts):
        key = (tag, *parts)
        found = self.interned.get(key)
        if found is None:
            found = len(self.nodes)
            self.interned[key] = found
            self.nodes.append(key)
        return found

    def negate(self, value):
        if value == self.true:
            return self.false
        if value == self.false:
            return self.true
        node = self.nodes[value]
        return node[1] if node[0] == 'not' else self.node('not', value)

    def combine(self, tag, *values):
        neutral, absorbing = (self.true, self.false) if tag == 'and' else (self.false, self.true)
        parts = set()
        for value in values:
            if value == absorbing:
                return absorbing
            if value == neutral:
                continue
            item = self.nodes[value]
            parts.update(item[1] if item[0] == tag else (value,))
        for part in parts:
            item = self.nodes[part]
            if item[0] == 'not' and item[1] in parts:
                return absorbing
        if not parts:
            return neutral
        if len(parts) == 1:
            return next(iter(parts))
        return self.node(tag, tuple(sorted(parts)))

    def choose(self, condition, yes, no):
        if condition == self.true or yes == no:
            return yes
        if condition == self.false:
            return no
        return self.node('choice', condition, yes, no)

    def build(self, bodies):
        dependencies = {}
        counts = {}
        for name, function in bodies.items():
            dependencies[name] = []
            seen = set()
            pending = [function.body]
            while pending:
                item = pending.pop()
                if item is None or id(item) in seen:
                    continue
                seen.add(id(item))
                if item.kind == NodeKind.FUNCTION:
                    continue
                if item.kind == NodeKind.CALL:
                    target = self.key(item.function) if item.function and item.function.kind == NodeKind.IDENTIFIER else None
                    dependencies[name].append(target)
                for value in vars(item).values():
                    if isinstance(value, ASTNode):
                        pending.append(value)
                    elif isinstance(value, list):
                        pending.extend(x for x in value if isinstance(x, ASTNode))
            counts[name] = len(seen)
        self.work_bound = max(1, sum(counts.values()) ** 2)
        work = {}
        remaining = set(bodies)
        while remaining:
            ready = [name for name in remaining if all(c not in remaining for c in dependencies[name])]
            if not ready:
                for name in remaining:
                    self.reasons[name] = {'cyclic or unresolved declaration dependency'}
                break
            for name in ready:
                remaining.remove(name)
                reasons = set()
                cost = counts[name]
                for callee in dependencies[name]:
                    if callee not in bodies or self.reasons.get(callee):
                        reasons.add('unknown or incomplete callee')
                    cost = min(self.work_bound + 1, cost + work.get(callee, 0))
                work[name] = cost
                if cost > self.work_bound:
                    reasons.add('transitive work exceeds squared source-node certificate')
                self.reasons[name] = reasons
                if reasons:
                    continue
                function = bodies[name]
                state = ReadState(self.true)
                for index, parameter in enumerate(function.parameters or []):
                    typ = self.node_type(parameter)
                    if not isinstance(typ, (PrimitiveType, ReferenceType)) and (parameter.param_type is None or parameter.param_type.kind not in {NodeKind.TYPE_POINTER, NodeKind.TYPE_PRIMITIVE}):
                        reasons.add('aggregate or unresolved formal')
                    state.values[self.key(parameter)] = self.node('parameter', index)
                failures = []
                stack = [self.steps(function.body, state, failures, reasons)]
                while stack:
                    frame = stack[-1]
                    try:
                        child, child_state = next(frame)
                    except StopIteration:
                        stack.pop()
                    else:
                        stack.append(self.steps(child, child_state, failures, reasons))
                if not reasons:
                    root = self.combine('or', *failures)
                    costs = []
                    for entry in self.nodes:
                        tag = entry[0]
                        children = entry[1] if tag in {'and', 'or'} else (entry[1],) if tag in {'not', 'read'} else entry[2:] if tag == 'compare' else entry[1:] if tag == 'choice' else (entry[1], *entry[2]) if tag == 'apply' else ()
                        costs.append(min(self.work_bound + 1, 1 + sum(costs[child] for child in children)))
                    work[name] = costs[root]
                    if costs[root] > self.work_bound:
                        reasons.add('expanded requirement graph exceeds squared source-node certificate')
                    else:
                        self.summaries[name] = root
        self.expanded_work = work

    def expression(self, root, state, failures, reasons):
        if root is None:
            return self.unknown
        values = {}
        pending = [(root, False)]
        while pending:
            node, finish = pending.pop()
            kind = node.kind
            children = []
            if kind == NodeKind.BINARY:
                children = [node.left, node.right]
            elif kind == NodeKind.UNARY:
                children = [node.operand]
            elif kind == NodeKind.FIELD_ACCESS:
                children = [node.object]
            elif kind == NodeKind.CALL:
                children = list(node.arguments or [])
            if not finish:
                pending.append((node, True))
                pending.extend((c, False) for c in reversed(children) if c is not None)
                continue
            result = self.unknown
            if kind == NodeKind.LITERAL:
                if node.literal_kind == LiteralKind.NIL:
                    result = self.true
                elif node.literal_kind in {LiteralKind.BOOLEAN, LiteralKind.INTEGER}:
                    # Tagged constants distinguish Python's equal bool/int keys.
                    result = self.node('constant', node.literal_value) if node.literal_kind == LiteralKind.BOOLEAN else self.node('integer', int(node.literal_value))
                else:
                    reasons.add('unsupported literal')
            elif kind == NodeKind.IDENTIFIER:
                key = self.key(node)
                if key in self.globals:
                    reasons.add('global storage')
                result = state.values.get(key, self.unknown)
            elif kind == NodeKind.FIELD_ACCESS:
                if node.object.kind != NodeKind.IDENTIFIER or isinstance(self.node_type(node), ReferenceType):
                    reasons.add('selected or reference-valued field')
                elif isinstance(self.node_type(node.object), ReferenceType):
                    origin = id(node)
                    self.origins[origin] = node
                    failing = self.combine('and', state.guard, values[id(node.object)])
                    failures.append(self.node('read', failing, origin))
                else:
                    reasons.add('aggregate field root')
            elif kind == NodeKind.UNARY and node.operator == UnaryOp.NOT:
                result = self.negate(values[id(node.operand)])
            elif kind == NodeKind.BINARY:
                left, right = values[id(node.left)], values[id(node.right)]
                if node.operator in {BinaryOp.AND, BinaryOp.OR}:
                    # Calls/reads in a short-circuit operand need guarded effects.
                    pure = list(children)
                    while pure:
                        child = pure.pop()
                        if child.kind == NodeKind.BINARY:
                            pure.extend([child.left, child.right])
                        elif child.kind == NodeKind.UNARY:
                            pure.append(child.operand)
                        elif child.kind not in {NodeKind.IDENTIFIER, NodeKind.LITERAL}:
                            reasons.add('effectful short-circuit operand')
                    result = self.combine('and' if node.operator == BinaryOp.AND else 'or', left, right)
                elif node.operator in {BinaryOp.EQ, BinaryOp.NE, BinaryOp.LT, BinaryOp.LE, BinaryOp.GT, BinaryOp.GE}:
                    ref_operands = any(isinstance(self.node_type(c), ReferenceType) for c in children)
                    if ref_operands and not (node.operator in {BinaryOp.EQ, BinaryOp.NE} and any(c.kind == NodeKind.LITERAL and c.literal_kind == LiteralKind.NIL for c in children)):
                        reasons.add('reference comparison beyond nil')
                    result = self.node('compare', node.operator.name, left, right)
                else:
                    reasons.add('unrepresented arithmetic')
            elif kind == NodeKind.CALL:
                target = self.key(node.function) if node.function and node.function.kind == NodeKind.IDENTIFIER else None
                if target not in self.summaries:
                    reasons.add('unknown or incomplete callee')
                else:
                    # An implicit borrow contributes a non-nil address, not its scalar value.
                    borrowed = getattr(node, "implicit_ref_args", ())
                    args = tuple(self.false if index in borrowed else values[id(arg)]
                                 for index, arg in enumerate(node.arguments or []))
                    failures.append(self.combine('and', state.guard, self.node('apply', self.summaries[target], args)))
                    if isinstance(self.node_type(node), ReferenceType):
                        reasons.add('reference-returning call')
            else:
                reasons.add('unsupported expression ' + kind.name.lower())
            values[id(node)] = result
        return values[id(root)]

    def steps(self, node, state, failures, reasons):
        if node is None:
            return
        kind = node.kind
        if kind == NodeKind.BLOCK:
            prior_keys = set(state.values)
            state.defers.append([])
            for statement in node.statements or []:
                yield statement, state
            deferred = state.defers.pop()
            for statement in reversed(deferred):
                yield statement, state
            for key in set(state.values) - prior_keys:
                del state.values[key]
        elif kind in {NodeKind.VAR, NodeKind.CONST}:
            state.values[self.key(node)] = self.expression(node.value, state, failures, reasons)
        elif kind == NodeKind.ASSIGNMENT:
            if node.target is None or node.target.kind != NodeKind.IDENTIFIER or self.key(node.target) in self.globals or getattr(node, 'implicit_deref_target', False) or node.operator != AssignOp.ASSIGN:
                reasons.add('nonlocal or compound assignment')
            else:
                state.values[self.key(node.target)] = self.expression(node.value, state, failures, reasons)
        elif kind == NodeKind.EXPRESSION_STMT:
            self.expression(node.expression, state, failures, reasons)
        elif kind == NodeKind.IF_STMT:
            condition = self.expression(node.condition, state, failures, reasons)
            yes, no = state.copy(), state.copy()
            yes.guard = self.combine('and', state.guard, condition)
            no.guard = self.combine('and', state.guard, self.negate(condition))
            yield node.then_stmt, yes
            yield node.else_stmt, no
            state.guard = self.combine('or', yes.guard, no.guard)
            for key in set(yes.values) | set(no.values):
                state.values[key] = self.choose(condition, yes.values.get(key, self.unknown), no.values.get(key, self.unknown))
            if yes.defers != no.defers:
                reasons.add('conditional unscoped defer registration')
        elif kind == NodeKind.DEFER:
            if not state.defers:
                reasons.add('unscoped defer')
            else:
                state.defers[-1].append(node.statement)
        elif kind == NodeKind.RETURN:
            if node.value is not None:
                self.expression(node.value, state, failures, reasons)
                if isinstance(self.node_type(node.value), ReferenceType):
                    reasons.add('reference return')
            saved_defers = state.defers
            state.defers = []
            for deferred in reversed(saved_defers):
                for statement in reversed(deferred):
                    yield statement, state
            state.defers = saved_defers
            state.guard = self.false
        elif kind in {NodeKind.FOR, NodeKind.WHILE}:
            if node.init is not None:
                yield node.init, state
            condition = self.expression(node.condition, state, failures, reasons)
            counter = None
            finite = False
            if kind == NodeKind.FOR:
                test, update = node.condition, node.update
                if test and test.kind == NodeKind.BINARY and test.left.kind == NodeKind.IDENTIFIER and test.operator in {BinaryOp.LT, BinaryOp.LE} and update and update.kind == NodeKind.ASSIGNMENT and update.target.kind == NodeKind.IDENTIFIER and update.operator == AssignOp.ADD_ASSIGN and self.key(update.target) == self.key(test.left):
                    counter = self.key(test.left)
                    initial = self.nodes[state.values.get(counter, self.unknown)]
                    bound = self.nodes[self.expression(test.right, state, failures, reasons)]
                    increment = self.nodes[self.expression(update.value, state, failures, reasons)]
                    typ = self.node_type(test.left)
                    if initial[0] == bound[0] == increment[0] == 'integer' and increment[1] > 0 and isinstance(typ, PrimitiveType) and typ.name in INTEGER_RANGES:
                        first, stop, step = initial[1], bound[1], increment[1]
                        count = max(0, (stop - first + (1 if test.operator == BinaryOp.LE else 0) + step - 1) // step)
                        low, high = INTEGER_RANGES[typ.name]
                        finite = low <= first <= high and low <= first + count * step <= high
                if not finite:
                    reasons.add('unrepresented counted loop')
            pending = [node.body]
            seen = set()
            while pending:
                item = pending.pop()
                if item is None or id(item) in seen:
                    continue
                seen.add(id(item))
                if item.kind in {NodeKind.ASSIGNMENT, NodeKind.BREAK, NodeKind.CONTINUE}:
                    reasons.add('loop mutation or structured exit')
                if counter is not None and item.kind == NodeKind.IDENTIFIER and self.key(item) == counter:
                    reasons.add('body depends on induction counter')
                for value in vars(item).values():
                    if isinstance(value, ASTNode):pending.append(value)
                    elif isinstance(value, list):pending.extend(x for x in value if isinstance(x, ASTNode))
            body = state.copy()
            body.guard = self.combine('and', state.guard, condition)
            yield node.body, body
            if finite:
                state.values[counter] = self.node('integer', first + count * step)
                state.guard = self.combine('or', self.combine('and', state.guard, self.negate(condition)), body.guard)
            else:
                state.guard = self.combine('and', state.guard, self.negate(condition))
        elif kind == NodeKind.MATCH:
            value = self.expression(node.expression, state, failures, reasons)
            remaining = state.guard
            arms = []
            for case in node.cases or []:
                predicates = []
                for pattern in case.patterns or []:
                    if pattern.kind == NodeKind.PATTERN_LITERAL:
                        predicates.append(self.node('compare', 'EQ', value, self.expression(pattern.literal, state, failures, reasons)))
                    else:
                        reasons.add('unrepresented match pattern')
                condition = self.combine('or', *predicates)
                arm = state.copy();arm.guard = self.combine('and', remaining, condition)
                remaining = self.combine('and', remaining, self.negate(condition))
                for statement in [case.statement, *(case.statements or [])]:
                    if statement is not None:yield statement, arm
                arms.append(arm)
            arm = state.copy();arm.guard = remaining
            if isinstance(node.else_case, ASTNode):yield node.else_case, arm
            elif node.else_case:
                for statement in node.else_case:yield statement, arm
            arms.append(arm)
            state.guard = self.combine('or', *(arm.guard for arm in arms))
            if any(any(arm.values.get(key) != value for key, value in state.values.items()) or arm.defers != state.defers for arm in arms):
                reasons.add('match local transfer')
        elif kind == NodeKind.FUNCTION:
            pass
        else:
            reasons.add('unsupported statement ' + kind.name.lower())

    def evaluate(self, name, arguments):
        if name not in self.summaries:
            return None, None, 'incomplete declaration'
        environments = [tuple(arguments)]
        env_ids = {tuple((type(value), value) for value in environments[0]): 0}
        cache = {}
        root = (self.summaries[name], 0)
        pending = [(root, False)]
        while pending:
            key, finish = pending.pop()
            if key in cache:
                continue
            ident, env_id = key
            node = self.nodes[ident];tag = node[0]
            if tag in {'constant', 'integer'}:
                cache[key] = (node[1], None);continue
            if tag == 'unknown':cache[key] = (None, None);continue
            if tag == 'parameter':
                env = environments[env_id];cache[key] = (env[node[1]] if node[1] < len(env) else None, None);continue
            if tag == 'apply':
                children = [(arg, env_id) for arg in node[2]]
                if not finish:
                    pending.append((key, True));pending.extend((child, False) for child in reversed(children));continue
                actual = tuple(cache[child][0] for child in children)
                # Equal Python bool/int values remain distinct A7 argument domains.
                actual_key = tuple((type(value), value) for value in actual)
                new_env = env_ids.get(actual_key)
                if new_env is None:
                    new_env = len(environments);env_ids[actual_key] = new_env;environments.append(actual)
                target = (node[1], new_env)
                if target not in cache:
                    pending.append((key, True));pending.append((target, False));continue
                cache[key] = cache[target];continue
            indices = node[1] if tag in {'and', 'or'} else (node[1],) if tag in {'not', 'read'} else node[2:] if tag == 'compare' else node[1:]
            children = [(arg, env_id) for arg in indices]
            if not finish:
                pending.append((key, True));pending.extend((child, False) for child in reversed(children));continue
            vals = [cache[child][0] for child in children]
            origin = next((cache[child][1] for child in children if cache[child][0] is True and cache[child][1] is not None), None)
            if tag == 'not':value = None if vals[0] is None else not vals[0]
            elif tag == 'and':value = False if False in vals else None if None in vals else True
            elif tag == 'or':value = True if True in vals else None if None in vals else False
            elif tag == 'choice':value = vals[1] if vals[0] is True else vals[2] if vals[0] is False else vals[1] if vals[1] == vals[2] else None
            elif tag == 'read':value = vals[0];origin = node[2] if value is True else None
            else:
                left, right = vals
                if left is None or right is None:value = None
                elif node[1] == 'EQ':value = left == right
                elif node[1] == 'NE':value = left != right
                elif node[1] == 'LT':value = left < right
                elif node[1] == 'LE':value = left <= right
                elif node[1] == 'GT':value = left > right
                else:value = left >= right
            cache[key] = (value, origin)
        value, origin = cache[root]
        return value, self.origins.get(origin), 'violation' if value is True else 'discharged' if value is False else 'unresolved actual predicate'
