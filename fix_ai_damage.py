import os

root_dir = r'D:\Dmarket_bot'

# Map of damaged string -> correct string
# Based on "AI" -> "Algo" replacement
fixes = {
    'raise': 'raise',
    'await': 'await',
    'main': 'main',
    'fail': 'fail',
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
    'aiolimiter': 'aiolimiter',
    'aiohttp': 'aiohttp',
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

for subdir, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(subdir, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                for wrong, right in fixes.items():
                    content = content.replace(wrong, right)
                
                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f'Fixed: {filepath}')
            except Exception as e:
                print(f'Skipped {filepath}: {e}')
