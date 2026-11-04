"""Safe descriptive download names, including Unicode through RFC 5987."""
import re
import unicodedata
from urllib.parse import quote


def part(value, limit=45):
    value = unicodedata.normalize('NFKC', str(value))
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', ' ', value)
    return re.sub(r'\s+', '-', value.strip()).rstrip('. -')[:limit] or 'Schedule'


def report_disposition(row, extension):
    filename = '_'.join(['JadwAI', part(row.snapshot['term']), part(row.snapshot['name']),
                         'Statistics-Report', 'Full-Schedule', 'Draft', f'v{row.input_version}',
                         row.created_at.date().isoformat(), row.id[:8]]) + '.' + extension
    fallback = filename.encode('ascii', 'ignore').decode('ascii')
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(filename, safe="")}'
