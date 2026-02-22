import os

# Root directory
root_dir = r'D:\Dmarket_bot'

# Mappings of broken string -> correct string
# We use a very specific list to avoid false positives.
replacements = {
    'await': 'await',
    'raise': 'raise',
    'main': 'main',
    'aiolimiter': 'aiolimiter',
    'aiohttp': 'aiohttp',
    'Failed': 'Failed',
    'email': 'email',
    'detail': 'detail',
    'plain': 'plain',
    'chain': 'chain',
    'train': 'train',
    'available': 'available',
    'maintain': 'maintain',
    'remain': 'remain',
    'against': 'against',
    'brain': 'brain',
    'claim': 'claim',
    'contain': 'contain',
    'daily': 'daily',
    'gain': 'gain',
    'pail': 'pail',
    'paint': 'paint',
    'rail': 'rail',
    'sail': 'sail',
    'tail': 'tail',
    'wail': 'wail',
    'wait': 'wait',
    'openai': 'openai',
    'aiocache': 'aiocache',
    'aiometer': 'aiometer',
    'aiofiles': 'aiofiles',
    'aiodns': 'aiodns',
    'aioredis': 'aioredis',
    'aioamqp': 'aioamqp',
    'aioinflux': 'aioinflux',
    'aiopg': 'aiopg',
    'aiomysql': 'aiomysql',
    'aiozk': 'aiozk',
    'aiokafka': 'aiokafka',
    'aioboto3': 'aioboto3'
}

def fix_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        for broken, fixed in replacements.items():
            content = content.replace(broken, fixed)
            
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed: {filepath}")
            return True
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    return False

def main():
    count = 0
    for subdir, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(('.py', '.rs')):
                full_path = os.path.join(subdir, file)
                if fix_file(full_path):
                    count += 1
    print(f"Total files fixed: {count}")

if __name__ == '__main__':
    main()
