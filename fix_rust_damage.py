import os

root_dir = r'D:\Dmarket_bot\src\rust_core\src'

fixes = {
    'await': 'await',
    'raise': 'raise', # Rust uses raise? No. But maybe panic? Or just noise.
    # Rust uses await.
    # What about 'AI' in comments?
}

for subdir, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith('.rs'):
            filepath = os.path.join(subdir, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                if 'await' in content:
                    content = content.replace('await', 'await')
                
                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f'Fixed: {filepath}')
            except Exception as e:
                print(f'Skipped {filepath}: {e}')
