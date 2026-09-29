from pathlib import Path
p=Path('tmp/untyped-constants-next/candidate/a7/passes/type_checker.py')
s=p.read_text().replace('        format_type = arg_types[0] if arg_types else UNKNOWN', '''        for arg in args[1:]:
            exact = getattr(arg, 'exact_constant', None)
            if exact is not None and not exact[1] and not self._integer_literal_fits_type(exact[0].numerator, I32):
                self.add_error("Exact constant does not fit formatting default i32; use an explicitly typed intermediate", arg.span)
        format_type = arg_types[0] if arg_types else UNKNOWN''')
p.write_text(s)
