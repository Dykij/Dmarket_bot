"""Scan src/ for module-level os.getenv() calls and check load_dotenv ordering."""
import ast
import os

results = []

for root, dirs, files in os.walk('src'):
    for f in files:
        if not f.endswith('.py'):
            continue
        fp = os.path.join(root, f)
        try:
            with open(fp) as fh:
                source = fh.read()
            tree = ast.parse(source, fp)
        except (SyntaxError, UnicodeDecodeError):
            continue

        load_dotenv_line = None
        getenv_calls = []

        # Walk top-level statements only (module-level)
        for node in ast.iter_child_nodes(tree):
            # Find load_dotenv
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                func = node.value.func
                if (isinstance(func, ast.Name) and func.id == 'load_dotenv') or \
                   (isinstance(func, ast.Attribute) and func.attr == 'load_dotenv'):
                    load_dotenv_line = node.lineno

            # Find os.getenv in assignments
            if isinstance(node, ast.Assign):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func = child.func
                        if isinstance(func, ast.Attribute) and func.attr == 'getenv':
                            getenv_calls.append(child.lineno)
            
            # Find os.getenv in top-level expressions
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Attribute) and func.attr == 'getenv':
                    getenv_calls.append(node.lineno)
            
            # Find os.getenv in if-statements at module level
            if isinstance(node, ast.If):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func = child.func
                        if isinstance(func, ast.Attribute) and func.attr == 'getenv':
                            getenv_calls.append(child.lineno)

            # Find os.getenv in for-loops at module level
            if isinstance(node, ast.For):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func = child.func
                        if isinstance(func, ast.Attribute) and func.attr == 'getenv':
                            getenv_calls.append(child.lineno)

        if getenv_calls:
            for gl in getenv_calls:
                if load_dotenv_line is None:
                    marker = 'HAZARD'
                    reason = 'NO load_dotenv in module'
                elif gl < load_dotenv_line:
                    marker = 'HAZARD'
                    reason = f'getenv@L{gl} BEFORE load_dotenv@L{load_dotenv_line}'
                else:
                    marker = 'OK'
                    reason = f'after load_dotenv@L{load_dotenv_line}'
                
                results.append((marker, fp, gl, reason))

for marker, fp, gl, reason in sorted(results):
    print(f'{marker}: {fp}:{gl} — {reason}')
