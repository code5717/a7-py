"""Quick script to fix __post_init__ methods in types.py"""
import re

# Read the file
with open("a7/types.py", "r") as f:
    content = f.read()

# Remove all __post_init__ methods and replace with __init__
# This is a simplified fix - we'll keep the dataclass decorator but override __init__

# For VoidType and UnknownType (no fields)
content = re.sub(
    r'(@dataclass\(frozen=True\)\nclass (VoidType|UnknownType)\(Type\):.*?)def __post_init__\(self\):\s+object\.__setattr__\(self, \'kind\', TypeKind\.\w+\)',
    r'\1def __init__(self):\n        object.__setattr__(self, \'kind\', TypeKind.\2.upper())',
    content,
    flags=re.DOTALL
)

# For GenericParamType
content = content.replace(
    '    def __post_init__(self):\n        object.__setattr__(self, \'kind\', TypeKind.GENERIC_PARAM)',
    '    def __init__(self, name: str, constraint: Optional[\'TypeSet\'] = None):\n        object.__setattr__(self, \'kind\', TypeKind.GENERIC_PARAM)\n        object.__setattr__(self, \'name\', name)\n        object.__setattr__(self, \'constraint\', constraint)'
)

# For StructType, EnumType, UnionType, GenericInstanceType, TypeSet - more complex
# Let me do these manually in the next step

print("Basic fixes applied, check the file manually for remaining issues")
print("Remaining __post_init__ to fix manually:")
matches = re.findall(r'class (\w+)\(.*?\):.*?def __post_init__', content, re.DOTALL)
for match in set(matches):
    print(f"  - {match}")
