import os

files_to_check = [
    'README.md',
    'backend/app/config.py',
    'backend/app/collector/collector.py',
    'backend/app/services/analytics.py',
    'docs/API.md',
    'docs/ARCHITECTURE.md',
    'docs/REST-API.md',
    'backend/tests/test_analytics.py',
    'backend/tests/test_routes.py'
]

def safe_replace(content, f):
    content = content.replace('30-day', '14-day')
    content = content.replace('30 days', '14 days')
    content = content.replace('RETENTION_DAYS", "30"', 'RETENTION_DAYS", "14"')
    content = content.replace('default_chart_range": "30d', 'default_chart_range": "14d')
    content = content.replace('high_30d', 'high_7d')
    content = content.replace('low_30d', 'low_7d')
    content = content.replace('average_30d', 'average_7d')
    content = content.replace('median_30d', 'median_7d')
    content = content.replace('volatility_30d', 'volatility_7d')
    content = content.replace('change_30d', 'change_7d')
    
    if f.endswith('.md'):
        content = content.replace('30d', '14d')
        content = content.replace('30D', '14D')
    
    # In collector and api_client, "30d" is needed for the Wiki API request, 
    # but the retention logic docstrings can be updated. We handled "30-day" and "30 days" above.
    return content

for f in files_to_check:
    if os.path.exists(f):
        with open(f, 'r', encoding='utf-8') as file:
            c = file.read()
        c = safe_replace(c, f)
        with open(f, 'w', encoding='utf-8') as file:
            file.write(c)

print('Done replacing.')
