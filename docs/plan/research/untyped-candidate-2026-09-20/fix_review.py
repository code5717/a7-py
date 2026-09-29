from pathlib import Path
p=Path('tmp/untyped-constants-next/candidate/a7/exact_constants.py')
s=p.read_text().replace("values[key] = (Fraction(node.raw_text), True)","value = Fraction(node.raw_text)\n                floating = 'negative_zero' if not value and node.raw_text.startswith('-') else True\n                values[key] = (value, floating)")
s=s.replace('values[key] = (-value, floating)',"values[key] = (-value, ('negative_zero' if floating != 'negative_zero' else True) if floating and not value else floating)")
s=s.replace('values[key] = (result, lf or rf)', '''floating = bool(lf or rf)
                if not result and floating:
                    ln = left < 0 or lf == 'negative_zero'
                    rn = right < 0 or rf == 'negative_zero'
                    negative = (ln != rn) if node.operator == BinaryOp.MUL else (ln and (rn if node.operator == BinaryOp.ADD else not rn))
                    if negative:
                        floating = 'negative_zero'
                values[key] = (result, floating)''')
s=s.replace('node.raw_text = decimal_text(value)',"node.raw_text = '-0.0' if floating == 'negative_zero' else decimal_text(value)")
p.write_text(s)
p=Path('tmp/untyped-constants-next/candidate/a7/passes/type_checker.py')
s=p.read_text().replace('        exact = evaluate(node, self.symbols.lookup, self.exact_bindings)\n        if exact is not None:', '''        if node.kind == NodeKind.BINARY and node.operator in {BinaryOp.EQ, BinaryOp.NE, BinaryOp.LT, BinaryOp.LE, BinaryOp.GT, BinaryOp.GE}:
            left = evaluate(node.left, self.symbols.lookup, self.exact_bindings)
            right = evaluate(node.right, self.symbols.lookup, self.exact_bindings)
            if left is not None and right is not None:
                a, b = left[0], right[0]
                comparisons = {BinaryOp.EQ: a == b, BinaryOp.NE: a != b, BinaryOp.LT: a < b, BinaryOp.LE: a <= b, BinaryOp.GT: a > b, BinaryOp.GE: a >= b}
                node.literal_value = comparisons[node.operator]
                node.kind = NodeKind.LITERAL
                node.literal_kind = LiteralKind.BOOLEAN
                node.raw_text = 'true' if node.literal_value else 'false'
                node.left = node.right = None
        exact = evaluate(node, self.symbols.lookup, self.exact_bindings)
        if exact is not None:''')
p.write_text(s)
