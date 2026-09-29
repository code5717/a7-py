from pathlib import Path
p=Path('tmp/untyped-constants-next/candidate/a7/passes/type_checker.py')
s=p.read_text().replace('        op = node.operator\n\n        # Arithmetic operators', '''        op = node.operator
        left_exact = getattr(node.left, 'exact_constant', None)
        right_exact = getattr(node.right, 'exact_constant', None)
        if op in {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL} and (left_exact is None) != (right_exact is None):
            constant = node.left if left_exact is not None else node.right
            concrete = right_type if left_exact is not None else left_type
            if isinstance(concrete, PrimitiveType) and concrete.is_integral():
                self._is_initializer_assignable_to(constant, self.get_type(constant), concrete, constant.span)
                return concrete

        # Arithmetic operators''')
p.write_text(s)
