import os
import ast

def get_imports(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except SyntaxError:
            return set()
    
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports

def find_all_py_files(root_dir):
    py_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        if '__pycache__' in dirpath or '.mypy_cache' in dirpath:
            continue
        for f in filenames:
            if f.endswith('.py'):
                py_files.append(os.path.join(dirpath, f))
    return py_files

def main():
    root = "D:\\Dmarket_bot\\src"
    entry_points = [
        os.path.join(root, "core", "autonomous_scanner.py"),
        os.path.join(root, "telegram", "bot.py")
    ]
    
    all_files = find_all_py_files(root)
    
    # Simple dependency mapping
    modules_map = {}
    for f in all_files:
        rel_path = os.path.relpath(f, root)
        mod_name = 'src.' + rel_path.replace(os.sep, '.')[:-3]
        if mod_name.endswith('.__init__'):
            mod_name = mod_name[:-9]
        modules_map[f] = mod_name
        
    # Walk dependencies from entry points
    visited_files = set(entry_points)
    queue = list(entry_points)
    
    # Pre-parse all imports to see who imports who
    file_to_imports = {f: get_imports(f) for f in all_files}
    
    while queue:
        current = queue.pop(0)
        current_imports = file_to_imports.get(current, set())
        
        for f in all_files:
            mod_name = modules_map[f]
            # If the current file imports mod_name, mark f as visited
            for imp in current_imports:
                if imp == mod_name or imp.startswith(mod_name + '.'):
                    if f not in visited_files:
                        visited_files.add(f)
                        queue.append(f)
                        
    print("=== CONNECTED FILES ===")
    for f in sorted(list(visited_files)):
        print(os.path.relpath(f, root))
        
    print("\n=== DISCONNECTED (ORPHANED) FILES ===")
    orphans = [f for f in all_files if f not in visited_files]
    for f in sorted(orphans):
        print(os.path.relpath(f, root))

if __name__ == "__main__":
    main()
